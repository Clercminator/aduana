from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class RoundingConfig(BaseModel):
    dp: int = Field(ge=0, le=8)
    mode: Literal["half_up"] = "half_up"


class ValuationConfig(BaseModel):
    base_name: str
    components: list[str]


class CostLineConfig(BaseModel):
    code: str
    label: str
    dutiable: bool
    source: str


class AllocationConfig(BaseModel):
    basis: Literal["invoice_value", "gross_weight", "volume"]
    residual_to: Literal["largest_line"]
    cost_lines: list[CostLineConfig]


class InsuranceTheoreticalConfig(BaseModel):
    rate: Decimal | None = Field(default=None, gt=0, le=1)


class IncotermRuleConfig(BaseModel):
    deduct: list[Literal["freight", "insurance", "duties"]]


class FXConfig(BaseModel):
    quote_currency: str
    source: str
    granularity: Literal["daily", "monthly"]
    date_rule: Literal["din_acceptance_month", "declaration_date", "bl_date", "arrival_date"]
    rounding: RoundingConfig


class RateConfig(BaseModel):
    type: Literal["flat", "hs_lookup"]
    value: Decimal | None = Field(default=None, ge=0, le=1)
    default: Decimal | None = Field(default=None, ge=0, le=1)
    preference_capable: bool = False

    @model_validator(mode="after")
    def validate_rate_fields(self) -> "RateConfig":
        if self.type == "flat" and self.value is None:
            raise ValueError("flat rate requires value")
        if self.type == "hs_lookup" and self.default is None:
            raise ValueError("hs_lookup rate requires default")
        return self


class LevyConfig(BaseModel):
    code: str
    label: str
    base: str
    rate: RateConfig
    rounding: RoundingConfig
    recoverable: bool = False


class ToleranceConfig(BaseModel):
    weight_pct: Decimal = Field(ge=0, le=1)
    money_abs: Decimal = Field(ge=0)


class TradeAgreementConfig(BaseModel):
    code: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    form: str
    origin_countries: list[str]
    preferential_rate: Decimal = Field(ge=0, le=1)


class DeclarationConfig(BaseModel):
    code: str
    name: str
    authority: str
    adapter: str


class JurisdictionConfig(BaseModel):
    code: str
    name: str
    currency: str
    declaration: DeclarationConfig
    valuation: ValuationConfig
    allocation: AllocationConfig
    incoterm_rules: dict[str, IncotermRuleConfig]
    insurance_theoretical: InsuranceTheoreticalConfig
    fx: FXConfig
    levies: list[LevyConfig]
    tolerances: ToleranceConfig
    trade_agreements: list[TradeAgreementConfig]


class LoadedJurisdiction(BaseModel):
    config: JurisdictionConfig
    content_hash: str
    raw: dict


def load_jurisdiction(path: str | Path) -> LoadedJurisdiction:
    source = Path(path).read_bytes()
    parsed = yaml.safe_load(source)
    config = JurisdictionConfig.model_validate(parsed)
    return LoadedJurisdiction(
        config=config,
        content_hash=hashlib.sha256(source).hexdigest(),
        raw=config.model_dump(mode="json"),
    )
