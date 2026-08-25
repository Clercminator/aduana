from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "org"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


class JurisdictionConfigVersion(Base):
    __tablename__ = "jurisdiction_config_version"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(2), index=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    content: Mapped[dict] = mapped_column(JSONB)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientConfigVersion(Base):
    __tablename__ = "client_config_version"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client: Mapped[str] = mapped_column(String(80), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(2), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    content: Mapped[dict] = mapped_column(JSONB)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CustomsFxRate(Base):
    __tablename__ = "customs_fx_rate"
    __table_args__ = (
        UniqueConstraint("org_id", "base_currency", "quote_currency", "year", "month"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    source: Mapped[str] = mapped_column(String(200))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dispatch(Base):
    __tablename__ = "dispatch"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    jurisdiction_config_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jurisdiction_config_version.id")
    )
    client_config_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("client_config_version.id")
    )
    customs_fx_rate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customs_fx_rate.id"))
    jurisdiction: Mapped[str] = mapped_column(String(2), default="CL")
    regime: Mapped[str] = mapped_column(String(40), default="import_for_consumption")
    despacho_no: Mapped[str | None] = mapped_column(String(60))
    referencia: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(40), default="awaiting_documents")
    expected_documents: Mapped[dict] = mapped_column(JSONB, default=dict)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    fx_source: Mapped[str | None] = mapped_column(String(200))
    fx_date: Mapped[date | None] = mapped_column(Date)
    din_acceptance_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "document"
    __table_args__ = (UniqueConstraint("dispatch_id", "content_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100), default="application/pdf")
    doc_type: Mapped[str | None] = mapped_column(String(50))
    classify_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    page_count: Mapped[int | None] = mapped_column(Integer)
    has_text_layer: Mapped[bool | None] = mapped_column(Boolean)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExtractionRun(Base):
    __tablename__ = "extraction_run"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    parser: Mapped[str] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    provider: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(30), default="v1")
    schema_version: Mapped[str] = mapped_column(String(30), default="v1")
    payload: Mapped[dict | None] = mapped_column(JSONB)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FieldCorrection(Base):
    __tablename__ = "field_correction"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    field_path: Mapped[str] = mapped_column(String(300))
    value: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "job"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(60), default="queued")
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=0)
    error: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CalculationRun(Base):
    __tablename__ = "calculation_run"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    engine_version: Mapped[str] = mapped_column(String(30), default="v1")
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExceptionResult(Base):
    __tablename__ = "exception_result"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    calculation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculation_run.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(20), index=True)
    severity: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSONB)
    accepted_rationale: Mapped[str | None] = mapped_column(Text)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifact"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org.id"), index=True)
    dispatch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dispatch.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(50))
    path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
