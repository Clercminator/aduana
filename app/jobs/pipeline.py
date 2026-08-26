from __future__ import annotations

import hashlib
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    AuditEvent,
    CalculationRun,
    ClientConfigVersion,
    CustomsFxRate,
    Dispatch,
    Document,
    ExceptionResult,
    ExtractionRun,
    FieldCorrection,
    Job,
    JurisdictionConfigVersion,
)
from app.engine.client import ClientExtractionConfig, ClientProfileConfig, DocumentTemplateConfig
from app.engine.fx import validate_rate_period
from app.engine.jurisdiction import JurisdictionConfig
from app.engine.reconcile import reconcile
from app.engine.review import evaluate_review_gates, extraction_mode
from app.llm.classify import classify_text
from app.llm.client import OpenRouterClient
from app.llm.extract import SCHEMAS
from app.llm.local_extract import extract_local_text, pdf_text
from app.schemas.domain import DispatchBundle, DocumentType


@dataclass(frozen=True)
class DocumentTask:
    document_id: uuid.UUID
    path: Path
    extraction_config: ClientExtractionConfig | None = None


@dataclass(frozen=True)
class PendingExtractionRun:
    status: str
    parser: str
    model: str | None = None
    provider: str | None = None
    payload: dict[str, Any] | None = None
    raw_response: dict[str, Any] | None = None
    error: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = Decimal("0")
    latency_ms: int | None = None


@dataclass(frozen=True)
class DocumentOutcome:
    document_id: uuid.UUID
    doc_type: DocumentType
    classify_confidence: Decimal
    page_count: int | None
    has_text_layer: bool | None
    ocr_used: bool
    classification: PendingExtractionRun
    extraction: PendingExtractionRun | None = None
    attempts: tuple[PendingExtractionRun, ...] = ()


def _match_template(
    text: str, doc_type: DocumentType, config: ClientExtractionConfig | None
) -> DocumentTemplateConfig | None:
    if config is None:
        return None
    normalized = text.casefold()
    for template in config.templates:
        if doc_type.value not in template.document_types:
            continue
        if any(marker.casefold() in normalized for marker in template.match_any):
            return template
    return None


def _local_classification(text: str, has_text: bool) -> tuple[DocumentType, Decimal, str | None]:
    doc_type, signature = classify_text(text)
    confidence = Decimal("0.999") if has_text and signature else Decimal("0")
    return doc_type, confidence, signature


def _failed_outcome(task: DocumentTask, error: Exception) -> DocumentOutcome:
    return DocumentOutcome(
        document_id=task.document_id,
        doc_type=DocumentType.UNKNOWN,
        classify_confidence=Decimal("0"),
        page_count=None,
        has_text_layer=None,
        ocr_used=False,
        classification=PendingExtractionRun(
            status="failed", parser="classification", error=str(error)
        ),
    )


def _process_document(task: DocumentTask, settings: Settings) -> DocumentOutcome:
    """Perform file and provider I/O without touching the SQLAlchemy session."""
    try:
        text, pages, has_text = pdf_text(task.path)
    except Exception as exc:
        return _failed_outcome(task, exc)

    classification_started = time.perf_counter()
    local_type, local_confidence, signature = _local_classification(text, has_text)
    template = _match_template(text, local_type, task.extraction_config)
    local_requested = settings.extraction_backend == "local" or (
        settings.extraction_backend == "auto" and not settings.openrouter_api_key
    )
    configured_local = settings.extraction_backend == "hybrid" and template is not None
    if local_requested or configured_local:
        doc_type = local_type
        confidence = local_confidence
        classification = PendingExtractionRun(
            status="done" if signature else "failed",
            parser="classification",
            model="content-signature-v1",
            provider="local",
            payload={
                "doc_type": doc_type.value,
                "confidence": str(confidence),
                "evidence": signature,
            },
            raw_response={
                "text_layer": has_text,
                "template_id": template.id if template else None,
            },
            latency_ms=int((time.perf_counter() - classification_started) * 1000),
        )
        raw_classification: dict[str, Any] | None = None
        client = None
    else:
        if not settings.openrouter_api_key:
            message = (
                "No configured supplier template matched this layout and "
                "OPENROUTER_API_KEY is not configured for the hybrid fallback"
            )
            return DocumentOutcome(
                document_id=task.document_id,
                doc_type=local_type,
                classify_confidence=local_confidence,
                page_count=pages,
                has_text_layer=has_text,
                ocr_used=False,
                classification=PendingExtractionRun(
                    status="failed",
                    parser="classification",
                    provider="hybrid",
                    error=message,
                    latency_ms=int((time.perf_counter() - classification_started) * 1000),
                ),
            )
        try:
            client = OpenRouterClient(settings)
            classified, raw_classification = client.classify_document(
                text, path=task.path if not has_text else None
            )
            classification_meta = client.usage(raw_classification)
        except Exception as exc:
            if client is not None:
                client.close()
            return DocumentOutcome(
                document_id=task.document_id,
                doc_type=DocumentType.UNKNOWN,
                classify_confidence=Decimal("0"),
                page_count=pages,
                has_text_layer=has_text,
                ocr_used=False,
                classification=PendingExtractionRun(
                    status="failed",
                    parser="classification",
                    model=settings.classify_model,
                    provider="openrouter",
                    error=str(exc),
                    latency_ms=int((time.perf_counter() - classification_started) * 1000),
                ),
            )
        doc_type = classified.doc_type
        confidence = classified.confidence
        classification = PendingExtractionRun(
            status="done",
            parser="classification",
            model=classification_meta.get("model"),
            provider=classification_meta.get("provider"),
            payload=classified.model_dump(mode="json"),
            raw_response=classification_meta.get("raw"),
            tokens_in=int(classification_meta["tokens_in"]),
            tokens_out=int(classification_meta["tokens_out"]),
            cost_usd=Decimal(str(classification_meta["cost_usd"])),
            latency_ms=int((time.perf_counter() - classification_started) * 1000),
        )
    if doc_type == DocumentType.UNKNOWN:
        if client is not None:
            client.close()
        return DocumentOutcome(
            document_id=task.document_id,
            doc_type=doc_type,
            classify_confidence=confidence,
            page_count=pages,
            has_text_layer=has_text,
            ocr_used=False,
            classification=classification,
        )

    extraction_started = time.perf_counter()
    attempts: list[PendingExtractionRun] = []
    try:
        if local_requested or configured_local:
            try:
                parsed = extract_local_text(text, doc_type)
                metadata = {
                    "backend": "local-demo",
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cost_usd": "0",
                    "provider": "local",
                    "model": "regex-fixture-v1",
                    "raw": {
                        "mode": "local-demo",
                        "template_id": template.id if template else "forced-local",
                    },
                    "ocr_used": False,
                }
            except Exception as local_error:
                if settings.extraction_backend != "hybrid" or not settings.openrouter_api_key:
                    raise
                attempts.append(
                    PendingExtractionRun(
                        status="failed",
                        parser="local-demo",
                        provider="local",
                        model="regex-fixture-v1",
                        error=str(local_error),
                    )
                )
                client = OpenRouterClient(settings)
                classified, raw_classification = client.classify_document(
                    text, path=task.path if not has_text else None
                )
                doc_type = classified.doc_type
                confidence = classified.confidence
                classification_meta = client.usage(raw_classification)
                classification = PendingExtractionRun(
                    status="done",
                    parser="classification",
                    model=classification_meta.get("model"),
                    provider=classification_meta.get("provider") or "openrouter",
                    payload=classified.model_dump(mode="json"),
                    raw_response=classification_meta.get("raw"),
                    tokens_in=int(classification_meta["tokens_in"]),
                    tokens_out=int(classification_meta["tokens_out"]),
                    cost_usd=Decimal(str(classification_meta["cost_usd"])),
                )
                schema = SCHEMAS[doc_type]
                prompt = (Path(__file__).parents[1] / "llm" / "prompts" / "extract.txt").read_text(
                    encoding="utf-8"
                )
                parsed, raw = client.extract_pdf(
                    task.path,
                    prompt.format(doc_type=doc_type.value),
                    schema,
                    ocr=not has_text,
                    classification_body=raw_classification,
                )
                metadata = client.usage(raw)
                metadata.update(
                    backend="openrouter",
                    ocr_used=not has_text,
                    ocr_reused=bool(client.file_annotations(raw_classification or {})),
                )
        else:
            assert client is not None
            schema = SCHEMAS[doc_type]
            prompt = (Path(__file__).parents[1] / "llm" / "prompts" / "extract.txt").read_text(
                encoding="utf-8"
            )
            parsed, raw = client.extract_pdf(
                task.path,
                prompt.format(doc_type=doc_type.value),
                schema,
                ocr=not has_text,
                classification_body=raw_classification,
            )
            metadata = client.usage(raw)
            metadata.update(
                backend="openrouter",
                ocr_used=not has_text,
                ocr_reused=bool(client.file_annotations(raw_classification or {})),
            )
        extraction = PendingExtractionRun(
            status="done",
            parser=metadata.get("backend", "unknown"),
            model=metadata.get("model"),
            provider=metadata.get("provider"),
            payload=parsed.model_dump(mode="json"),
            raw_response={
                "provider_response": metadata.get("raw"),
                "ocr_reused": bool(metadata.get("ocr_reused", False)),
                "template_id": template.id
                if template and metadata.get("provider") == "local"
                else None,
            },
            tokens_in=int(metadata.get("tokens_in", 0)),
            tokens_out=int(metadata.get("tokens_out", 0)),
            cost_usd=Decimal(str(metadata.get("cost_usd", "0"))),
            latency_ms=int((time.perf_counter() - extraction_started) * 1000),
        )
        ocr_used = bool(metadata.get("ocr_used", False))
    except Exception as exc:
        extraction = PendingExtractionRun(
            status="failed",
            parser="extraction",
            error=str(exc),
            latency_ms=int((time.perf_counter() - extraction_started) * 1000),
        )
        ocr_used = False
    finally:
        if client is not None:
            client.close()

    return DocumentOutcome(
        document_id=task.document_id,
        doc_type=doc_type,
        classify_confidence=confidence,
        page_count=pages,
        has_text_layer=has_text,
        ocr_used=ocr_used,
        classification=classification,
        extraction=extraction,
        attempts=tuple(attempts),
    )


def _run_document_tasks(tasks: list[DocumentTask], settings: Settings):
    """Yield completed documents while keeping provider concurrency bounded."""
    worker_count = min(settings.document_concurrency, len(tasks))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="pdf") as executor:
        future_tasks = {executor.submit(_process_document, task, settings): task for task in tasks}
        for future in as_completed(future_tasks):
            task = future_tasks[future]
            try:
                yield future.result()
            except Exception as exc:  # defensive isolation between documents
                yield _failed_outcome(task, exc)


def _persist_run(
    db: Session,
    job: Job,
    document_id: uuid.UUID,
    run: PendingExtractionRun,
) -> ExtractionRun:
    record = ExtractionRun(
        org_id=job.org_id,
        document_id=document_id,
        status=run.status,
        parser=run.parser,
        model=run.model,
        provider=run.provider,
        payload=run.payload,
        raw_response=run.raw_response,
        error=run.error,
        tokens_in=run.tokens_in,
        tokens_out=run.tokens_out,
        cost_usd=run.cost_usd,
        latency_ms=run.latency_ms,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    return record


def _persist_outcome(db: Session, job: Job, outcome: DocumentOutcome) -> tuple[int, int, Decimal]:
    document = db.scalar(
        select(Document).where(
            Document.id == outcome.document_id,
            Document.org_id == job.org_id,
        )
    )
    if document is None:
        raise ValueError(f"document not found: {outcome.document_id}")
    document.doc_type = outcome.doc_type.value
    document.classify_confidence = outcome.classify_confidence
    document.page_count = outcome.page_count
    document.has_text_layer = outcome.has_text_layer
    document.ocr_used = outcome.ocr_used
    runs = [outcome.classification, *outcome.attempts]
    _persist_run(db, job, outcome.document_id, outcome.classification)
    for attempt in outcome.attempts:
        _persist_run(db, job, outcome.document_id, attempt)
    if outcome.extraction is not None:
        runs.append(outcome.extraction)
        _persist_run(db, job, outcome.document_id, outcome.extraction)
    return (
        sum(run.tokens_in for run in runs),
        sum(run.tokens_out for run in runs),
        sum((run.cost_usd for run in runs), Decimal("0")),
    )


def _latest_extractions(
    db: Session, dispatch_id: uuid.UUID, org_id: uuid.UUID
) -> list[tuple[Document, ExtractionRun]]:
    documents = db.scalars(
        select(Document)
        .where(Document.org_id == org_id, Document.dispatch_id == dispatch_id)
        .order_by(Document.uploaded_at)
    ).all()
    output = []
    for document in documents:
        run = db.scalar(
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == document.id,
                ExtractionRun.org_id == org_id,
                ExtractionRun.status == "done",
                ExtractionRun.parser != "classification",
            )
            .order_by(ExtractionRun.created_at.desc())
        )
        if run:
            output.append((document, run))
    return output


def _review_document_records(
    db: Session, documents: list[Document], org_id: uuid.UUID
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gate_documents: list[dict[str, Any]] = []
    extraction_records: list[dict[str, Any]] = []
    for document in documents:
        run = db.scalar(
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == document.id,
                ExtractionRun.org_id == org_id,
                ExtractionRun.parser != "classification",
            )
            .order_by(ExtractionRun.created_at.desc())
        )
        gate_documents.append(
            {
                "id": str(document.id),
                "filename": document.filename,
                "doc_type": document.doc_type,
                "classify_confidence": str(document.classify_confidence or "0"),
                "extraction_status": run.status if run else "pending",
                "extraction_error": run.error if run else None,
            }
        )
        if run and run.status == "done":
            raw = run.raw_response or {}
            extraction_records.append(
                {
                    "provider": run.provider,
                    "model": run.model,
                    "parser": run.parser,
                    "ocr_reused": bool(raw.get("ocr_reused")),
                }
            )
    return gate_documents, extraction_records


def _set_path(payload: dict, path: str, value) -> None:
    current = payload
    parts = path.split(".")
    for part in parts[:-1]:
        if part.isdigit():
            current = current[int(part)]
        else:
            current = current[part]
    leaf = parts[-1]
    if leaf.isdigit():
        current[int(leaf)] = value
    else:
        current[leaf] = value


def build_bundle(
    db: Session, dispatch_id: uuid.UUID, org_id: uuid.UUID
) -> tuple[DispatchBundle, list[dict]]:
    extracted = _latest_extractions(db, dispatch_id, org_id)
    corrections = db.scalars(
        select(FieldCorrection)
        .where(FieldCorrection.org_id == org_id, FieldCorrection.dispatch_id == dispatch_id)
        .order_by(FieldCorrection.created_at)
    ).all()
    correction_map: dict[str, list[FieldCorrection]] = {}
    for correction in corrections:
        document_id, _, path = correction.field_path.partition(":")
        correction_map.setdefault(document_id, []).append(correction)
    payloads: list[dict] = []
    typed = []
    for document, run in extracted:
        payload = json.loads(json.dumps(run.payload))
        for correction in correction_map.get(str(document.id), []):
            _, _, path = correction.field_path.partition(":")
            _set_path(payload, path, correction.value.get("value"))
            cited_root = path.rsplit(".", 1)[0]
            try:
                _set_path(payload, cited_root + ".provenance", "manual")
                _set_path(payload, cited_root + ".page", None)
                _set_path(payload, cited_root + ".source_text", None)
                _set_path(payload, cited_root + ".confidence", "1")
            except (KeyError, TypeError, IndexError):
                pass
        doc_type = DocumentType(payload["doc_type"])
        typed.append(SCHEMAS[doc_type].model_validate(payload))
        payloads.append(
            {"document_id": str(document.id), "filename": document.filename, "payload": payload}
        )

    bundle = DispatchBundle()
    for item in typed:
        if item.doc_type == DocumentType.DISPATCH_INSTRUCTION:
            bundle.instruction = item
        elif item.doc_type == DocumentType.BILL_OF_LADING:
            bundle.bill_of_lading = item
        elif item.doc_type == DocumentType.COMMERCIAL_INVOICE:
            bundle.invoices.append(item)
        elif item.doc_type == DocumentType.PACKING_LIST:
            bundle.packing_list = item
        elif item.doc_type == DocumentType.INSURANCE_CERTIFICATE:
            bundle.insurance = item
        elif item.doc_type == DocumentType.CERTIFICATE_OF_ORIGIN:
            bundle.certificate_of_origin = item
    bundle.invoices.sort(key=lambda item: item.invoice_number.value or "")
    return bundle, payloads


def process_job(db: Session, job: Job, settings: Settings) -> None:
    dispatch = db.scalar(
        select(Dispatch).where(
            Dispatch.id == job.dispatch_id,
            Dispatch.org_id == job.org_id,
        )
    )
    if not dispatch:
        raise ValueError("dispatch not found")
    client_version = db.scalar(
        select(ClientConfigVersion).where(
            ClientConfigVersion.id == dispatch.client_config_version_id,
            ClientConfigVersion.org_id == job.org_id,
        )
    )
    if client_version is None:
        raise ValueError("pinned client config version not found")
    client_config = ClientProfileConfig.model_validate(client_version.content)
    job.status = "running"
    job.stage = "classification"
    job.started_at = datetime.now(timezone.utc)
    dispatch.status = "extracting"
    db.commit()
    documents = db.scalars(
        select(Document)
        .where(Document.org_id == job.org_id, Document.dispatch_id == dispatch.id)
        .order_by(Document.uploaded_at, Document.filename)
    ).all()
    tokens_in = tokens_out = 0
    cost = Decimal("0")
    tasks: list[DocumentTask] = []
    for document in documents:
        existing = db.scalar(
            select(ExtractionRun).where(
                ExtractionRun.document_id == document.id,
                ExtractionRun.org_id == job.org_id,
                ExtractionRun.status == "done",
                ExtractionRun.parser != "classification",
            )
        )
        if existing is None:
            tasks.append(
                DocumentTask(
                    document_id=document.id,
                    path=Path(document.storage_path),
                    extraction_config=client_config.extraction,
                )
            )

    total_documents = max(len(documents), 1)
    completed_documents = len(documents) - len(tasks)
    job.stage = "extraction"
    job.progress = Decimal(completed_documents) / Decimal(total_documents) * Decimal("0.85")
    db.commit()

    if tasks:
        for outcome in _run_document_tasks(tasks, settings):
            run_tokens_in, run_tokens_out, run_cost = _persist_outcome(db, job, outcome)
            tokens_in += run_tokens_in
            tokens_out += run_tokens_out
            cost += run_cost
            completed_documents += 1
            job.progress = Decimal(completed_documents) / Decimal(total_documents) * Decimal("0.85")
            db.commit()

    job.stage = "reconciliation"
    job.progress = Decimal("0.90")
    db.commit()
    bundle, effective_payloads = build_bundle(db, dispatch.id, job.org_id)
    if bundle.instruction:
        dispatch.despacho_no = bundle.instruction.despacho_no.value
        dispatch.referencia = bundle.instruction.referencia.value
    gate_documents, extraction_records = _review_document_records(db, documents, job.org_id)
    review = evaluate_review_gates(
        gate_documents,
        effective_payloads,
        dispatch.expected_documents,
        client_config.extraction,
    )
    processing = extraction_mode(extraction_records)
    db.add(
        AuditEvent(
            org_id=job.org_id,
            dispatch_id=dispatch.id,
            action="review_gate_evaluated",
            payload={"review": review, "processing": processing},
        )
    )

    if not review["can_calculate"]:
        dispatch.status = "review_required"
        job.status = "needs_review"
        job.stage = "review_required"
        job.progress = Decimal("1")
        job.tokens_in = tokens_in
        job.tokens_out = tokens_out
        job.cost_usd = cost
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return

    config_version = db.get(JurisdictionConfigVersion, dispatch.jurisdiction_config_version_id)
    if config_version is None:
        raise ValueError("pinned jurisdiction config version not found")
    config = JurisdictionConfig.model_validate(config_version.content)
    fx_record = db.scalar(
        select(CustomsFxRate).where(
            CustomsFxRate.id == dispatch.customs_fx_rate_id,
            CustomsFxRate.org_id == job.org_id,
        )
    )
    if fx_record is None:
        raise ValueError("pinned customs FX rate not found")
    acceptance_date = dispatch.din_acceptance_date or date.fromisoformat(
        settings.demo_din_acceptance_date
    )
    rate_date = date(fx_record.year, fx_record.month, 1)
    validate_rate_period(rate_date, acceptance_date, config.fx)
    calculation = reconcile(
        bundle,
        config,
        client_config,
        fx_record.rate,
        fx_record.source,
        rate_date,
    )
    input_json = json.dumps(
        {
            "documents": effective_payloads,
            "jurisdiction_config_hash": config_version.content_hash,
            "client_config_hash": client_version.content_hash,
            "fx_rate": str(fx_record.rate),
            "fx_source": fx_record.source,
            "fx_period": f"{fx_record.year:04d}-{fx_record.month:02d}",
            "din_acceptance_date": acceptance_date.isoformat(),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    input_hash = hashlib.sha256(input_json.encode("utf-8")).hexdigest()
    calc_run = db.scalar(
        select(CalculationRun).where(
            CalculationRun.org_id == job.org_id,
            CalculationRun.dispatch_id == dispatch.id,
            CalculationRun.input_hash == input_hash,
        )
    )
    if calc_run is None:
        calc_run = CalculationRun(
            org_id=job.org_id,
            dispatch_id=dispatch.id,
            input_hash=input_hash,
            payload=calculation,
        )
        db.add(calc_run)
        db.flush()
        for result in calculation["rules"]:
            db.add(
                ExceptionResult(
                    org_id=job.org_id,
                    dispatch_id=dispatch.id,
                    calculation_run_id=calc_run.id,
                    rule_id=result["id"],
                    severity=result["severity"],
                    result=result["status"],
                    payload=result,
                )
            )
    dispatch.status = "review_required" if review["blocked"] else "review"
    job.status = "needs_review" if review["blocked"] else "done"
    job.stage = "review_required" if review["blocked"] else "done"
    job.progress = Decimal("1")
    job.tokens_in = tokens_in
    job.tokens_out = tokens_out
    job.cost_usd = cost
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
