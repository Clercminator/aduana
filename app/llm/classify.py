from app.schemas.domain import DocumentType

SIGNATURES: tuple[tuple[str, DocumentType], ...] = (
    ("INSTRUCCIÓN DE DESPACHO", DocumentType.DISPATCH_INSTRUCTION),
    ("BILL OF LADING", DocumentType.BILL_OF_LADING),
    ("COMMERCIAL INVOICE", DocumentType.COMMERCIAL_INVOICE),
    ("PACKING LIST", DocumentType.PACKING_LIST),
    ("CERTIFICADO DE SEGURO", DocumentType.INSURANCE_CERTIFICATE),
    ("CERTIFICATE OF ORIGIN", DocumentType.CERTIFICATE_OF_ORIGIN),
)


def classify_text(text: str) -> tuple[DocumentType, str]:
    upper = text.upper()
    for signature, doc_type in SIGNATURES:
        if signature in upper:
            return doc_type, signature
    return DocumentType.UNKNOWN, ""
