from decimal import Decimal

from app.engine.jurisdiction import JurisdictionConfig
from app.schemas.domain import AllocationResult, CommercialInvoice, Money


class MissingIncludedAmount(ValueError):
    def __init__(self, invoice_number: str, incoterm: str, component: str):
        self.invoice_number = invoice_number
        self.incoterm = incoterm
        self.component = component
        super().__init__(f"{invoice_number}: {incoterm} requiere monto incluido de {component}")


class MissingRequiredValue(ValueError):
    pass


def normalize_to_fob(invoice: CommercialInvoice, cfg: JurisdictionConfig) -> Money:
    """Normalize the printed invoice price to FOB before customs valuation."""
    invoice_number = invoice.invoice_number.value or "sin número"
    currency = invoice.currency.value
    if not currency:
        raise MissingRequiredValue(f"{invoice_number}: missing invoice currency")
    if invoice.invoice_total.value is None:
        raise MissingRequiredValue(f"{invoice_number}: missing invoice total")
    if invoice.invoice_total.value <= 0:
        raise MissingRequiredValue(f"{invoice_number}: invoice total must be positive")
    incoterm = (invoice.incoterm.value or "").strip().upper().split(maxsplit=1)[0]
    if incoterm not in cfg.incoterm_rules:
        raise ValueError(f"unsupported incoterm: {incoterm or 'missing'}")
    fob = Money(amount=invoice.invoice_total.value, currency=currency)
    for component in cfg.incoterm_rules[incoterm].deduct:
        included = invoice.included_amounts.get(component)
        if included is None or included.value is None:
            raise MissingIncludedAmount(invoice_number, incoterm, component)
        if included.value < 0:
            raise MissingRequiredValue(
                f"{invoice_number}: included {component} amount cannot be negative"
            )
        fob -= Money(amount=included.value, currency=currency)
    if fob.amount <= 0:
        raise MissingRequiredValue(f"{invoice_number}: normalized FOB must be positive")
    return fob


def customs_value(fob: Money, allocation: AllocationResult, cfg: JurisdictionConfig) -> Money:
    amount = fob.amount
    for component in cfg.valuation.components:
        if component == "fob":
            continue
        allocated = allocation.amounts.get(component)
        if allocated is not None:
            if allocated.currency != fob.currency:
                raise ValueError("valuation currency mismatch")
            amount += allocated.amount
    return Money(amount=amount, currency=fob.currency)


def landed_cost(
    fob: Money, allocation: AllocationResult, nonrecoverable_levies: list[Money]
) -> Money:
    total = fob
    for allocated in allocation.amounts.values():
        total = total + allocated
    for levy in nonrecoverable_levies:
        total = total + levy
    return Money(amount=total.amount.quantize(Decimal("0.01")), currency=total.currency)
