"""Regenerate deterministic fixture expectations from the confirmed engine configuration."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.engine.client import load_client_profile
from app.engine.jurisdiction import load_jurisdiction
from app.engine.reconcile import reconcile
from app.llm.local_extract import extract_local
from app.schemas.domain import DispatchBundle, DocumentType

ROOT = Path(__file__).parents[1]


def bundle_from(folder: str) -> DispatchBundle:
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


def scenario(folder: str, description: str) -> dict:
    jurisdiction = load_jurisdiction(ROOT / "jurisdictions" / "chile.yaml")
    client = load_client_profile(ROOT / "clients" / "falabella.yaml")
    bundle = bundle_from(folder)
    result = reconcile(
        bundle,
        jurisdiction.config,
        client.config,
        Decimal("963.45"),
        "dólar aduanero mensual ficticio del demo",
        date(2026, 8, 1),
    )
    instruction = bundle.instruction
    bl = bundle.bill_of_lading
    return {
        "scenario": description,
        "despacho": instruction.despacho_no.value if instruction else None,
        "referencia": instruction.referencia.value if instruction else None,
        "bl": bl.bl_number.value if bl else None,
        "uploaded_files": len(list((ROOT / "fixtures" / folder).glob("*.pdf"))),
        "commercial_invoices": len(bundle.invoices),
        "din_count": len(bundle.invoices),
        "checks": result["rules"],
        "prorrateo": result["lines"],
        "totals": result["totals"],
        "insurance": {
            "source": result.get("insurance_source"),
            "policy": result.get("policy"),
        },
        "views": {
            "declaration": result["totals"].get("declaration_view"),
            "cost": result["totals"].get("cost_view"),
        },
    }


def main() -> None:
    output = {
        "A": scenario("scenario_A_clean", "CLEAN - straight-through, 3 invoices / 3 DIN"),
        "B": scenario("scenario_B_exceptions", "EXCEPTIONS - held for review, 3 invoices / 3 DIN"),
        "C": scenario("scenario_C_volume", "VOLUME - 40 invoices / 40 DIN"),
        "D": scenario("scenario_D_cif", "CIF - normalize to FOB before rebuilding customs value"),
        "_meta": {
            "engine": "jurisdiction and client-config driven",
            "jurisdiction_config": "jurisdictions/chile.yaml",
            "client_config": "clients/falabella.yaml",
            "client_config_hash": load_client_profile(
                ROOT / "clients" / "falabella.yaml"
            ).content_hash,
            "levy_stack": ["AD_VALOREM", "IVA"],
            "recoverable_levies": ["IVA"],
            "valuation_flow": "invoice price -> normalized FOB -> freight + insurance -> customs value",
            "fx": {
                "source": "dolar_aduanero",
                "granularity": "monthly",
                "date_rule": "din_acceptance_month",
                "demo_rate_usd_clp": "963.45",
                "demo_period": "2026-08",
            },
            "open_assumptions": {
                "insurance_coverage_pct": {
                    "value": "1.15",
                    "provenance": "inferred",
                    "status": "pending agency confirmation",
                },
                "insurance_theoretical_rate": {
                    "value": None,
                    "status": "pending agency confirmation",
                },
            },
        },
    }
    (ROOT / "fixtures" / "ANSWER_KEY.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
