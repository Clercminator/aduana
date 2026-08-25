from decimal import Decimal

from app.engine.jurisdiction import JurisdictionConfig
from app.engine.money import assert_same_currency, round_money
from app.schemas.domain import AllocationInput, AllocationResult, CostLine, Money


def allocate(
    invoices: list[AllocationInput], cost_lines: list[CostLine], cfg: JurisdictionConfig
) -> list[AllocationResult]:
    if not invoices:
        return []
    currency = assert_same_currency([invoice.basis for invoice in invoices])
    assert_same_currency(
        [line.amount for line in cost_lines] + [Money(amount=Decimal("0"), currency=currency)]
    )
    total_basis = sum((item.basis.amount for item in invoices), Decimal("0"))
    if total_basis <= 0:
        raise ValueError("allocation basis must be positive")
    shares = [item.basis.amount / total_basis for item in invoices]
    largest_index = max(range(len(invoices)), key=lambda index: invoices[index].basis.amount)
    by_key = [
        AllocationResult(key=item.key, share=share, amounts={})
        for item, share in zip(invoices, shares)
    ]

    for cost in cost_lines:
        allocated = [round_money(cost.amount * share, 2) for share in shares]
        residual = cost.amount.amount - sum((item.amount for item in allocated), Decimal("0"))
        if residual:
            current = allocated[largest_index]
            allocated[largest_index] = Money(
                amount=current.amount + residual, currency=current.currency
            )
            by_key[largest_index].residual_codes.append(cost.code)
        if sum((item.amount for item in allocated), Decimal("0")) != cost.amount.amount:
            raise AssertionError(f"allocation for {cost.code} does not reconcile")
        for result, amount in zip(by_key, allocated):
            result.amounts[cost.code] = amount
    return by_key
