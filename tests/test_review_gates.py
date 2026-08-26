import pytest
from fastapi import HTTPException

from app.api.routes import _require_exportable
from app.engine.client import ClientExtractionConfig
from app.engine.review import AI_EXTRACTION_LABEL, evaluate_review_gates, extraction_mode


def _config() -> ClientExtractionConfig:
    return ClientExtractionConfig(
        classification_min_confidence="0.90",
        financial_min_confidence="0.95",
        review_fields={"commercial_invoice": ["invoice_total", "lines.*.line_total"]},
    )


def _documents(status: str = "done") -> list[dict]:
    return [
        {
            "id": "instruction",
            "filename": "instruction.pdf",
            "doc_type": "dispatch_instruction",
            "classify_confidence": "0.99",
            "extraction_status": "done",
        },
        {
            "id": "invoice",
            "filename": "invoice.pdf",
            "doc_type": "commercial_invoice",
            "classify_confidence": "0.99",
            "extraction_status": status,
            "extraction_error": "provider unavailable" if status != "done" else None,
        },
    ]


def _payload(confidence: str) -> list[dict]:
    cited = {"value": "100", "confidence": confidence, "provenance": "extracted"}
    return [
        {
            "document_id": "invoice",
            "payload": {
                "doc_type": "commercial_invoice",
                "invoice_total": cited,
                "lines": [{"line_total": cited}],
            },
        }
    ]


def test_failed_extraction_blocks_calculation_and_completion():
    result = evaluate_review_gates(_documents("failed"), [], {"commercial_invoice": 1}, _config())

    assert result["blocked"] is True
    assert result["can_calculate"] is False
    assert {reason["code"] for reason in result["reasons"]} >= {
        "MISSING_REQUIRED_DOCUMENT",
        "EXTRACTION_NOT_SUCCESSFUL",
    }


def test_low_confidence_financial_field_requires_human_review():
    result = evaluate_review_gates(
        _documents(), _payload("0.72"), {"commercial_invoice": 1}, _config()
    )

    assert result["blocked"] is True
    assert result["can_calculate"] is True
    assert any(reason["code"] == "LOW_FINANCIAL_CONFIDENCE" for reason in result["reasons"])


def test_manual_high_confidence_financial_field_passes_gate():
    result = evaluate_review_gates(
        _documents(), _payload("1"), {"commercial_invoice": 1}, _config()
    )

    assert result["blocked"] is False
    assert result["can_calculate"] is True


def test_export_gate_fails_closed():
    with pytest.raises(HTTPException) as caught:
        _require_exportable({"review": {"blocked": True}})

    assert caught.value.status_code == 409


def test_openrouter_attempt_selects_the_ai_processing_label():
    result = extraction_mode([{"provider": "Google", "parser": "openrouter", "ocr_reused": True}])

    assert result == {
        "mode": "openrouter",
        "label": AI_EXTRACTION_LABEL,
        "providers": ["Google"],
        "ocr_reused": 1,
    }
