import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ClientConfigVersion, CustomsFxRate, JurisdictionConfigVersion, Org
from app.engine.agency import AgencyProfileConfig, load_agency_catalog
from app.engine.client import load_client_profile
from app.engine.jurisdiction import load_jurisdiction


@dataclass(frozen=True)
class DemoConfigPins:
    organization: Org
    agency: AgencyProfileConfig
    jurisdiction: JurisdictionConfigVersion
    client: ClientConfigVersion
    fx_rate: CustomsFxRate


def ensure_demo_records(
    db: Session, settings: Settings, selected_org_id: uuid.UUID | None = None
) -> DemoConfigPins:
    selected_org_id = selected_org_id or uuid.UUID(settings.demo_org_id)
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
    rate_date = date.fromisoformat(settings.demo_fx_date)
    pins: dict[uuid.UUID, DemoConfigPins] = {}
    for loaded_agency in load_agency_catalog(settings.agency_root):
        agency = loaded_agency.config
        org_id = agency.organization_id
        organization = db.get(Org, org_id)
        org_profile = {
            "agency_config_hash": loaded_agency.content_hash,
            "client_label": agency.client_label,
            "branding": agency.branding.model_dump(mode="json"),
        }
        if organization is None:
            organization = Org(id=org_id, name=agency.name, slug=agency.slug, profile=org_profile)
            db.add(organization)
        else:
            organization.name = agency.name
            organization.slug = agency.slug
            organization.profile = org_profile

        client = load_client_profile(settings.client_root / agency.client_profile)
        client_version = db.scalar(
            select(ClientConfigVersion).where(
                ClientConfigVersion.org_id == org_id,
                ClientConfigVersion.content_hash == client.content_hash,
            )
        )
        if client_version is None:
            client_version = ClientConfigVersion(
                org_id=org_id,
                client=client.config.client,
                jurisdiction=client.config.jurisdiction,
                effective_from=client.config.insurance.effective_from,
                content_hash=client.content_hash,
                content=client.raw,
            )
            db.add(client_version)

        fx_rate = db.scalar(
            select(CustomsFxRate).where(
                CustomsFxRate.org_id == org_id,
                CustomsFxRate.base_currency == loaded.config.fx.quote_currency,
                CustomsFxRate.quote_currency == loaded.config.currency,
                CustomsFxRate.year == rate_date.year,
                CustomsFxRate.month == rate_date.month,
            )
        )
        if fx_rate is None:
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

        pins[org_id] = DemoConfigPins(
            organization=organization,
            agency=agency,
            jurisdiction=jurisdiction_version,
            client=client_version,
            fx_rate=fx_rate,
        )
    db.commit()
    if selected_org_id not in pins:
        raise ValueError(f"organization {selected_org_id} is not configured in the demo catalog")
    selected = pins[selected_org_id]
    db.refresh(selected.organization)
    db.refresh(selected.jurisdiction)
    db.refresh(selected.client)
    db.refresh(selected.fx_rate)
    return selected
