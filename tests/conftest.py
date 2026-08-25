from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.engine.client import load_client_profile
from app.engine.jurisdiction import load_jurisdiction
from app.llm.local_extract import extract_local
from app.schemas.domain import DispatchBundle, DocumentType

ROOT = Path(__file__).parents[1]


def fixture_bundle(folder: str) -> DispatchBundle:
    bundle = DispatchBundle()
    for path in sorted((ROOT / "fixtures" / folder).glob("*.pdf")):
        item = extract_local(path)
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
    return bundle


@pytest.fixture
def chile_cfg():
    return load_jurisdiction(ROOT / "jurisdictions" / "chile.yaml").config


@pytest.fixture
def falabella_cfg():
    return load_client_profile(ROOT / "clients" / "falabella.yaml").config


@pytest.fixture
def scenario_a():
    return fixture_bundle("scenario_A_clean")


@pytest.fixture
def scenario_b():
    return fixture_bundle("scenario_B_exceptions")


@pytest.fixture
def scenario_c():
    return fixture_bundle("scenario_C_volume")


@pytest.fixture
def scenario_d():
    return fixture_bundle("scenario_D_cif")


@pytest.fixture
def demo_fx():
    return Decimal("963.45"), "dólar aduanero mensual ficticio del demo", date(2026, 8, 1)
