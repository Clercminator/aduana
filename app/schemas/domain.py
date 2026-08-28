from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Provenance(StrEnum):
    EXTRACTED = "extracted"
    MANUAL = "manual"
    INFERRED = "inferred"
    DERIVED = "derived"


T = TypeVar("T")


class Cited(BaseModel, Generic[T]):
    value: T | None = None
    provenance: Provenance = Provenance.EXTRACTED
    page: int | None = Field(default=None, ge=1)
    source_text: str | None = None
    confidence: Decimal = Field(default=Decimal("0"), ge=0, le=1)

    @model_validator(mode="after")
    def validate_citation(self) -> "Cited[T]":
        if self.provenance == Provenance.EXTRACTED and self.value is not None:
            if self.page is None or not self.source_text:
                raise ValueError("extracted values require page and source_text")
        elif self.provenance != Provenance.EXTRACTED and (
            self.page is not None or self.source_text is not None
        ):
            raise ValueError("only extracted values may carry page/source_text")
        return self


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"currency mismatch: {self.currency} != {other.currency}")
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError(f"currency mismatch: {self.currency} != {other.currency}")
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, rate: Decimal) -> "Money":
        return Money(amount=self.amount * rate, currency=self.currency)


class DocumentType(StrEnum):
    DISPATCH_INSTRUCTION = "dispatch_instruction"
    BILL_OF_LADING = "bill_of_lading"
    COMMERCIAL_INVOICE = "commercial_invoice"
    PACKING_LIST = "packing_list"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    UNKNOWN = "unknown"


class ClassificationResponse(BaseModel):
    doc_type: DocumentType
    confidence: Decimal = Field(ge=0, le=1)
    evidence: str


class InvoiceLine(BaseModel):
    description: Cited[str]
    hs_code: Cited[str]
    quantity: Cited[Decimal]
    uom: Cited[str]
    unit_price: Cited[Decimal]
    line_total: Cited[Decimal]


class DispatchInstruction(BaseModel):
    doc_type: DocumentType = DocumentType.DISPATCH_INSTRUCTION
    despacho_no: Cited[str]
    referencia: Cited[str]
    importer_name: Cited[str]
    bl_number: Cited[str]
    invoice_numbers: list[Cited[str]] = []
    freight_amount: Cited[Decimal]
    freight_currency: Cited[str]
    agreement_name: Cited[str]


class BillOfLading(BaseModel):
    doc_type: DocumentType = DocumentType.BILL_OF_LADING
    bl_number: Cited[str]
    vessel: Cited[str]
    voyage: Cited[str]
    port_loading: Cited[str]
    port_discharge: Cited[str]
    shipped_on_board_date: Cited[date]
    consignee_name: Cited[str]
    gross_weight_kg: Cited[Decimal]
    package_count: Cited[int]
    measurement_cbm: Cited[Decimal]
    freight_amount: Cited[Decimal]
    freight_currency: Cited[str]
    declared_value_total: Cited[Decimal] = Field(default_factory=Cited[Decimal])
    container_number: Cited[str]
    invoice_numbers_cited: list[Cited[str]] = []


class CommercialInvoice(BaseModel):
    doc_type: DocumentType = DocumentType.COMMERCIAL_INVOICE
    invoice_number: Cited[str]
    invoice_date: Cited[date]
    supplier_name: Cited[str]
    consignee_name: Cited[str]
    incoterm: Cited[str]
    currency: Cited[str]
    invoice_total: Cited[Decimal]
    included_amounts: dict[str, Cited[Decimal]] = Field(default_factory=dict)
    package_count: Cited[int]
    gross_weight_kg: Cited[Decimal]
    net_weight_kg: Cited[Decimal]
    lines: list[InvoiceLine]


class PackingLine(BaseModel):
    invoice_number: Cited[str]
    description: Cited[str]
    quantity: Cited[Decimal]
    uom: Cited[str]
    cartons: Cited[int]
    gross_weight_kg: Cited[Decimal]
    net_weight_kg: Cited[Decimal]


class PackingList(BaseModel):
    doc_type: DocumentType = DocumentType.PACKING_LIST
    bl_number: Cited[str]
    consignee_name: Cited[str]
    container_number: Cited[str]
    package_count: Cited[int]
    gross_weight_kg: Cited[Decimal]
    net_weight_kg: Cited[Decimal]
    measurement_cbm: Cited[Decimal]
    lines: list[PackingLine]


class InsuranceCertificate(BaseModel):
    doc_type: DocumentType = DocumentType.INSURANCE_CERTIFICATE
    certificate_number: Cited[str]
    assured_name: Cited[str]
    bl_number: Cited[str]
    sum_insured: Cited[Decimal]
    premium: Cited[Decimal]
    premium_rate: Cited[Decimal]
    currency: Cited[str]
    coverage_basis: Cited[str]
    invoices_covered: list[Cited[str]] = []


class OriginItem(BaseModel):
    hs_code: Cited[str]
    description: Cited[str]
    origin_criterion: Cited[str] = Field(default_factory=Cited)
    net_weight_or_quantity: Cited[Decimal]
    weight_or_quantity_unit: Cited[str] = Field(default_factory=Cited)
    invoice_number: Cited[str]
    invoice_date: Cited[date] = Field(default_factory=Cited)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_gross_weight(cls, data: Any) -> Any:
        if isinstance(data, dict) and "net_weight_or_quantity" not in data:
            legacy = data.get("gross_weight_kg")
            if legacy is not None:
                data = dict(data)
                data["net_weight_or_quantity"] = legacy
                data.setdefault(
                    "weight_or_quantity_unit",
                    Cited(value="KGS", provenance=Provenance.INFERRED).model_dump(),
                )
        return data


class CertificateOfOrigin(BaseModel):
    doc_type: DocumentType = DocumentType.CERTIFICATE_OF_ORIGIN
    certificate_number: Cited[str]
    issue_date: Cited[date]
    exporter_name: Cited[str]
    issuing_authority: Cited[str] = Field(default_factory=Cited)
    consignee_name: Cited[str]
    agreement_name: Cited[str]
    departure_date: Cited[date]
    is_retrospective: Cited[bool]
    container_number: Cited[str]
    items: list[OriginItem]

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_importer_name(cls, data: Any) -> Any:
        if isinstance(data, dict) and "consignee_name" not in data and "importer_name" in data:
            data = dict(data)
            data["consignee_name"] = data["importer_name"]
        return data


ExtractedDocument = (
    DispatchInstruction
    | BillOfLading
    | CommercialInvoice
    | PackingList
    | InsuranceCertificate
    | CertificateOfOrigin
)


class CostLine(BaseModel):
    code: str
    amount: Money
    dutiable: bool
    source: str


class AllocationInput(BaseModel):
    key: str
    basis: Money


class AllocationResult(BaseModel):
    key: str
    share: Decimal
    amounts: dict[str, Money]
    residual_codes: list[str] = []


class LevyResult(BaseModel):
    code: str
    label: str
    base_expression: str
    base_amount: Money
    rate: Decimal
    amount: Money
    recoverable: bool


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class RuleResult(BaseModel):
    id: str
    severity: Severity
    status: RuleStatus
    title: str
    detail: str
    suggested_action: str | None = None
    financial_impact: dict[str, str] | None = None
    source_refs: list[dict[str, Any]] = []


class DispatchBundle(BaseModel):
    instruction: DispatchInstruction | None = None
    bill_of_lading: BillOfLading | None = None
    invoices: list[CommercialInvoice] = []
    packing_list: PackingList | None = None
    insurance: InsuranceCertificate | None = None
    certificate_of_origin: CertificateOfOrigin | None = None
