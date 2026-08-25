from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.cl_din import din_payload, render_din_pdf
from app.adapters.xlsx import build_workbook
from app.config import Settings, get_settings
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
    GeneratedArtifact,
    Job,
    JurisdictionConfigVersion,
    Org,
)
from app.db.session import get_db
from app.engine.agency import load_agency_catalog
from app.engine.client import load_client_profile
from app.services.bootstrap import ensure_demo_records
from app.services.storage import LocalDocumentStore
from app.services.upload_validation import UploadRejected, read_validated_uploads

router = APIRouter(prefix="/api")


class CorrectionRequest(BaseModel):
    value: Any
    reason: str = Field(min_length=3)


class RationaleRequest(BaseModel):
    rationale: str = Field(min_length=3)


@dataclass(frozen=True)
class TenantContext:
    org_id: uuid.UUID
    slug: str
    name: str


def require_tenant(
    x_org_id: str | None = Header(default=None, alias="X-Org-ID"),
    org_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> TenantContext:
    if x_org_id and org_id and x_org_id != org_id:
        raise HTTPException(400, "X-Org-ID y org_id deben identificar la misma organización")
    raw_org_id = x_org_id or org_id
    if not raw_org_id:
        raise HTTPException(400, "Falta el contexto obligatorio X-Org-ID")
    try:
        parsed_org_id = uuid.UUID(raw_org_id)
    except ValueError as exc:
        raise HTTPException(400, "El contexto de organización no es un UUID válido") from exc
    organization = db.get(Org, parsed_org_id)
    if organization is None:
        raise HTTPException(404, "Organización no encontrada")
    return TenantContext(org_id=organization.id, slug=organization.slug, name=organization.name)


def _dispatch_for_tenant(db: Session, dispatch_id: uuid.UUID, tenant: TenantContext) -> Dispatch:
    dispatch = db.scalar(
        select(Dispatch).where(Dispatch.id == dispatch_id, Dispatch.org_id == tenant.org_id)
    )
    if dispatch is None:
        raise HTTPException(404, "Despacho no encontrado")
    return dispatch


def _record_artifact(
    db: Session,
    settings: Settings,
    dispatch: Dispatch,
    kind: str,
    extension: str,
    content: bytes,
) -> None:
    digest = hashlib.sha256(content).hexdigest()
    target = settings.artifact_root / str(dispatch.org_id) / digest[:2] / f"{digest}.{extension}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_bytes(content)
    db.add(
        GeneratedArtifact(
            org_id=dispatch.org_id,
            dispatch_id=dispatch.id,
            kind=kind,
            path=str(target.resolve()),
            content_hash=digest,
        )
    )
    db.commit()


def _create_dispatch(
    db: Session, settings: Settings, tenant: TenantContext, expected_invoices: int = 3
) -> Dispatch:
    pins = ensure_demo_records(db, settings, tenant.org_id)
    dispatch = Dispatch(
        org_id=tenant.org_id,
        jurisdiction_config_version_id=pins.jurisdiction.id,
        client_config_version_id=pins.client.id,
        customs_fx_rate_id=pins.fx_rate.id,
        jurisdiction="CL",
        status="awaiting_documents",
        expected_documents={
            "bill_of_lading": 1,
            "commercial_invoice": expected_invoices,
            "packing_list": 1,
            "insurance_certificate": 1,
            "certificate_of_origin": 1,
        },
        fx_rate=Decimal(settings.demo_fx_rate),
        fx_source=settings.demo_fx_source,
        fx_date=date.fromisoformat(settings.demo_fx_date),
        din_acceptance_date=date.fromisoformat(settings.demo_din_acceptance_date),
    )
    db.add(dispatch)
    db.commit()
    db.refresh(dispatch)
    return dispatch


def _add_documents(
    db: Session, settings: Settings, dispatch: Dispatch, uploads: list[tuple[str, bytes]]
) -> tuple[int, int]:
    store = LocalDocumentStore(settings.document_root / str(dispatch.org_id))
    added = duplicates = 0
    for filename, content in uploads:
        if not content.startswith(b"%PDF"):
            raise HTTPException(415, f"{filename} no es un PDF válido")
        digest, path = store.put(content)
        existing = db.scalar(
            select(Document).where(
                Document.dispatch_id == dispatch.id, Document.content_hash == digest
            )
        )
        if existing:
            duplicates += 1
            continue
        db.add(
            Document(
                org_id=dispatch.org_id,
                dispatch_id=dispatch.id,
                filename=Path(filename).name,
                content_hash=digest,
                storage_path=str(path),
            )
        )
        added += 1
    db.add(
        AuditEvent(
            org_id=dispatch.org_id,
            dispatch_id=dispatch.id,
            action="documents_uploaded",
            payload={"added": added, "duplicates": duplicates},
        )
    )
    db.commit()
    return added, duplicates


def _queue(db: Session, dispatch: Dispatch) -> Job:
    running = db.scalar(
        select(Job).where(
            Job.org_id == dispatch.org_id,
            Job.dispatch_id == dispatch.id,
            Job.status.in_(["queued", "running"]),
        )
    )
    if running:
        return running
    job = Job(
        org_id=dispatch.org_id, dispatch_id=dispatch.id, status="queued", stage="queued", progress=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "demo_only": True}


@router.get("/demo/agencies")
def demo_agencies(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    agencies = []
    for loaded in load_agency_catalog(settings.agency_root):
        agency = loaded.config
        client = load_client_profile(settings.client_root / agency.client_profile).config
        agencies.append(
            {
                "organization_id": str(agency.organization_id),
                "slug": agency.slug,
                "name": agency.name,
                "client": client.client,
                "client_label": agency.client_label,
                "branding": agency.branding.model_dump(mode="json"),
                "policy": {
                    "insurance_mode": client.insurance.mode,
                    "policy_rate": str(client.insurance.policy_rate)
                    if client.insurance.policy_rate is not None
                    else None,
                    "coverage_pct": str(client.insurance.coverage_pct),
                    "allocation_basis": client.allocation.basis,
                    "default_incoterm": client.default_incoterm,
                    "transport_document": client.transport_document,
                },
            }
        )
    return {
        "agencies": agencies,
        "upload_limits": {
            "max_files": settings.max_upload_files,
            "max_file_bytes": settings.max_upload_file_bytes,
            "max_batch_bytes": settings.max_upload_batch_bytes,
            "max_pdf_pages": settings.max_pdf_pages,
        },
    }


@router.post("/intake/batches", status_code=202)
async def intake_batch(
    files: list[UploadFile] = File(...),
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        uploads = await read_validated_uploads(files, settings)
    except UploadRejected as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    dispatch = _create_dispatch(db, settings, tenant)
    added, duplicates = _add_documents(db, settings, dispatch, uploads)
    job = _queue(db, dispatch)
    return {
        "dispatch_id": str(dispatch.id),
        "job_id": str(job.id),
        "added": added,
        "duplicates": duplicates,
    }


@router.post("/demo/load/{scenario}", status_code=202)
def load_demo(
    scenario: str,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    scenarios = {
        "A": ("scenario_A_clean", 3),
        "B": ("scenario_B_exceptions", 3),
        "C": ("scenario_C_volume", 40),
        "D": ("scenario_D_cif", 1),
    }
    key = scenario.upper()
    if key not in scenarios:
        raise HTTPException(404, "Escenario debe ser A, B, C o D")
    folder, expected_invoices = scenarios[key]
    dispatch = _create_dispatch(db, settings, tenant, expected_invoices=expected_invoices)
    paths = sorted((settings.fixture_root / folder).glob("*.pdf"))
    uploads = [(path.name, path.read_bytes()) for path in paths]
    added, duplicates = _add_documents(db, settings, dispatch, uploads)
    job = _queue(db, dispatch)
    return {
        "dispatch_id": str(dispatch.id),
        "job_id": str(job.id),
        "added": added,
        "duplicates": duplicates,
    }


@router.post("/dispatches/{dispatch_id}/documents", status_code=202)
async def add_dispatch_documents(
    dispatch_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    try:
        uploads = await read_validated_uploads(files, settings)
    except UploadRejected as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc
    added, duplicates = _add_documents(db, settings, dispatch, uploads)
    job = _queue(db, dispatch)
    return {
        "dispatch_id": str(dispatch.id),
        "job_id": str(job.id),
        "added": added,
        "duplicates": duplicates,
    }


@router.get("/jobs/{job_id}")
def get_job(
    job_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    job = db.scalar(select(Job).where(Job.id == job_id, Job.org_id == tenant.org_id))
    if not job:
        raise HTTPException(404, "Trabajo no encontrado")
    elapsed = None
    if job.started_at:
        end = job.finished_at or datetime.now(job.started_at.tzinfo)
        elapsed = (end - job.started_at).total_seconds()
    return {
        "id": str(job.id),
        "dispatch_id": str(job.dispatch_id),
        "status": job.status,
        "stage": job.stage,
        "progress": str(job.progress),
        "error": job.error,
        "elapsed_seconds": elapsed,
    }


def _state(db: Session, dispatch_id: uuid.UUID, tenant: TenantContext) -> dict[str, Any]:
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    docs = db.scalars(
        select(Document)
        .where(Document.org_id == tenant.org_id, Document.dispatch_id == dispatch.id)
        .order_by(Document.filename)
    ).all()
    document_payloads = []
    for doc in docs:
        extraction = db.scalar(
            select(ExtractionRun)
            .where(
                ExtractionRun.document_id == doc.id,
                ExtractionRun.org_id == tenant.org_id,
                ExtractionRun.status == "done",
                ExtractionRun.parser != "classification",
            )
            .order_by(ExtractionRun.created_at.desc())
        )
        document_payloads.append(
            {
                "id": str(doc.id),
                "filename": doc.filename,
                "content_hash": doc.content_hash,
                "doc_type": doc.doc_type,
                "classify_confidence": str(doc.classify_confidence)
                if doc.classify_confidence is not None
                else None,
                "page_count": doc.page_count,
                "has_text_layer": doc.has_text_layer,
                "ocr_used": doc.ocr_used,
                "file_url": f"/api/documents/{doc.id}/file?org_id={tenant.org_id}",
                "extraction": extraction.payload if extraction else None,
                "extraction_status": extraction.status if extraction else "pending",
            }
        )
    calc = db.scalar(
        select(CalculationRun)
        .where(
            CalculationRun.org_id == tenant.org_id,
            CalculationRun.dispatch_id == dispatch.id,
        )
        .order_by(CalculationRun.created_at.desc())
    )
    calculation = json.loads(json.dumps(calc.payload)) if calc else None
    config_version = db.get(JurisdictionConfigVersion, dispatch.jurisdiction_config_version_id)
    client_version = db.scalar(
        select(ClientConfigVersion).where(
            ClientConfigVersion.id == dispatch.client_config_version_id,
            ClientConfigVersion.org_id == tenant.org_id,
        )
    )
    fx_rate = db.get(CustomsFxRate, dispatch.customs_fx_rate_id)
    if calc and calculation:
        persisted = db.scalars(
            select(ExceptionResult).where(
                ExceptionResult.org_id == tenant.org_id,
                ExceptionResult.calculation_run_id == calc.id,
            )
        ).all()
        by_rule = {item.rule_id: item for item in persisted}
        for rule in calculation.get("rules", []):
            record = by_rule.get(rule.get("id"))
            if record:
                rule["exception_id"] = str(record.id)
                rule["accepted_rationale"] = record.accepted_rationale
    audit = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.org_id == tenant.org_id, AuditEvent.dispatch_id == dispatch.id)
        .order_by(AuditEvent.created_at.desc())
    ).all()
    artifacts = db.scalars(
        select(GeneratedArtifact)
        .where(
            GeneratedArtifact.org_id == tenant.org_id,
            GeneratedArtifact.dispatch_id == dispatch.id,
        )
        .order_by(GeneratedArtifact.created_at.desc())
    ).all()
    return {
        "dispatch": {
            "id": str(dispatch.id),
            "organization_id": str(tenant.org_id),
            "organization_name": tenant.name,
            "organization_slug": tenant.slug,
            "despacho_no": dispatch.despacho_no,
            "referencia": dispatch.referencia,
            "status": dispatch.status,
            "regime": dispatch.regime,
            "jurisdiction": dispatch.jurisdiction,
            "jurisdiction_config_hash": config_version.content_hash if config_version else None,
            "client_config_hash": client_version.content_hash if client_version else None,
            "client": client_version.client if client_version else None,
            "din_acceptance_date": dispatch.din_acceptance_date.isoformat()
            if dispatch.din_acceptance_date
            else None,
            "fx_period": f"{fx_rate.year:04d}-{fx_rate.month:02d}" if fx_rate else None,
            "expected_documents": dispatch.expected_documents,
            "created_at": dispatch.created_at.isoformat(),
        },
        "documents": document_payloads,
        "calculation": calculation,
        "calculation_run": {
            "id": str(calc.id),
            "input_hash": calc.input_hash,
            "engine_version": calc.engine_version,
            "created_at": calc.created_at.isoformat(),
        }
        if calc
        else None,
        "audit": [
            {
                "action": item.action,
                "payload": item.payload,
                "created_at": item.created_at.isoformat(),
            }
            for item in audit
        ],
        "artifacts": [
            {
                "id": str(item.id),
                "kind": item.kind,
                "content_hash": item.content_hash,
                "created_at": item.created_at.isoformat(),
            }
            for item in artifacts
        ],
    }


@router.get("/dispatches/{dispatch_id}")
def get_dispatch(
    dispatch_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    return _state(db, dispatch_id, tenant)


@router.post("/dispatches/{dispatch_id}/run", status_code=202)
def rerun(
    dispatch_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    job = _queue(db, dispatch)
    return {"job_id": str(job.id), "dispatch_id": str(dispatch.id)}


@router.patch("/dispatches/{dispatch_id}/fields/{field_path:path}", status_code=202)
def correct_field(
    dispatch_id: uuid.UUID,
    field_path: str,
    request: CorrectionRequest,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    document_id, sep, path = field_path.partition(":")
    if not sep or not path:
        raise HTTPException(400, "La ruta debe ser document_id:ruta.del.campo.value")
    try:
        doc_uuid = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(400, "document_id inválido") from exc
    document = db.scalar(
        select(Document).where(
            Document.id == doc_uuid,
            Document.org_id == tenant.org_id,
            Document.dispatch_id == dispatch.id,
        )
    )
    if document is None:
        raise HTTPException(404, "Documento no encontrado")
    correction = FieldCorrection(
        org_id=dispatch.org_id,
        dispatch_id=dispatch.id,
        field_path=field_path,
        value={"value": request.value},
        reason=request.reason,
    )
    db.add(correction)
    db.add(
        AuditEvent(
            org_id=dispatch.org_id,
            dispatch_id=dispatch.id,
            action="field_corrected",
            payload={"field_path": field_path, "reason": request.reason, "value": request.value},
        )
    )
    db.commit()
    job = _queue(db, dispatch)
    return {"correction_id": str(correction.id), "job_id": str(job.id)}


@router.post("/exceptions/{exception_id}/accept-risk")
def accept_risk(
    exception_id: uuid.UUID,
    request: RationaleRequest,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    item = db.scalar(
        select(ExceptionResult).where(
            ExceptionResult.id == exception_id,
            ExceptionResult.org_id == tenant.org_id,
        )
    )
    if not item:
        raise HTTPException(404, "Excepción no encontrada")
    item.accepted_rationale = request.rationale
    item.accepted_at = datetime.now(UTC)
    db.add(
        AuditEvent(
            org_id=item.org_id,
            dispatch_id=item.dispatch_id,
            action="risk_accepted_demo",
            payload={"rule_id": item.rule_id, "rationale": request.rationale},
        )
    )
    db.commit()
    return {
        "status": "accepted",
        "notice": "Aceptación de demo con alcance tenant; autenticación aún pendiente",
    }


@router.get("/documents/{document_id}/file")
def document_file(
    document_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.org_id == tenant.org_id,
        )
    )
    if not document:
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(
        document.storage_path, media_type="application/pdf", filename=document.filename
    )


@router.get("/dispatches/{dispatch_id}/exports/reconciliation.xlsx")
def export_xlsx(
    dispatch_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    state = _state(db, dispatch_id, tenant)
    content = build_workbook(state)
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    _record_artifact(db, settings, dispatch, "reconciliation_xlsx", "xlsx", content)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="reconciliacion-{state["dispatch"]["despacho_no"] or dispatch_id}.xlsx"'
        },
    )


@router.get("/dispatches/{dispatch_id}/exports/din.json")
def export_din_json(
    dispatch_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    payload = din_payload(_state(db, dispatch_id, tenant))
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    _record_artifact(db, settings, dispatch, "din_json", "json", content)
    return Response(
        content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="din-demo-{dispatch_id}.json"'},
    )


@router.get("/dispatches/{dispatch_id}/exports/din.pdf")
def export_din_pdf(
    dispatch_id: uuid.UUID,
    tenant: TenantContext = Depends(require_tenant),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    content = render_din_pdf(_state(db, dispatch_id, tenant))
    dispatch = _dispatch_for_tenant(db, dispatch_id, tenant)
    _record_artifact(db, settings, dispatch, "din_pdf", "pdf", content)
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="din-demo-{dispatch_id}.pdf"'},
    )
