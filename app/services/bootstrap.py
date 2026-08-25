import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ClientConfigVersion, CustomsFxRate, JurisdictionConfigVersion, Org
from app.engine.client import load_client_profile
from app.engine.jurisdiction import load_jurisdiction


@dataclass(frozen=True)
class DemoConfigPins:
    jurisdiction: JurisdictionConfigVersion
    client: ClientConfigVersion
    fx_rate: CustomsFxRate


def ensure_demo_records(db: Session, settings: Settings) -> DemoConfigPins:
    org_id = uuid.UUID(settings.demo_org_id)
    if not db.get(Org, org_id):
        db.add(Org(id=org_id, name="Organización Demo", slug="demo"))
    loaded = load_jurisdiction(settings.jurisdiction_root / "chile.yaml")
    jurisdiction_version = db.scalar(
        select(JurisdictionConfigVersion).where(
            JurisdictionConfigVersion.content_hash == loaded.content_hash
        )
    )
    if not jurisdiction_version:
        jurisdiction_version = JurisdictionConfigVersion(
            jurisdiction="CL", content_hash=loaded.content_hash, content=loaded.raw
        )
        db.add(jurisdiction_version)
    client = load_client_profile(settings.client_root / "falabella.yaml")
    client_version = db.scalar(
        select(ClientConfigVersion).where(ClientConfigVersion.content_hash == client.content_hash)
    )
    if not client_version:
        client_version = ClientConfigVersion(
            client=client.config.client,
            jurisdiction=client.config.jurisdiction,
            effective_from=client.config.insurance.effective_from,
            content_hash=client.content_hash,
            content=client.raw,
        )
        db.add(client_version)
    rate_date = date.fromisoformat(settings.demo_fx_date)
    fx_rate = db.scalar(
        select(CustomsFxRate).where(
            CustomsFxRate.org_id == org_id,
            CustomsFxRate.base_currency == loaded.config.fx.quote_currency,
            CustomsFxRate.quote_currency == loaded.config.currency,
            CustomsFxRate.year == rate_date.year,
            CustomsFxRate.month == rate_date.month,
        )
    )
    if not fx_rate:
        fx_rate = CustomsFxRate(
            org_id=org_id,
            base_currency=loaded.config.fx.quote_currency,
            quote_currency=loaded.config.currency,
            year=rate_date.year,
            month=rate_date.month,
            rate=Decimal(settings.demo_fx_rate),
            source=settings.demo_fx_source,
        )
        db.add(fx_rate)
    db.commit()
    db.refresh(jurisdiction_version)
    db.refresh(client_version)
    db.refresh(fx_rate)
    return DemoConfigPins(jurisdiction=jurisdiction_version, client=client_version, fx_rate=fx_rate)
