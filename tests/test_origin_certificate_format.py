from decimal import Decimal
from pathlib import Path

import pdfplumber
import pytest

from app.llm.local_extract import extract_local
from app.schemas.domain import CertificateOfOrigin
from scripts.origin_certificate_fixture import (
    OriginCertificateData,
    OriginItemData,
    render_origin_certificate,
)

ROOT = Path(__file__).parents[1]


def origin_paths() -> list[Path]:
    paths = list((ROOT / "fixtures").glob("scenario_[ABCD]*/*ORIGIN*.pdf"))
    paths.extend(
        (ROOT / "fixtures" / "scenario_E_document_realism").glob("origin_certificate*.pdf")
    )
    return sorted(paths)


def test_all_origin_certificates_follow_the_two_page_reference_form():
    paths = origin_paths()
    assert len(paths) == 6
    for path in paths:
        with pdfplumber.open(path) as pdf:
            assert len(pdf.pages) == 2
            assert pdf.pages[0].width == pytest.approx(216 * 72 / 25.4, abs=0.5)
            assert pdf.pages[0].height == pytest.approx(330 * 72 / 25.4, abs=0.5)
            front = pdf.pages[0].extract_text() or ""
            overleaf = pdf.pages[1].extract_text() or ""
        assert "1. Exporter's name, address, country:" in front
        assert "3. Consignee's name, address, country:" in front
        assert "11. Net weight or" in front
        assert "14. Certification" in front
        assert "Gross weight" not in front
        assert "SYNTHETIC DEMO - NOT VALID FOR CUSTOMS OR COMMERCIAL USE" in front
        assert "Overleaf Instruction" in overleaf
        assert "Fifty is the maximum" in overleaf
        assert all(criterion in overleaf for criterion in ("WO", "WP", "RVC", "PSR"))


def test_scenario_a_origin_extraction_uses_reference_semantics():
    parsed = extract_local(
        ROOT / "fixtures" / "scenario_A_clean" / "05_CERTIFICATE_OF_ORIGIN_C26CL0114772.pdf"
    )
    assert parsed.consignee_name.value == "FALABELLA RETAIL S.A."
    assert "China Council for the Promotion of International Trade" in (
        parsed.issuing_authority.value or ""
    )
    assert [item.net_weight_or_quantity.value for item in parsed.items] == [
        Decimal("4680.0"),
        Decimal("6820.0"),
        Decimal("2110.0"),
    ]
    assert {item.weight_or_quantity_unit.value for item in parsed.items} == {"KGS"}
    assert {item.origin_criterion.value for item in parsed.items} == {"WO"}
    assert [item.invoice_date.value.isoformat() for item in parsed.items] == [
        "2026-06-08",
        "2026-06-08",
        "2026-06-09",
    ]


def test_origin_schema_accepts_legacy_importer_and_gross_weight_payloads():
    current = extract_local(
        ROOT / "fixtures" / "scenario_A_clean" / "05_CERTIFICATE_OF_ORIGIN_C26CL0114772.pdf"
    ).model_dump(mode="json")
    current["importer_name"] = current.pop("consignee_name")
    for item in current["items"]:
        item["gross_weight_kg"] = item.pop("net_weight_or_quantity")
        item.pop("origin_criterion")
        item.pop("weight_or_quantity_unit")
        item.pop("invoice_date")
    parsed = CertificateOfOrigin.model_validate(current)
    assert parsed.consignee_name.value == "FALABELLA RETAIL S.A."
    assert parsed.items[0].net_weight_or_quantity.value == Decimal("4680.0")
    assert parsed.items[0].weight_or_quantity_unit.value == "KGS"


def test_scenario_c_keeps_all_40_items_on_the_form_page():
    path = ROOT / "fixtures" / "scenario_C_volume" / "05_CERTIFICATE_OF_ORIGIN_C26CL0124001.pdf"
    parsed = extract_local(path)
    assert len(parsed.items) == 40
    assert parsed.items[0].invoice_number.value == "BN26010601"
    assert parsed.items[-1].invoice_number.value == "BN26010640"
    with pdfplumber.open(path) as pdf:
        overleaf = pdf.pages[1].extract_text() or ""
    assert "BN26010621" not in overleaf
    assert "Overleaf Instruction" in overleaf


def test_realism_variants_cover_all_origin_criteria_and_front_page_retrospective_logic():
    target = ROOT / "fixtures" / "scenario_E_document_realism"
    first = extract_local(target / "origin_certificate_01_stamped.pdf")
    second = extract_local(target / "origin_certificate_02_stamped.pdf")
    criteria = {item.origin_criterion.value for item in [*first.items, *second.items]}
    assert criteria == {"WO", "WP", "RVC", "PSR"}
    assert first.is_retrospective.value is False
    assert second.is_retrospective.value is True


def test_renderer_supports_the_reference_maximum_of_50_items(tmp_path):
    criteria = ("WO", "WP", "RVC", "PSR")
    items = tuple(
        OriginItemData(
            marks="N/M",
            packages="1 CARTON",
            description=f"Synthetic maximum-row item {index}",
            hs_code="6302.60",
            origin_criterion=criteria[(index - 1) % len(criteria)],
            net_weight_or_quantity=Decimal(index),
            unit="KGS",
            invoice_number=f"BN269900{index:02d}",
            invoice_date="2026-09-01",
        )
        for index in range(1, 51)
    )
    path = tmp_path / "maximum-50-items.pdf"
    render_origin_certificate(
        path,
        OriginCertificateData(
            certificate_number="TEST-COO-50",
            exporter_name="SYNTHETIC EXPORTER CO., LTD.",
            exporter_address="Synthetic address, CHINA",
            producer="SAME",
            consignee_name="SYNTHETIC CONSIGNEE SpA",
            consignee_address="Synthetic address, CHILE",
            issued_in="CHINA",
            departure_date="2026-09-02",
            transport_number="SYNTHETIC VESSEL V.1",
            port_of_loading="SHANGHAI, CHINA",
            port_of_discharge="VALPARAISO, CHILE",
            remarks="Maximum-row rendering test.",
            issue_place="SHANGHAI",
            issue_date="2026-09-01",
            issuing_authority="Synthetic test authority",
            items=items,
        ),
    )
    parsed = extract_local(path)
    assert len(parsed.items) == 50
    assert parsed.items[-1].invoice_number.value == "BN26990050"
