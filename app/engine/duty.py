from datetime import date
from decimal import Decimal

from app.engine.jurisdiction import JurisdictionConfig
from app.engine.normalize import normalized_text
from app.schemas.domain import CertificateOfOrigin


def duty_rate(
    hs_code: str,
    coo: CertificateOfOrigin | None,
    sailing_date: date | None,
    cfg: JurisdictionConfig,
) -> tuple[Decimal, str]:
    lookup_levy = next((levy for levy in cfg.levies if levy.rate.type == "hs_lookup"), None)
    if lookup_levy is None or lookup_levy.rate.default is None:
        raise ValueError("jurisdiction lacks a default hs_lookup rate")
    general_rate = lookup_levy.rate.default
    if coo is None:
        return general_rate, "Tasa general: no se recibió certificado de origen"
    covered = {item.hs_code.value for item in coo.items if item.hs_code.value}
    certificate = coo.certificate_number.value or "sin número"
    if hs_code not in covered:
        return (
            general_rate,
            f"Tasa general: HS {hs_code} no está cubierto por certificado {certificate}",
        )
    certificate_agreement = normalized_text(coo.agreement_name.value)
    agreement = next(
        (
            item
            for item in cfg.trade_agreements
            if certificate_agreement
            in {normalized_text(candidate) for candidate in (item.code, item.label, *item.aliases)}
        ),
        None,
    )
    if agreement is None:
        return (
            general_rate,
            "Tasa general: el acuerdo del certificado no coincide con la configuración",
        )
    reason = f"Preferencia {agreement.label}, certificado {certificate}"
    if (
        sailing_date
        and coo.issue_date.value
        and coo.issue_date.value > sailing_date
        and not bool(coo.is_retrospective.value)
    ):
        reason += " - EN RIESGO: certificado emitido después del embarque"
    return agreement.preferential_rate, reason
