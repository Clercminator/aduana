from datetime import date
from decimal import Decimal

import pytest

from app.engine.duty import duty_rate
from app.engine.fx import convert, validate_rate_period
from app.schemas.domain import Money


def test_duty_is_per_line_and_postdated_certificate_only_flags_risk(scenario_b, chile_cfg):
    coo = scenario_b.certificate_of_origin
    sailing = scenario_b.bill_of_lading.shipped_on_board_date.value
    preferred, reason = duty_rate("9405.20", coo, sailing, chile_cfg)
    general, uncovered_reason = duty_rate("8544.42", coo, sailing, chile_cfg)
    assert preferred == Decimal("0.00")
    assert "EN RIESGO" in reason
    assert general == Decimal("0.06")
    assert "no está cubierto" in uncovered_reason


def test_duty_matches_the_certificate_agreement_instead_of_first_config_entry(
    scenario_a, chile_cfg
):
    chile_cfg.trade_agreements[0].preferential_rate = Decimal("0.03")
    chile_cfg.trade_agreements[1].preferential_rate = Decimal("0.01")
    scenario_a.certificate_of_origin.agreement_name.value = chile_cfg.trade_agreements[1].label
    rate, reason = duty_rate(
        scenario_a.invoices[0].lines[0].hs_code.value,
        scenario_a.certificate_of_origin,
        scenario_a.bill_of_lading.shipped_on_board_date.value,
        chile_cfg,
    )
    assert rate == Decimal("0.01")
    assert chile_cfg.trade_agreements[1].label in reason


def test_duty_matches_a_configured_agreement_alias(scenario_a, chile_cfg):
    scenario_a.certificate_of_origin.agreement_name.value = "CHINA-CHILE FREE TRADE AGREEMENT"
    rate, reason = duty_rate(
        scenario_a.invoices[0].lines[0].hs_code.value,
        scenario_a.certificate_of_origin,
        scenario_a.bill_of_lading.shipped_on_board_date.value,
        chile_cfg,
    )
    assert rate == Decimal("0.00")
    assert chile_cfg.trade_agreements[0].label in reason


def test_fx_uses_half_up_rounding_and_rejects_invalid_rate():
    result = convert(
        Money(amount=Decimal("13719.81"), currency="USD"),
        Decimal("963.45"),
        "CLP",
        "demo",
        date(2026, 8, 18),
        0,
    )
    assert result.converted_amount.amount == Decimal("13218351")
    with pytest.raises(ValueError, match="positive"):
        convert(
            Money(amount=Decimal("1"), currency="USD"), Decimal("0"), "CLP", "demo", date.today(), 0
        )


def test_monthly_customs_fx_must_match_din_acceptance_month(chile_cfg):
    validate_rate_period(date(2026, 8, 1), date(2026, 8, 31), chile_cfg.fx)
    with pytest.raises(ValueError, match="2026-07 != 2026-08"):
        validate_rate_period(date(2026, 7, 1), date(2026, 8, 1), chile_cfg.fx)
