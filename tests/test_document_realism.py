import json
from pathlib import Path

from app.llm.local_extract import pdf_text

ROOT = Path(__file__).parents[1]


def test_realism_pack_has_12_templates_stamps_languages_and_two_photo_pdfs():
    target = ROOT / "fixtures" / "scenario_E_document_realism"
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    invoices = manifest["invoices"]

    assert manifest["distinct_supplier_templates"] == 12
    assert len({item["supplier"] for item in invoices}) == 12
    assert all(item["stamp_overlay"] for item in invoices)
    assert any(item["language"] == "mixed English/Spanish" for item in invoices)
    assert len(manifest["stamped_origin_certificates"]) == 2

    photo_paths = [target / item["file"] for item in invoices if item["image_only_phone_photo"]]
    assert len(photo_paths) == 2
    for path in photo_paths:
        text, pages, has_text_layer = pdf_text(path)
        assert pages == 1
        assert not has_text_layer
        assert text.strip() == ""

    vector_path = target / invoices[0]["file"]
    text, pages, has_text_layer = pdf_text(vector_path)
    assert pages == 1
    assert has_text_layer
    assert "COMMERCIAL INVOICE" in text
