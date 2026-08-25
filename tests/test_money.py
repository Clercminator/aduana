from decimal import Decimal

import pytest

from app.schemas.domain import Money


def test_money_preserves_currency_and_exact_decimal():
    total = Money(amount=Decimal("10.10"), currency="usd") + Money(
        amount=Decimal("0.20"), currency="USD"
    )
    assert total.amount == Decimal("10.30")
    assert total.currency == "USD"


def test_mixed_currency_addition_raises():
    with pytest.raises(ValueError, match="currency mismatch"):
        Money(amount=Decimal("1"), currency="USD") + Money(amount=Decimal("1"), currency="CLP")
