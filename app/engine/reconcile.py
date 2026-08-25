from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.engine.allocation import allocate
from app.engine.client import ClientProfileConfig, InsuranceMode
from app.engine.duty import duty_rate
from app.engine.fx import convert
from app.engine.jurisdiction import JurisdictionConfig
from app.engine.levies import apply_levies
from app.engine.money import round_money
from app.engine.rules import run_rules
from app.engine.valuation import (
    MissingIncludedAmount,
    MissingRequiredValue,
    customs_value,
    landed_cost,
    normalize_to_fob,
)
from app.schemas.domain import (
    AllocationInput,
    AllocationResult,
    CostLine,
    DispatchBundle,
    Money,
    RuleResult,
    RuleStatus,
    Severity,
)


def _s(value: Decimal) -> str:
    return format(value, "f")


def _input_error(error_id: str, title: str, detail: str, action: str) -> RuleResult:
    return RuleResult(
        id=error_id,
        severity=Severity.CRITICAL,
        status=RuleStatus.FAIL,
        title=title,
        detail=detail,
        suggested_action=action,
    )


def _blocked(rules: list[RuleResult], label: str) -> dict[str, Any]:
    return {
        "label": label,
        "rules": [item.model_dump(mode="json") for item in rules],
        "lines": [],
        "totals": {},
        "scenarios": {},
    }


def _financial_input_error(bundle: DispatchBundle) -> RuleResult | None:
    problems: list[str] = []
    bill_of_lading = bundle.bill_of_lading
    if bill_of_lading:
        freight = bill_of_lading.freight_amount.value
        if freight is None:
            problems.append("missing B/L freight")
        elif freight < 0:
            problems.append("B/L freight cannot be negative")
        if not bill_of_lading.freight_currency.value:
            problems.append("missing B/L freight currency")

    invoice_currencies: set[str] = set()
    for index, invoice in enumerate(bundle.invoices, start=1):
        invoice_number = invoice.invoice_number.value or f"invoice {index}"
        if invoice.invoice_total.value is None:
            problems.append(f"{invoice_number}: missing invoice total")
        elif invoice.invoice_total.value <= 0:
            problems.append(f"{invoice_number}: invoice total must be positive")
        if not invoice.currency.value:
            problems.append(f"{invoice_number}: missing invoice currency")
        else:
            invoice_currencies.add(invoice.currency.value)
        if not invoice.lines:
            problems.append(f"{invoice_number}: missing invoice lines")
        for line_index, line in enumerate(invoice.lines, start=1):
            if line.line_total.value is None:
                problems.append(f"{invoice_number} line {line_index}: missing line total")
            elif line.line_total.value < 0:
                problems.append(
                    f"{invoice_number} line {line_index}: line total cannot be negative"
                )

    if len(invoice_currencies) > 1:
        problems.append(f"mixed invoice currencies: {sorted(invoice_currencies)}")
    freight_currency = bill_of_lading.freight_currency.value if bill_of_lading else None
    if len(invoice_currencies) == 1 and freight_currency:
        invoice_currency = next(iter(invoice_currencies))
        if invoice_currency != freight_currency:
            problems.append(
                f"currency mismatch: invoices {invoice_currency} != B/L freight {freight_currency}"
            )
    if not problems:
        return None
    return _input_error(
        "VAL-03",
        "Datos monetarios requeridos incompletos",
        "; ".join(problems),
        "Detener el cálculo y completar o corregir los valores y monedas documentales.",
    )


def _allocate_invoice_to_lines(
    invoice_number: str,
    invoice,
    invoice_fob: Money,
    invoice_allocation: AllocationResult,
    cfg: JurisdictionConfig,
) -> list[AllocationResult]:
    line_inputs = [
        AllocationInput(
            key=f"{invoice_number}:{index}",
            basis=Money(amount=line.line_total.value, currency=invoice_fob.currency),
        )
        for index, line in enumerate(invoice.lines)
    ]
    cost_lines = [CostLine(code="fob", amount=invoice_fob, dutiable=True, source="invoice")]
    cost_lines.extend(
        CostLine(code=code, amount=amount, dutiable=True, source="invoice_allocation")
        for code, amount in invoice_allocation.amounts.items()
    )
    return allocate(line_inputs, cost_lines, cfg)


def _insurance_allocations(
    bundle: DispatchBundle,
    client_cfg: ClientProfileConfig,
    jurisdiction_cfg: JurisdictionConfig,
    allocation_inputs: list[AllocationInput],
    freight_allocations: list[AllocationResult],
    normalized_fob: dict[str, Money],
    currency: str,
) -> tuple[dict[str, Money], str, dict[str, str]]:
    insurance_cfg = client_cfg.insurance
    mode = insurance_cfg.mode
    if mode == InsuranceMode.CERTIFICATE:
        premium = bundle.insurance.premium.value if bundle.insurance else None
        if premium is None:
            raise ValueError("certificate mode requires a printed insurance premium")
        premium_currency = (
            bundle.insurance.currency.value
            if bundle.insurance and bundle.insurance.currency.value
            else currency
        )
        allocated = allocate(
            allocation_inputs,
            [
                CostLine(
                    code="insurance",
                    amount=Money(amount=premium, currency=premium_currency),
                    dutiable=True,
                    source="insurance_certificate",
                )
            ],
            jurisdiction_cfg,
        )
        return (
            {item.key: item.amounts["insurance"] for item in allocated},
            "insurance_certificate",
            {
                "mode": mode.value,
                "insurance_coverage_pct": _s(insurance_cfg.coverage_pct),
            },
        )

    rate = (
        insurance_cfg.policy_rate
        if mode == InsuranceMode.POLICY_RATE
        else jurisdiction_cfg.insurance_theoretical.rate
    )
    if rate is None:
        raise ValueError(f"{mode.value} insurance requires a configured rate")
    freight_by_invoice = {item.key: item.amounts["freight"] for item in freight_allocations}
    per_invoice: dict[str, Money] = {}
    for item in allocation_inputs:
        cfr = normalized_fob[item.key] + freight_by_invoice[item.key]
        per_invoice[item.key] = round_money(
            Money(amount=cfr.amount * insurance_cfg.coverage_pct * rate, currency=currency),
            2,
        )
    total_cfr = sum(
        (
            normalized_fob[item.key].amount + freight_by_invoice[item.key].amount
            for item in allocation_inputs
        ),
        Decimal("0"),
    )
    global_reference = round_money(
        Money(amount=total_cfr * insurance_cfg.coverage_pct * rate, currency=currency), 2
    ).amount
    line_total = sum((money.amount for money in per_invoice.values()), Decimal("0"))
    source = (
        "client_policy_rate" if mode == InsuranceMode.POLICY_RATE else "jurisdiction_theoretical"
    )
    return (
        per_invoice,
        source,
        {
            "mode": mode.value,
            "insurance_coverage_pct": _s(insurance_cfg.coverage_pct),
            "insurance_rate": _s(rate),
            "effective_from": insurance_cfg.effective_from.isoformat(),
            "global_premium_reference": _s(global_reference),
            "line_premium_total": _s(line_total),
            "rounding_difference": _s(line_total - global_reference),
            "coverage_pct_provenance": insurance_cfg.coverage_pct_provenance,
        },
    )


def reconcile(
    bundle: DispatchBundle,
    cfg: JurisdictionConfig,
    client_cfg: ClientProfileConfig,
    fx_rate: Decimal,
    fx_source: str,
    fx_date: date,
) -> dict[str, Any]:
    if client_cfg.jurisdiction != cfg.code:
        raise ValueError(f"client jurisdiction mismatch: {client_cfg.jurisdiction} != {cfg.code}")
    if client_cfg.allocation.basis != cfg.allocation.basis:
        raise ValueError("client and jurisdiction allocation bases do not match")
    rules = run_rules(bundle, cfg, client_cfg)
    if not bundle.invoices or not bundle.bill_of_lading:
        return _blocked(rules, "según documentos, pendiente de revisión")

    financial_error = _financial_input_error(bundle)
    if financial_error:
        rules.append(financial_error)
        return _blocked(rules, "no calculado: datos monetarios incompletos")

    currencies = {invoice.currency.value for invoice in bundle.invoices}
    if len(currencies) != 1:
        return _blocked(rules, "no calculado: facturas en monedas distintas")
    currency = next(iter(currencies))

    normalized_fob: dict[str, Money] = {}
    for index, invoice in enumerate(bundle.invoices):
        invoice_number = invoice.invoice_number.value or f"invoice-{index}"
        try:
            normalized_fob[invoice_number] = normalize_to_fob(invoice, cfg)
        except (MissingIncludedAmount, MissingRequiredValue) as exc:
            rules.append(
                _input_error(
                    "VAL-01",
                    "Componente incluido requerido por Incoterm",
                    str(exc),
                    "Detener la valoración y capturar el monto desglosado en la factura.",
                )
            )
        except ValueError as exc:
            rules.append(
                _input_error(
                    "VAL-01",
                    "Incoterm no soportado",
                    f"{invoice_number}: {exc}",
                    "Corregir o confirmar el Incoterm antes de valorar.",
                )
            )
    if len(normalized_fob) != len(bundle.invoices):
        return _blocked(rules, "no calculado: falta desglose para normalizar a FOB")

    allocation_inputs = [
        AllocationInput(key=key, basis=value) for key, value in normalized_fob.items()
    ]
    freight = CostLine(
        code="freight",
        amount=Money(
            amount=bundle.bill_of_lading.freight_amount.value or Decimal("0"),
            currency=bundle.bill_of_lading.freight_currency.value or currency,
        ),
        dutiable=True,
        source="bill_of_lading",
    )
    freight_allocations = allocate(allocation_inputs, [freight], cfg)
    try:
        insurance_by_invoice, insurance_source, policy = _insurance_allocations(
            bundle,
            client_cfg,
            cfg,
            allocation_inputs,
            freight_allocations,
            normalized_fob,
            currency,
        )
    except ValueError as exc:
        rules.append(
            _input_error(
                "VAL-02",
                "Seguro no calculable",
                str(exc),
                "Configurar la fuente requerida o capturar la prima impresa; nunca estimar.",
            )
        )
        return _blocked(rules, "no calculado: seguro incompleto")

    allocations: list[AllocationResult] = []
    for item in freight_allocations:
        item.amounts["insurance"] = insurance_by_invoice[item.key]
        allocations.append(item)
    by_invoice = {item.key: item for item in allocations}
    sailing_date = bundle.bill_of_lading.shipped_on_board_date.value
    output_lines: list[dict[str, Any]] = []
    total_fob = Decimal("0")
    total_customs = Decimal("0")
    total_landed = Decimal("0")
    levy_totals: dict[str, Decimal] = {levy.code: Decimal("0") for levy in cfg.levies}
    recoverable_levy_totals: dict[str, Decimal] = {
        levy.code: Decimal("0") for levy in cfg.levies if levy.recoverable
    }
    nonrecoverable_levy_totals: dict[str, Decimal] = {
        levy.code: Decimal("0") for levy in cfg.levies if not levy.recoverable
    }

    for invoice in bundle.invoices:
        invoice_number = invoice.invoice_number.value or "sin número"
        invoice_allocation = by_invoice[invoice_number]
        invoice_fob = normalized_fob[invoice_number]
        line_allocations = _allocate_invoice_to_lines(
            invoice_number, invoice, invoice_fob, invoice_allocation, cfg
        )
        for line, allocated_line in zip(invoice.lines, line_allocations):
            fob = allocated_line.amounts["fob"]
            allocation = AllocationResult(
                key=allocated_line.key,
                share=invoice_allocation.share * allocated_line.share,
                amounts={
                    code: amount for code, amount in allocated_line.amounts.items() if code != "fob"
                },
                residual_codes=list(
                    dict.fromkeys(invoice_allocation.residual_codes + allocated_line.residual_codes)
                ),
            )
            value = customs_value(fob, allocation, cfg)
            total_fob += fob.amount
            total_customs += value.amount
            hs_code = line.hs_code.value or "sin HS"
            rate, reason = duty_rate(hs_code, bundle.certificate_of_origin, sailing_date, cfg)
            levies = apply_levies(value, rate, cfg)
            for levy in levies:
                levy_totals[levy.code] += levy.amount.amount
                target = recoverable_levy_totals if levy.recoverable else nonrecoverable_levy_totals
                target[levy.code] += levy.amount.amount
            nonrecoverable = [levy.amount for levy in levies if not levy.recoverable]
            cost = landed_cost(fob, allocation, nonrecoverable)
            total_landed += cost.amount
            levy_total = sum((levy.amount.amount for levy in levies), Decimal("0"))
            capitalized_levies = sum(
                (levy.amount.amount for levy in levies if not levy.recoverable), Decimal("0")
            )
            output_lines.append(
                {
                    "invoice": invoice_number,
                    "description": line.description.value,
                    "hs_code": hs_code,
                    "quantity": _s(line.quantity.value or Decimal("0")),
                    "uom": line.uom.value,
                    "invoice_total": _s(invoice.invoice_total.value or Decimal("0")),
                    "fob": _s(fob.amount),
                    "share": _s(allocation.share),
                    "allocations": {
                        code: _s(money.amount) for code, money in allocation.amounts.items()
                    },
                    "residual_codes": allocation.residual_codes,
                    "customs_value": _s(value.amount),
                    "duty_rate": _s(rate),
                    "duty_reason": reason,
                    "levies": [levy.model_dump(mode="json") for levy in levies],
                    "levy_total": _s(levy_total),
                    "landed_cost": _s(cost.amount),
                    "declaration_view": {"payable_levies": _s(levy_total)},
                    "cost_view": {
                        "capitalized_levies": _s(capitalized_levies),
                        "recoverable_levies_excluded": _s(levy_total - capitalized_levies),
                        "landed_cost": _s(cost.amount),
                    },
                }
            )

    total_payable = sum(levy_totals.values(), Decimal("0"))
    total_recoverable = sum(recoverable_levy_totals.values(), Decimal("0"))
    total_nonrecoverable = sum(nonrecoverable_levy_totals.values(), Decimal("0"))
    total_insurance = sum(
        (allocation.amounts["insurance"].amount for allocation in allocations), Decimal("0")
    )
    converted = convert(
        Money(amount=total_payable, currency=currency),
        fx_rate,
        cfg.currency,
        fx_source,
        fx_date,
        cfg.fx.rounding.dp,
    )
    total_duty = sum(
        (
            levy_totals.get(levy.code, Decimal("0"))
            for levy in cfg.levies
            if levy.rate.type == "hs_lookup"
        ),
        Decimal("0"),
    )

    for rule in rules:
        if rule.id == "EXC-03" and rule.status == RuleStatus.FAIL:
            general = Decimal("0")
            iva_delta = Decimal("0")
            downstream_rate = next(
                levy.rate.value
                for levy in cfg.levies
                if levy.rate.type == "flat" and levy.rate.value is not None
            )
            for line in output_lines:
                if Decimal(line["duty_rate"]) > 0:
                    duty_amount = Decimal(str(line["levies"][0]["amount"]["amount"]))
                    general += duty_amount
                    iva_delta += (duty_amount * downstream_rate).quantize(Decimal("0.01"))
            rule.financial_impact = {
                "duty_under_declared": _s(general),
                "iva_under_declared": _s(iva_delta),
                "total_under_declared": _s(general + iva_delta),
            }

    scenario_totals = _comparison_scenarios(
        output_lines, cfg, currency, fx_rate, fx_source, fx_date
    )
    return {
        "label": "según documentos, pendiente de revisión",
        "insurance_source": insurance_source,
        "policy": policy,
        "rules": [item.model_dump(mode="json") for item in rules],
        "lines": output_lines,
        "totals": {
            "currency": currency,
            "fob": _s(total_fob),
            "freight": _s(freight.amount.amount),
            "insurance": _s(total_insurance),
            "customs_value": _s(total_customs),
            "levies": {code: _s(amount) for code, amount in levy_totals.items()},
            "recoverable_levies": {
                code: _s(amount) for code, amount in recoverable_levy_totals.items()
            },
            "nonrecoverable_levies": {
                code: _s(amount) for code, amount in nonrecoverable_levy_totals.items()
            },
            "duty": _s(total_duty),
            "total_payable": _s(total_payable),
            "recoverable_total": _s(total_recoverable),
            "capitalized_levy_total": _s(total_nonrecoverable),
            "landed_cost": _s(total_landed),
            "declaration_view": {"total_payable": _s(total_payable)},
            "cost_view": {
                "landed_cost": _s(total_landed),
                "recoverable_levies_excluded": _s(total_recoverable),
            },
            "settlement_currency": cfg.currency,
            "fx_rate": _s(fx_rate),
            "fx_source": fx_source,
            "fx_date": fx_date.isoformat(),
            "fx_period": f"{fx_date:%Y-%m}",
            "total_payable_settlement": _s(converted.converted_amount.amount),
        },
        "scenarios": scenario_totals,
    }


def _comparison_scenarios(
    lines: list[dict[str, Any]],
    cfg: JurisdictionConfig,
    currency: str,
    fx_rate: Decimal,
    fx_source: str,
    fx_date: date,
) -> dict[str, Any]:
    if not lines:
        return {}
    general_rate = next(levy.rate.default for levy in cfg.levies if levy.rate.type == "hs_lookup")
    preference_rate = min(
        (agreement.preferential_rate for agreement in cfg.trade_agreements), default=general_rate
    )
    output: dict[str, Any] = {}
    for name, rate in (
        ("blanket_preference", preference_rate),
        ("preference_rejected", general_rate),
    ):
        scenario_customs_value = sum(
            (Decimal(line["customs_value"]) for line in lines), Decimal("0")
        )
        levies = apply_levies(Money(amount=scenario_customs_value, currency=currency), rate, cfg)
        total = sum((item.amount.amount for item in levies), Decimal("0"))
        converted = convert(
            Money(amount=total, currency=currency),
            fx_rate,
            cfg.currency,
            fx_source,
            fx_date,
            cfg.fx.rounding.dp,
        )
        output[name] = {
            "total": _s(total),
            "settlement_total": _s(converted.converted_amount.amount),
        }
    return output
