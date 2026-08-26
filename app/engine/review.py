from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.engine.client import ClientExtractionConfig

LOCAL_EXTRACTION_LABEL = "Extracción local determinista — demo"
AI_EXTRACTION_LABEL = "Extracción con IA — OpenRouter"


def extraction_mode(records: list[dict[str, Any]]) -> dict[str, Any]:
    providers = {str(item.get("provider") or "") for item in records}
    ai_used = "openrouter" in providers or any(
        item.get("parser") == "openrouter" for item in records
    )
    return {
        "mode": "openrouter" if ai_used else "local",
        "label": AI_EXTRACTION_LABEL if ai_used else LOCAL_EXTRACTION_LABEL,
        "providers": sorted(item for item in providers if item),
        "ocr_reused": sum(1 for item in records if item.get("ocr_reused")),
    }


def _walk_pattern(value: Any, parts: list[str], prefix: str = "") -> list[tuple[str, Any]]:
    if not parts:
        return [(prefix, value)]
    part, rest = parts[0], parts[1:]
    if part == "*":
        if not isinstance(value, list):
            return []
        output: list[tuple[str, Any]] = []
        for index, child in enumerate(value):
            output.extend(_walk_pattern(child, rest, f"{prefix}.{index}".strip(".")))
        return output
    if not isinstance(value, dict) or part not in value:
        return []
    return _walk_pattern(value[part], rest, f"{prefix}.{part}".strip("."))


def _confidence(value: Any) -> Decimal:
    if not isinstance(value, dict):
        return Decimal("0")
    try:
        return Decimal(str(value.get("confidence", "0")))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def evaluate_review_gates(
    documents: list[dict[str, Any]],
    effective_payloads: list[dict[str, Any]],
    expected_documents: dict[str, int],
    config: ClientExtractionConfig,
) -> dict[str, Any]:
    reasons: list[dict[str, Any]] = []
    required = {"dispatch_instruction": 1, **expected_documents}
    successful = [item for item in documents if item.get("extraction_status") == "done"]
    for doc_type, expected in required.items():
        received = sum(1 for item in successful if item.get("doc_type") == doc_type)
        if received < int(expected):
            reasons.append(
                {
                    "category": "completeness",
                    "code": "MISSING_REQUIRED_DOCUMENT",
                    "document_type": doc_type,
                    "detail": f"{received}/{expected} extracciones completas",
                }
            )

    for document in documents:
        if document.get("extraction_status") != "done":
            reasons.append(
                {
                    "category": "completeness",
                    "code": "EXTRACTION_NOT_SUCCESSFUL",
                    "document_id": document.get("id"),
                    "filename": document.get("filename"),
                    "detail": document.get("extraction_error") or "Extracción no completada",
                }
            )
        try:
            confidence = Decimal(str(document.get("classify_confidence") or "0"))
        except InvalidOperation:
            confidence = Decimal("0")
        if confidence < config.classification_min_confidence:
            reasons.append(
                {
                    "category": "confidence",
                    "code": "LOW_CLASSIFICATION_CONFIDENCE",
                    "document_id": document.get("id"),
                    "filename": document.get("filename"),
                    "confidence": str(confidence),
                    "threshold": str(config.classification_min_confidence),
                    "detail": "Clasificación requiere revisión humana",
                }
            )

    payload_by_id = {item["document_id"]: item["payload"] for item in effective_payloads}
    for document in successful:
        payload = payload_by_id.get(str(document.get("id")))
        if not isinstance(payload, dict):
            continue
        doc_type = str(document.get("doc_type") or "")
        for pattern in config.review_fields.get(doc_type, []):
            matches = _walk_pattern(payload, pattern.split("."))
            if not matches:
                reasons.append(
                    {
                        "category": "confidence",
                        "code": "MISSING_FINANCIAL_FIELD",
                        "document_id": document.get("id"),
                        "filename": document.get("filename"),
                        "field_path": pattern,
                        "detail": "Campo crítico ausente; revisión humana obligatoria",
                    }
                )
                continue
            for path, cited in matches:
                value = cited.get("value") if isinstance(cited, dict) else None
                confidence = _confidence(cited)
                if value is None or value == "":
                    code = "MISSING_FINANCIAL_FIELD"
                    detail = "Campo crítico sin valor; revisión humana obligatoria"
                elif confidence < config.financial_min_confidence:
                    code = "LOW_FINANCIAL_CONFIDENCE"
                    detail = "Campo crítico bajo el umbral; revisión humana obligatoria"
                else:
                    continue
                reasons.append(
                    {
                        "category": "confidence",
                        "code": code,
                        "document_id": document.get("id"),
                        "filename": document.get("filename"),
                        "field_path": path or pattern,
                        "confidence": str(confidence),
                        "threshold": str(config.financial_min_confidence),
                        "detail": detail,
                    }
                )

    return {
        "blocked": bool(reasons),
        "can_calculate": not any(item["category"] == "completeness" for item in reasons),
        "reason_count": len(reasons),
        "reasons": reasons,
        "thresholds": {
            "classification": str(config.classification_min_confidence),
            "financial": str(config.financial_min_confidence),
        },
    }
