from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.engine.jurisdiction import FXConfig
from app.engine.money import round_money
from app.schemas.domain import Money


class FXConversion(BaseModel):
    source_amount: Money
    rate: Decimal
    converted_amount: Money
    source: str
    rate_date: date


def validate_rate_period(rate_date: date, din_acceptance_date: date, cfg: FXConfig) -> None:
    if cfg.granularity == "monthly" and (
        rate_date.year,
        rate_date.month,
    ) != (din_acceptance_date.year, din_acceptance_date.month):
        raise ValueError(
            "FX rate month does not match the DIN acceptance month: "
            f"{rate_date:%Y-%m} != {din_acceptance_date:%Y-%m}"
        )


def convert(
    amount: Money,
    rate: Decimal,
    target_currency: str,
    source: str,
    rate_date: date,
    dp: int,
) -> FXConversion:
    if rate <= 0:
        raise ValueError("FX rate must be positive")
    converted = round_money(Money(amount=amount.amount * rate, currency=target_currency), dp)
    return FXConversion(
        source_amount=amount,
        rate=rate,
        converted_amount=converted,
        source=source,
        rate_date=rate_date,
    )
