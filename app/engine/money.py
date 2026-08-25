from decimal import ROUND_HALF_UP, Decimal

from app.schemas.domain import Money


def quantizer(dp: int) -> Decimal:
    return Decimal("1").scaleb(-dp)


def round_money(money: Money, dp: int) -> Money:
    return Money(
        amount=money.amount.quantize(quantizer(dp), rounding=ROUND_HALF_UP), currency=money.currency
    )


def assert_same_currency(values: list[Money]) -> str:
    if not values:
        raise ValueError("at least one monetary value is required")
    currencies = {value.currency for value in values}
    if len(currencies) != 1:
        raise ValueError(f"mixed currencies are not allocable: {sorted(currencies)}")
    return values[0].currency
