from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


class AgencyBrandingConfig(BaseModel):
    short_name: str = Field(min_length=2, max_length=40)
    primary_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class AgencyProfileConfig(BaseModel):
    organization_id: uuid.UUID
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=3, max_length=200)
    client_profile: str = Field(pattern=r"^[a-z0-9_-]+\.yaml$")
    client_label: str = Field(min_length=2, max_length=120)
    demo_scenarios: list[Literal["A", "B", "C", "D"]] = Field(default_factory=list)
    branding: AgencyBrandingConfig

    @field_validator("demo_scenarios")
    @classmethod
    def scenarios_are_unique(cls, scenarios: list[str]) -> list[str]:
        if len(scenarios) != len(set(scenarios)):
            raise ValueError("demo_scenarios must be unique")
        return scenarios


class LoadedAgencyProfile(BaseModel):
    config: AgencyProfileConfig
    content_hash: str
    raw: dict


def load_agency_profile(path: str | Path) -> LoadedAgencyProfile:
    source = Path(path).read_bytes()
    parsed = yaml.safe_load(source)
    config = AgencyProfileConfig.model_validate(parsed)
    return LoadedAgencyProfile(
        config=config,
        content_hash=hashlib.sha256(source).hexdigest(),
        raw=config.model_dump(mode="json"),
    )


def load_agency_catalog(root: str | Path) -> list[LoadedAgencyProfile]:
    profiles = [load_agency_profile(path) for path in sorted(Path(root).glob("*.yaml"))]
    if not profiles:
        raise ValueError("agency catalog is empty")
    ids = [item.config.organization_id for item in profiles]
    slugs = [item.config.slug for item in profiles]
    if len(ids) != len(set(ids)) or len(slugs) != len(set(slugs)):
        raise ValueError("agency organization_id and slug must be unique")
    return profiles
