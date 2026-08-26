from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class InsuranceMode(StrEnum):
    POLICY_RATE = "policy_rate"
    CERTIFICATE = "certificate"
    THEORETICAL = "theoretical"


class ClientInsuranceConfig(BaseModel):
    mode: InsuranceMode
    coverage_pct: Decimal = Field(gt=0, le=10)
    coverage_pct_provenance: Literal["confirmed", "inferred"]
    policy_rate: Decimal | None = Field(default=None, gt=0, le=1)
    effective_from: date
    note: str | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "ClientInsuranceConfig":
        if self.mode == InsuranceMode.POLICY_RATE and self.policy_rate is None:
            raise ValueError("policy_rate insurance requires policy_rate")
        if self.mode != InsuranceMode.POLICY_RATE and self.policy_rate is not None:
            raise ValueError("policy_rate is only valid in policy_rate mode")
        return self


class ClientAllocationConfig(BaseModel):
    basis: Literal["invoice_value", "gross_weight", "volume"]


class DocumentTemplateConfig(BaseModel):
    id: str = Field(min_length=1)
    parser: Literal["regex-fixture-v1"] = "regex-fixture-v1"
    document_types: list[str] = Field(min_length=1)
    match_any: list[str] = Field(min_length=1)


class ClientExtractionConfig(BaseModel):
    templates: list[DocumentTemplateConfig] = Field(default_factory=list)
    classification_min_confidence: Decimal = Field(default=Decimal("0.90"), ge=0, le=1)
    financial_min_confidence: Decimal = Field(default=Decimal("0.95"), ge=0, le=1)
    review_fields: dict[str, list[str]] = Field(default_factory=dict)


class ClientProfileConfig(BaseModel):
    client: str
    jurisdiction: str
    insurance: ClientInsuranceConfig
    allocation: ClientAllocationConfig
    default_incoterm: str
    transport_document: Literal["direct_bl", "master_bl", "house_bl"]
    extraction: ClientExtractionConfig = Field(default_factory=ClientExtractionConfig)


class LoadedClientProfile(BaseModel):
    config: ClientProfileConfig
    content_hash: str
    raw: dict


def load_client_profile(path: str | Path) -> LoadedClientProfile:
    source = Path(path).read_bytes()
    parsed = yaml.safe_load(source)
    config = ClientProfileConfig.model_validate(parsed)
    return LoadedClientProfile(
        config=config,
        content_hash=hashlib.sha256(source).hexdigest(),
        raw=config.model_dump(mode="json"),
    )
