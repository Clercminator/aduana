from app.engine.reconcile import reconcile


def test_volume_scenario_has_45_documents_and_all_controls_pass(
    scenario_c, chile_cfg, falabella_cfg, demo_fx
):
    assert len(scenario_c.invoices) == 40
    assert len(scenario_c.instruction.invoice_numbers) == 40
    assert len(scenario_c.bill_of_lading.invoice_numbers_cited) == 40
    assert len(scenario_c.packing_list.lines) == 40
    assert len(scenario_c.insurance.invoices_covered) == 40
    assert len(scenario_c.certificate_of_origin.items) == 40

    result = reconcile(scenario_c, chile_cfg, falabella_cfg, *demo_fx)

    assert all(rule["status"] == "PASS" for rule in result["rules"])
    assert result["totals"]["fob"] == "491220.00"
    assert result["totals"]["insurance"] == "266.22"
    assert result["totals"]["total_payable"] == "95253.87"
