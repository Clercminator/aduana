from copy import deepcopy
from decimal import Decimal

from app.adapters.cl_din import din_payload
from app.engine.reconcile import reconcile


def test_scenario_a_exact_totals_and_all_rules_pass(scenario_a, chile_cfg, falabella_cfg, demo_fx):
    result = reconcile(scenario_a, chile_cfg, falabella_cfg, *demo_fx)
    assert result["totals"]["insurance"] == "30.93"
    assert result["totals"]["customs_value"] == "58230.93"
    assert result["totals"]["total_payable"] == "11063.88"
    assert result["totals"]["landed_cost"] == "58230.93"
    assert result["totals"]["recoverable_levies"] == {"IVA": "11063.88"}
    assert result["totals"]["total_payable_settlement"] == "10659495"
    assert result["policy"]["global_premium_reference"] == "30.92"
    assert result["policy"]["rounding_difference"] == "0.01"
    assert len(result["rules"]) == 12
    assert all(item["status"] == "PASS" for item in result["rules"])


def test_scenario_b_exact_totals_and_exception_mix(scenario_b, chile_cfg, falabella_cfg, demo_fx):
    result = reconcile(scenario_b, chile_cfg, falabella_cfg, *demo_fx)
    assert result["totals"]["insurance"] == "36.41"
    assert result["totals"]["customs_value"] == "68556.41"
    assert result["totals"]["levies"] == {"AD_VALOREM": "582.79", "IVA": "13136.46"}
    assert result["totals"]["total_payable"] == "13719.25"
    assert result["totals"]["landed_cost"] == "69139.20"
    assert result["totals"]["total_payable_settlement"] == "13217811"
    failures = [item for item in result["rules"] if item["status"] == "FAIL"]
    assert [item["id"] for item in failures] == [
        "EXC-01",
        "EXC-02",
        "EXC-03",
        "EXC-04",
        "EXC-05",
        "EXC-06",
        "EXC-07",
    ]
    assert sum(item["severity"] == "CRITICAL" for item in failures) == 3
    assert sum(item["severity"] == "WARNING" for item in failures) == 4
    assert result["scenarios"]["blanket_preference"]["total"] == "13025.72"
    assert result["scenarios"]["preference_rejected"]["total"] == "17920.64"


def test_postdated_certificate_does_not_change_preference_rate(
    scenario_b, chile_cfg, falabella_cfg, demo_fx
):
    result = reconcile(scenario_b, chile_cfg, falabella_cfg, *demo_fx)
    first = result["lines"][0]
    assert Decimal(first["duty_rate"]) == Decimal("0")
    assert "EN RIESGO" in first["duty_reason"]


def test_policy_rate_ignores_printed_premium(scenario_a, chile_cfg, falabella_cfg, demo_fx):
    assert scenario_a.insurance.premium.value == Decimal("30.92")
    result = reconcile(scenario_a, chile_cfg, falabella_cfg, *demo_fx)
    assert result["insurance_source"] == "client_policy_rate"
    assert result["totals"]["insurance"] == "30.93"


def test_certificate_mode_never_estimates_missing_premium(
    scenario_a, chile_cfg, falabella_cfg, demo_fx
):
    certificate_profile = falabella_cfg.model_copy(deep=True)
    certificate_profile.insurance.mode = "certificate"
    certificate_profile.insurance.policy_rate = None
    scenario_a.insurance = None
    result = reconcile(scenario_a, chile_cfg, certificate_profile, *demo_fx)
    assert result["totals"] == {}
    assert result["rules"][-1]["id"] == "VAL-02"
    assert result["rules"][-1]["severity"] == "CRITICAL"


def test_exc_12_blocks_invoice_total_mismatch(scenario_a, chile_cfg, falabella_cfg, demo_fx):
    scenario_a.bill_of_lading.declared_value_total.value = Decimal("54000.00")
    result = reconcile(scenario_a, chile_cfg, falabella_cfg, *demo_fx)
    exc_12 = next(rule for rule in result["rules"] if rule["id"] == "EXC-12")
    assert exc_12["status"] == "FAIL"
    assert exc_12["severity"] == "CRITICAL"
    assert "1,000.00" in exc_12["detail"]


def test_cif_scenario_matches_equivalent_fob_valuation(
    scenario_d, chile_cfg, falabella_cfg, demo_fx
):
    result = reconcile(scenario_d, chile_cfg, falabella_cfg, *demo_fx)
    assert result["totals"]["fob"] == "12000.00"
    assert result["totals"]["freight"] == "1200.00"
    assert result["totals"]["insurance"] == "7.01"
    assert result["totals"]["customs_value"] == "13207.01"
    assert all(rule["status"] == "PASS" for rule in result["rules"])


def test_multiline_invoice_reconciles_without_repeating_invoice_amounts(
    scenario_a, chile_cfg, falabella_cfg, demo_fx
):
    baseline = reconcile(deepcopy(scenario_a), chile_cfg, falabella_cfg, *demo_fx)
    invoice = scenario_a.invoices[0]
    original = invoice.lines[0]
    first = original.model_copy(deep=True)
    second = original.model_copy(deep=True)
    for line in (first, second):
        line.quantity.value = original.quantity.value / 2
        line.line_total.value = original.line_total.value / 2
    invoice.lines = [first, second]

    result = reconcile(scenario_a, chile_cfg, falabella_cfg, *demo_fx)

    assert result["totals"] == baseline["totals"]
    assert len(result["lines"]) == 4
    assert sum(
        Decimal(line["customs_value"])
        for line in result["lines"]
        if line["invoice"] == invoice.invoice_number.value
    ) == Decimal("19692.64")
    state = {
        "dispatch": {"jurisdiction": "CL", "regime": "import_for_consumption"},
        "calculation": result,
    }
    assert len(din_payload(state)) == 3


def test_missing_required_financial_values_block_calculation(
    scenario_a, chile_cfg, falabella_cfg, demo_fx
):
    cases = [
        ("invoice total", lambda bundle: setattr(bundle.invoices[0].invoice_total, "value", None)),
        ("invoice currency", lambda bundle: setattr(bundle.invoices[0].currency, "value", None)),
        (
            "B/L freight",
            lambda bundle: setattr(bundle.bill_of_lading.freight_amount, "value", None),
        ),
        (
            "B/L freight currency",
            lambda bundle: setattr(bundle.bill_of_lading.freight_currency, "value", None),
        ),
        (
            "line total",
            lambda bundle: setattr(bundle.invoices[0].lines[0].line_total, "value", None),
        ),
    ]
    for expected_detail, mutate in cases:
        bundle = deepcopy(scenario_a)
        mutate(bundle)
        result = reconcile(bundle, chile_cfg, falabella_cfg, *demo_fx)
        assert result["totals"] == {}
        error = next(rule for rule in result["rules"] if rule["id"] == "VAL-03")
        assert error["status"] == "FAIL"
        assert expected_detail in error["detail"]
