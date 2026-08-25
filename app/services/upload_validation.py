from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from fastapi import UploadFile

from app.config import Settings

READ_CHUNK_BYTES = 1024 * 1024
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}


@dataclass(frozen=True)
class UploadRejected(Exception):
    status_code: int
    detail: str


def _validate_pdf(
    filename: str, content_type: str | None, content: bytes, settings: Settings
) -> None:
    if Path(filename).suffix.lower() != ".pdf":
        raise UploadRejected(415, f"{filename}: solo se permiten archivos .pdf")
    if content_type and content_type.lower() not in PDF_CONTENT_TYPES:
        raise UploadRejected(415, f"{filename}: tipo de contenido no permitido ({content_type})")
    if not content.startswith(b"%PDF"):
        raise UploadRejected(415, f"{filename}: la firma del archivo no corresponde a un PDF")
    try:
        document = pdfium.PdfDocument(content)
        page_count = len(document)
        document.close()
    except Exception as exc:
        raise UploadRejected(422, f"{filename}: PDF dañado o ilegible") from exc
    if page_count == 0:
        raise UploadRejected(422, f"{filename}: el PDF no contiene páginas")
    if page_count > settings.max_pdf_pages:
        raise UploadRejected(
            413,
            f"{filename}: {page_count} páginas exceden el máximo de {settings.max_pdf_pages}",
        )


async def read_validated_uploads(
    files: list[UploadFile], settings: Settings
) -> list[tuple[str, bytes]]:
    if not files:
        raise UploadRejected(400, "Debe cargar al menos un PDF")
    if len(files) > settings.max_upload_files:
        raise UploadRejected(
            413,
            f"La carga contiene {len(files)} archivos; el máximo es {settings.max_upload_files}",
        )

    total_bytes = 0
    uploads: list[tuple[str, bytes]] = []
    for upload in files:
        filename = Path(upload.filename or "document.pdf").name
        content = bytearray()
        try:
            while chunk := await upload.read(READ_CHUNK_BYTES):
                content.extend(chunk)
                total_bytes += len(chunk)
                if len(content) > settings.max_upload_file_bytes:
                    raise UploadRejected(
                        413,
                        f"{filename}: excede el máximo de {settings.max_upload_file_bytes} bytes",
                    )
                if total_bytes > settings.max_upload_batch_bytes:
                    raise UploadRejected(
                        413,
                        "La carga completa excede el máximo de "
                        f"{settings.max_upload_batch_bytes} bytes",
                    )
        finally:
            await upload.close()
        payload = bytes(content)
        _validate_pdf(filename, upload.content_type, payload, settings)
        uploads.append((filename, payload))
    return uploads
