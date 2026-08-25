from pathlib import Path

from app.config import Settings
from app.llm.client import OpenRouterClient
from app.llm.local_extract import extract_local, pdf_text
from app.schemas.domain import (
    BillOfLading,
    CertificateOfOrigin,
    CommercialInvoice,
    DispatchInstruction,
    DocumentType,
    InsuranceCertificate,
    PackingList,
)

SCHEMAS = {
    DocumentType.DISPATCH_INSTRUCTION: DispatchInstruction,
    DocumentType.BILL_OF_LADING: BillOfLading,
    DocumentType.COMMERCIAL_INVOICE: CommercialInvoice,
    DocumentType.PACKING_LIST: PackingList,
    DocumentType.INSURANCE_CERTIFICATE: InsuranceCertificate,
    DocumentType.CERTIFICATE_OF_ORIGIN: CertificateOfOrigin,
}


def extract_document(path: Path, doc_type: DocumentType, settings: Settings):
    if settings.extraction_backend == "local" or (
        settings.extraction_backend == "auto" and not settings.openrouter_api_key
    ):
        return extract_local(path), {
            "backend": "local-demo",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": "0",
            "provider": "local",
            "model": "regex-fixture-v1",
            "raw": {"mode": "local-demo", "parsed_from": str(path.name)},
        }
    schema = SCHEMAS[doc_type]
    prompt_template = (Path(__file__).parent / "prompts" / "extract.txt").read_text(
        encoding="utf-8"
    )
    _, _, has_text = pdf_text(path)
    with OpenRouterClient(settings) as client:
        parsed, raw = client.extract_pdf(
            path, prompt_template.format(doc_type=doc_type.value), schema, ocr=not has_text
        )
        metadata = client.usage(raw)
    metadata["backend"] = "openrouter"
    metadata["ocr_used"] = not has_text
    return parsed, metadata
