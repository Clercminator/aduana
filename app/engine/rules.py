from __future__ import annotations

from decimal import Decimal
from typing import Callable

from app.engine.client import ClientProfileConfig
from app.engine.jurisdiction import JurisdictionConfig
from app.engine.normalize import normalized_text
from app.engine.valuation import MissingIncludedAmount, normalize_to_fob
from app.schemas.domain import (
    DispatchBundle,
    RuleResult,
    RuleStatus,
    Severity,
)


def _result(
    rule_id: str,
    severity: Severity,
    status: RuleStatus,
    title: str,
    detail: str,
    action: str | None = None,
    refs: list[dict] | None = None,
    impact: dict[str, str] | None = None,
) -> RuleResult:
    return RuleResult(
        id=rule_id,
        severity=severity,
        status=status,
        title=title,
        detail=detail,
        suggested_action=action,
        source_refs=refs or [],
        financial_impact=impact,
    )


def _skip(rule_id: str, severity: Severity, title: str, missing: list[str]) -> RuleResult:
    return _result(rule_id, severity, RuleStatus.SKIPPED, title, f"Falta: {', '.join(missing)}")


def rule_exc_01(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    title = "Peso bruto packing list vs B/L"
    if not bundle.bill_of_lading or not bundle.packing_list:
        return _skip("EXC-01", Severity.CRITICAL, title, ["B/L o packing list"])
    left = bundle.packing_list.gross_weight_kg.value
    right = bundle.bill_of_lading.gross_weight_kg.value
    if left is None or right is None:
        return _skip("EXC-01", Severity.CRITICAL, title, ["peso bruto"])
    difference = abs(left - right)
    pct = difference / right if right else Decimal("1")
    status = RuleStatus.PASS if pct <= cfg.tolerances.weight_pct else RuleStatus.FAIL
    detail = (
        f"Packing list {left:,.1f} kg vs B/L {right:,.1f} kg; diferencia {difference:,.1f} kg "
        f"({pct * 100:.1f}%), tolerancia {cfg.tolerances.weight_pct * 100:.0f}%"
    )
    return _result(
        "EXC-01",
        Severity.CRITICAL,
        status,
        title,
        detail,
        "Solicitar B/L corregido o confirmación escrita del transportista."
        if status == RuleStatus.FAIL
        else None,
        [
            {"document": "packing_list", "field": "gross_weight_kg"},
            {"document": "bill_of_lading", "field": "gross_weight_kg"},
        ],
    )


def rule_exc_02(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Facturas citadas en B/L"
    if not bundle.bill_of_lading or not bundle.invoices:
        return _skip("EXC-02", Severity.CRITICAL, title, ["B/L o facturas"])
    cited = {item.value for item in bundle.bill_of_lading.invoice_numbers_cited if item.value}
    present = {item.invoice_number.value for item in bundle.invoices if item.invoice_number.value}
    missing = sorted(cited - present)
    extra = sorted(present - cited)
    status = RuleStatus.PASS if not missing and not extra else RuleStatus.FAIL
    detail = (
        "Todas las facturas coinciden"
        if status == RuleStatus.PASS
        else f"Faltan {missing or 'ninguna'}; no citadas {extra or 'ninguna'}"
    )
    return _result(
        "EXC-02",
        Severity.CRITICAL,
        status,
        title,
        detail,
        "Confirmar numeración y corregir B/L o factura." if status == RuleStatus.FAIL else None,
        [
            {"document": "bill_of_lading", "field": "invoice_numbers_cited"},
            {"document": "commercial_invoice", "field": "invoice_number"},
        ],
    )


def rule_exc_03(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Cobertura de códigos HS por certificado de origen"
    if not bundle.certificate_of_origin or not bundle.invoices:
        return _skip("EXC-03", Severity.CRITICAL, title, ["certificado de origen o facturas"])
    covered = {
        item.hs_code.value for item in bundle.certificate_of_origin.items if item.hs_code.value
    }
    invoice_codes = {
        line.hs_code.value
        for invoice in bundle.invoices
        for line in invoice.lines
        if line.hs_code.value
    }
    uncovered = sorted(invoice_codes - covered)
    status = RuleStatus.PASS if not uncovered else RuleStatus.FAIL
    detail = (
        "Todos los códigos HS están cubiertos"
        if status == RuleStatus.PASS
        else f"Códigos sin cobertura: {', '.join(uncovered)}"
    )
    return _result(
        "EXC-03",
        Severity.CRITICAL,
        status,
        title,
        detail,
        "Aplicar tasa general a las líneas no cubiertas o solicitar certificado enmendado."
        if status == RuleStatus.FAIL
        else None,
        [
            {"document": "commercial_invoice", "field": "lines[].hs_code"},
            {"document": "certificate_of_origin", "field": "items[].hs_code"},
        ],
    )


def rule_exc_04(
    bundle: DispatchBundle, cfg: JurisdictionConfig, client_cfg: ClientProfileConfig
) -> RuleResult:
    title = "Suma asegurada mínima"
    if not bundle.insurance or not bundle.bill_of_lading or not bundle.invoices:
        return _skip("EXC-04", Severity.WARNING, title, ["seguro, B/L o facturas"])
    insured = bundle.insurance.sum_insured.value
    freight = bundle.bill_of_lading.freight_amount.value
    if insured is None or freight is None:
        return _skip("EXC-04", Severity.WARNING, title, ["suma asegurada, flete o FOB"])
    try:
        total_fob = sum(
            (normalize_to_fob(invoice, cfg).amount for invoice in bundle.invoices), Decimal("0")
        )
    except (MissingIncludedAmount, ValueError):
        return _skip("EXC-04", Severity.WARNING, title, ["FOB normalizado"])
    cfr = total_fob + freight
    required = (cfr * client_cfg.insurance.coverage_pct).quantize(Decimal("0.01"))
    shortfall = max(required - insured, Decimal("0"))
    status = RuleStatus.PASS if shortfall == 0 else RuleStatus.FAIL
    currency = (
        bundle.insurance.currency.value or bundle.bill_of_lading.freight_currency.value or "?"
    )
    detail = (
        f"Asegurado {currency} {insured:,.2f}; requerido {currency} {required:,.2f}; "
        f"faltante {currency} {shortfall:,.2f}"
    )
    return _result(
        "EXC-04",
        Severity.WARNING,
        status,
        title,
        detail,
        "Solicitar endoso que aumente la suma asegurada." if status == RuleStatus.FAIL else None,
        [
            {"document": "insurance_certificate", "field": "sum_insured"},
            {"document": "bill_of_lading", "field": "freight_amount"},
        ],
    )


def rule_exc_05(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    title = "Aritmética de facturas"
    if not bundle.invoices:
        return _skip("EXC-05", Severity.WARNING, title, ["facturas"])
    issues: list[str] = []
    for invoice in bundle.invoices:
        line_sum = Decimal("0")
        for line in invoice.lines:
            if None in (line.quantity.value, line.unit_price.value, line.line_total.value):
                issues.append(f"{invoice.invoice_number.value}: línea incompleta")
                continue
            calculated = line.quantity.value * line.unit_price.value
            if abs(calculated - line.line_total.value) > cfg.tolerances.money_abs:
                issues.append(
                    f"{invoice.invoice_number.value}: {line.quantity.value} x {line.unit_price.value} = {calculated:.2f}, impreso {line.line_total.value:.2f}"
                )
            line_sum += line.line_total.value
        if (
            invoice.invoice_total.value is not None
            and abs(line_sum - invoice.invoice_total.value) > cfg.tolerances.money_abs
        ):
            issues.append(
                f"{invoice.invoice_number.value}: líneas {line_sum:.2f} vs total {invoice.invoice_total.value:.2f}"
            )
    status = RuleStatus.PASS if not issues else RuleStatus.FAIL
    return _result(
        "EXC-05",
        Severity.WARNING,
        status,
        title,
        "Todas las facturas cuadran" if not issues else "; ".join(issues),
        "Confirmar el valor correcto con el proveedor." if issues else None,
        [{"document": "commercial_invoice", "field": "lines[].quantity/unit_price/line_total"}],
    )


def rule_exc_06(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Consignatario consistente"
    values = []
    if bundle.bill_of_lading:
        values.append(("B/L", bundle.bill_of_lading.consignee_name.value))
    values.extend(
        (invoice.invoice_number.value or "factura", invoice.consignee_name.value)
        for invoice in bundle.invoices
    )
    if bundle.insurance:
        values.append(("seguro", bundle.insurance.assured_name.value))
    if bundle.certificate_of_origin:
        values.append(("CoO", bundle.certificate_of_origin.importer_name.value))
    if len(values) < 2:
        return _skip("EXC-06", Severity.WARNING, title, ["dos documentos con consignatario"])
    distinct = {normalized_text(value) for _, value in values if value}
    status = RuleStatus.PASS if len(distinct) == 1 else RuleStatus.FAIL
    detail = "; ".join(f"{source}: {value}" for source, value in values)
    return _result(
        "EXC-06",
        Severity.WARNING,
        status,
        title,
        detail,
        "Confirmar la entidad importadora y corregir los documentos."
        if status == RuleStatus.FAIL
        else None,
        [
            {"document": source, "field": "consignee_name", "value": value}
            for source, value in values
        ],
    )


def rule_exc_07(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Fecha del certificado de origen"
    if not bundle.certificate_of_origin or not bundle.bill_of_lading:
        return _skip("EXC-07", Severity.WARNING, title, ["CoO o B/L"])
    issue = bundle.certificate_of_origin.issue_date.value
    sailing = bundle.bill_of_lading.shipped_on_board_date.value
    if issue is None or sailing is None:
        return _skip("EXC-07", Severity.WARNING, title, ["fecha de emisión o embarque"])
    risky = issue > sailing and not bool(bundle.certificate_of_origin.is_retrospective.value)
    status = RuleStatus.FAIL if risky else RuleStatus.PASS
    detail = f"Certificado {issue.isoformat()}; embarque {sailing.isoformat()}; retrospectivo: {bool(bundle.certificate_of_origin.is_retrospective.value)}"
    return _result(
        "EXC-07",
        Severity.WARNING,
        status,
        title,
        detail,
        "Solicitar certificado con anotación retrospectiva." if risky else None,
        [
            {"document": "certificate_of_origin", "field": "issue_date/is_retrospective"},
            {"document": "bill_of_lading", "field": "shipped_on_board_date"},
        ],
    )


def rule_exc_08(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Contenedor consistente"
    docs = []
    if bundle.bill_of_lading:
        docs.append(("B/L", bundle.bill_of_lading.container_number.value))
    if bundle.packing_list:
        docs.append(("packing list", bundle.packing_list.container_number.value))
    if bundle.certificate_of_origin:
        docs.append(("CoO", bundle.certificate_of_origin.container_number.value))
    if len(docs) < 2:
        return _skip("EXC-08", Severity.WARNING, title, ["dos documentos con contenedor"])
    values = {normalized_text(value) for _, value in docs if value}
    status = RuleStatus.PASS if len(values) == 1 else RuleStatus.FAIL
    return _result(
        "EXC-08",
        Severity.WARNING,
        status,
        title,
        "; ".join(f"{d}: {v}" for d, v in docs),
        refs=[{"document": d, "field": "container_number"} for d, _ in docs],
    )


def rule_exc_09(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Moneda única de facturas"
    if not bundle.invoices:
        return _skip("EXC-09", Severity.WARNING, title, ["facturas"])
    currencies = sorted(
        {invoice.currency.value for invoice in bundle.invoices if invoice.currency.value}
    )
    missing = sum(invoice.currency.value is None for invoice in bundle.invoices)
    status = RuleStatus.PASS if len(currencies) == 1 and missing == 0 else RuleStatus.FAIL
    return _result(
        "EXC-09",
        Severity.WARNING,
        status,
        title,
        f"Monedas: {', '.join(currencies) or 'sin dato'}; sin moneda: {missing}",
    )


def rule_chk_10(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    del cfg
    title = "Cantidad de bultos"
    if not bundle.bill_of_lading or not bundle.packing_list:
        return _skip("CHK-10", Severity.INFO, title, ["B/L o packing list"])
    left, right = bundle.packing_list.package_count.value, bundle.bill_of_lading.package_count.value
    status = RuleStatus.PASS if left == right else RuleStatus.FAIL
    return _result("CHK-10", Severity.INFO, status, title, f"Packing list {left}; B/L {right}")


def rule_chk_11(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    title = "Flete B/L vs instrucción"
    if not bundle.bill_of_lading or not bundle.instruction:
        return _skip("CHK-11", Severity.INFO, title, ["B/L o instrucción"])
    left, right = (
        bundle.bill_of_lading.freight_amount.value,
        bundle.instruction.freight_amount.value,
    )
    if left is None or right is None:
        return _skip("CHK-11", Severity.INFO, title, ["flete"])
    left_currency = bundle.bill_of_lading.freight_currency.value
    right_currency = bundle.instruction.freight_currency.value
    same_currency = bool(left_currency and right_currency and left_currency == right_currency)
    status = (
        RuleStatus.PASS
        if same_currency and abs(left - right) <= cfg.tolerances.money_abs
        else RuleStatus.FAIL
    )
    return _result(
        "CHK-11",
        Severity.INFO,
        status,
        title,
        f"B/L {left_currency or '?'} {left:,.2f}; instrucción {right_currency or '?'} {right:,.2f}",
    )


def rule_exc_12(bundle: DispatchBundle, cfg: JurisdictionConfig) -> RuleResult:
    title = "Valor total de facturas vs B/L"
    if not bundle.bill_of_lading or not bundle.invoices:
        return _skip("EXC-12", Severity.CRITICAL, title, ["B/L o facturas"])
    declared = bundle.bill_of_lading.declared_value_total.value
    if declared is None:
        return _skip("EXC-12", Severity.CRITICAL, title, ["valor total declarado en B/L"])
    invoice_values = [invoice.invoice_total.value for invoice in bundle.invoices]
    if any(value is None for value in invoice_values):
        return _skip("EXC-12", Severity.CRITICAL, title, ["total de una o más facturas"])
    invoice_total = sum((value for value in invoice_values if value is not None), Decimal("0"))
    currencies = {invoice.currency.value for invoice in bundle.invoices if invoice.currency.value}
    currency = next(iter(currencies)) if len(currencies) == 1 else "?"
    bl_currency = bundle.bill_of_lading.freight_currency.value
    same_currency = bool(bl_currency and currency != "?" and bl_currency == currency)
    difference = abs(invoice_total - declared)
    status = (
        RuleStatus.PASS
        if same_currency and difference <= cfg.tolerances.money_abs
        else RuleStatus.FAIL
    )
    return _result(
        "EXC-12",
        Severity.CRITICAL,
        status,
        title,
        (
            f"Facturas {currency} {invoice_total:,.2f}; B/L {bl_currency or '?'} {declared:,.2f}; "
            f"diferencia {currency} {difference:,.2f}"
        ),
        "Detener la presentación y confirmar si falta una factura o si el B/L está incorrecto."
        if status == RuleStatus.FAIL
        else None,
        [
            {"document": "commercial_invoice", "field": "invoice_total"},
            {"document": "bill_of_lading", "field": "declared_value_total"},
        ],
    )


RULES: list[Callable[[DispatchBundle, JurisdictionConfig], RuleResult]] = [
    rule_exc_01,
    rule_exc_02,
    rule_exc_03,
    rule_exc_05,
    rule_exc_06,
    rule_exc_07,
    rule_exc_08,
    rule_exc_09,
    rule_chk_10,
    rule_chk_11,
    rule_exc_12,
]


def run_rules(
    bundle: DispatchBundle, cfg: JurisdictionConfig, client_cfg: ClientProfileConfig
) -> list[RuleResult]:
    results = [rule(bundle, cfg) for rule in RULES]
    results.insert(3, rule_exc_04(bundle, cfg, client_cfg))
    return results
