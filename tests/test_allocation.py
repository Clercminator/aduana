from decimal import Decimal

import pytest

from app.engine.allocation import allocate
from app.schemas.domain import AllocationInput, CostLine, Money


def test_printed_premium_is_fully_allocated_with_residual(chile_cfg):
    invoices = [
        AllocationInput(key="1", basis=Money(amount=Decimal("18600"), currency="USD")),
        AllocationInput(key="2", basis=Money(amount=Decimal("24400"), currency="USD")),
        AllocationInput(key="3", basis=Money(amount=Decimal("12000"), currency="USD")),
    ]
    results = allocate(
        invoices,
        [
            CostLine(
                code="insurance",
                amount=Money(amount=Decimal("38.66"), currency="USD"),
                dutiable=True,
                source="certificate",
            )
        ],
        chile_cfg,
    )
    assert [item.amounts["insurance"].amount for item in results] == [
        Decimal("13.07"),
        Decimal("17.16"),
        Decimal("8.43"),
    ]
    assert sum(item.amounts["insurance"].amount for item in results) == Decimal("38.66")
    assert results[1].residual_codes == ["insurance"]


def test_mixed_currency_allocation_raises(chile_cfg):
    with pytest.raises(ValueError, match="mixed currencies"):
        allocate(
            [
                AllocationInput(key="usd", basis=Money(amount=Decimal("1"), currency="USD")),
                AllocationInput(key="eur", basis=Money(amount=Decimal("1"), currency="EUR")),
            ],
            [],
            chile_cfg,
        )
