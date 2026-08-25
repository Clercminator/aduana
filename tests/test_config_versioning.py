import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.engine.agency import load_agency_catalog
from app.engine.client import ClientProfileConfig, load_client_profile
from app.engine.jurisdiction import JurisdictionConfig, load_jurisdiction

ROOT = Path(__file__).parents[1]


def test_config_content_hash_is_deterministic_and_changes_with_content(tmp_path):
    source = ROOT / "jurisdictions" / "chile.yaml"
    first = load_jurisdiction(source)
    copy_path = tmp_path / "chile.yaml"
    copy_path.write_bytes(source.read_bytes())
    assert load_jurisdiction(copy_path).content_hash == first.content_hash
    copy_path.write_text(
        source.read_text(encoding="utf-8") + "\n# nueva versión\n", encoding="utf-8"
    )
    assert load_jurisdiction(copy_path).content_hash != first.content_hash


def test_preferential_rate_is_required_by_schema():
    raw = yaml.safe_load((ROOT / "jurisdictions" / "chile.yaml").read_text(encoding="utf-8"))
    del raw["trade_agreements"][0]["preferential_rate"]
    with pytest.raises(ValidationError):
        JurisdictionConfig.model_validate(raw)


def test_client_profile_is_hashed_and_keeps_inferred_coverage_explicit():
    loaded = load_client_profile(ROOT / "clients" / "falabella.yaml")
    assert loaded.config.client == "FALABELLA_RETAIL"
    assert loaded.config.insurance.policy_rate == Decimal("0.000462")
    assert loaded.config.insurance.coverage_pct == Decimal("1.15")
    assert loaded.config.insurance.coverage_pct_provenance == "inferred"
    assert len(loaded.content_hash) == 64
    json.dumps(loaded.raw)


def test_two_unique_agency_profiles_reference_valid_client_configuration():
    agencies = load_agency_catalog(ROOT / "agencies")
    assert {item.config.slug for item in agencies} == {"imr-demo", "pacifico-demo"}
    assert len({item.config.organization_id for item in agencies}) == 2
    for agency in agencies:
        client = load_client_profile(ROOT / "clients" / agency.config.client_profile)
        assert client.config.jurisdiction == "CL"


def test_jurisdiction_config_rejects_unsafe_fractional_rates():
    raw = yaml.safe_load((ROOT / "jurisdictions" / "chile.yaml").read_text(encoding="utf-8"))
    for path, value in [
        (("levies", 1, "rate", "value"), Decimal("19")),
        (("levies", 0, "rate", "default"), Decimal("-0.01")),
        (("trade_agreements", 0, "preferential_rate"), Decimal("1.01")),
    ]:
        candidate = yaml.safe_load(yaml.safe_dump(raw))
        current = candidate
        for key in path[:-1]:
            current = current[key]
        current[path[-1]] = value
        with pytest.raises(ValidationError):
            JurisdictionConfig.model_validate(candidate)


def test_client_profile_rejects_unsafe_policy_rate():
    raw = yaml.safe_load((ROOT / "clients" / "falabella.yaml").read_text(encoding="utf-8"))
    raw["insurance"]["policy_rate"] = Decimal("4.62")
    with pytest.raises(ValidationError):
        ClientProfileConfig.model_validate(raw)
