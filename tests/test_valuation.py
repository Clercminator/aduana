from decimal import Decimal

import pytest

from app.engine.valuation import MissingIncludedAmount, customs_value, landed_cost, normalize_to_fob
from app.schemas.domain import AllocationResult, Money


def test_valuation_components_and_landed_cost_are_separate(chile_cfg):
    allocation = AllocationResult(
        key="invoice",
        share=Decimal("1"),
        amounts={
            "freight": Money(amount=Decimal("20"), currency="USD"),
            "insurance": Money(amount=Decimal("2"), currency="USD"),
            "storage": Money(amount=Decimal("5"), currency="USD"),
        },
    )
    fob = Money(amount=Decimal("100"), currency="USD")
    assert customs_value(fob, allocation, chile_cfg).amount == Decimal("122")
    fob_only = chile_cfg.model_copy(deep=True)
    fob_only.valuation.components = ["fob"]
    assert customs_value(fob, allocation, fob_only).amount == Decimal("100")
    landed = landed_cost(fob, allocation, [Money(amount=Decimal("23.18"), currency="USD")])
    assert landed.amount == Decimal("150.18")


def test_cif_fixture_normalizes_to_equivalent_fob(scenario_d, chile_cfg):
    invoice = scenario_d.invoices[0]
    assert invoice.invoice_total.value == Decimal("13215.00")
    assert normalize_to_fob(invoice, chile_cfg).amount == Decimal("12000.00")


def test_incoterm_deduction_never_estimates_missing_amount(scenario_d, chile_cfg):
    del scenario_d.invoices[0].included_amounts["insurance"]
    with pytest.raises(MissingIncludedAmount, match="insurance"):
        normalize_to_fob(scenario_d.invoices[0], chile_cfg)
