import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.config import Settings
from app.services.upload_validation import UploadRejected, read_validated_uploads

ROOT = Path(__file__).parents[1]
VALID_PDF = (
    ROOT / "fixtures" / "scenario_A_clean" / "00_INSTRUCCION_DESPACHO_700611.pdf"
).read_bytes()


def upload(
    content: bytes = VALID_PDF,
    filename: str = "document.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    return UploadFile(
        BytesIO(content),
        filename=filename,
        size=len(content),
        headers=Headers({"content-type": content_type}),
    )


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_valid_pdf_upload_is_returned_with_a_sanitized_filename():
    result = asyncio.run(
        read_validated_uploads([upload(filename="folder/invoice.pdf")], settings())
    )
    assert result == [("invoice.pdf", VALID_PDF)]


@pytest.mark.parametrize(
    ("item", "status_code"),
    [
        (upload(filename="invoice.exe"), 415),
        (upload(content_type="text/plain"), 415),
        (upload(content=b"%PDF-not-a-real-document"), 422),
    ],
)
def test_non_pdf_or_broken_upload_is_rejected(item: UploadFile, status_code: int):
    with pytest.raises(UploadRejected) as caught:
        asyncio.run(read_validated_uploads([item], settings()))
    assert caught.value.status_code == status_code


def test_per_file_and_batch_size_limits_are_enforced_before_persistence():
    with pytest.raises(UploadRejected) as file_error:
        asyncio.run(
            read_validated_uploads([upload()], settings(max_upload_file_bytes=len(VALID_PDF) - 1))
        )
    assert file_error.value.status_code == 413

    with pytest.raises(UploadRejected) as batch_error:
        asyncio.run(
            read_validated_uploads(
                [upload(filename="one.pdf"), upload(filename="two.pdf")],
                settings(max_upload_batch_bytes=len(VALID_PDF) * 2 - 1),
            )
        )
    assert batch_error.value.status_code == 413


def test_file_count_limit_is_enforced():
    with pytest.raises(UploadRejected) as caught:
        asyncio.run(
            read_validated_uploads(
                [upload(filename="one.pdf"), upload(filename="two.pdf")],
                settings(max_upload_files=1),
            )
        )
    assert caught.value.status_code == 413
