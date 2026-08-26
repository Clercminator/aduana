"""Reset transactional records and stored files for configured demo organizations."""

from __future__ import annotations

import argparse
import shutil
import uuid
from pathlib import Path

from sqlalchemy import delete, func, select

from app.config import Settings, get_settings
from app.db.models import (
    AuditEvent,
    CalculationRun,
    Dispatch,
    Document,
    ExceptionResult,
    ExtractionRun,
    FieldCorrection,
    GeneratedArtifact,
    Job,
)
from app.db.session import session_factory
from app.engine.agency import load_agency_catalog


def _configured_org_ids(settings: Settings) -> set[uuid.UUID]:
    return {item.config.organization_id for item in load_agency_catalog(settings.agency_root)}


def _safe_org_path(root: Path, org_id: uuid.UUID) -> Path:
    resolved_root = root.resolve()
    target = (resolved_root / str(org_id)).resolve()
    if target.parent != resolved_root:
        raise RuntimeError(f"Ruta de reset fuera de la raíz permitida: {target}")
    return target


def _remove_org_storage(settings: Settings, org_ids: set[uuid.UUID]) -> int:
    removed = 0
    for root in (settings.document_root, settings.artifact_root):
        for org_id in org_ids:
            target = _safe_org_path(root, org_id)
            if target.exists():
                shutil.rmtree(target)
                removed += 1
    return removed


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Elimina datos transaccionales de las agencias demo y conserva configuración."
    )
    parser.add_argument(
        "--org-id",
        action="append",
        type=uuid.UUID,
        help="Limita el reset a una organización configurada; se puede repetir.",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    settings = get_settings()
    configured = _configured_org_ids(settings)
    requested = set(args.org_id or configured)
    unknown = requested - configured
    if unknown:
        values = ", ".join(sorted(str(item) for item in unknown))
        raise SystemExit(f"Organización no configurada para la demo: {values}")

    with session_factory()() as db:
        dispatch_count = db.scalar(
            select(func.count()).select_from(Dispatch).where(Dispatch.org_id.in_(requested))
        )
        for model in (
            ExtractionRun,
            ExceptionResult,
            GeneratedArtifact,
            AuditEvent,
            FieldCorrection,
            Job,
            CalculationRun,
            Document,
            Dispatch,
        ):
            db.execute(delete(model).where(model.org_id.in_(requested)))
        db.commit()

    removed_directories = _remove_org_storage(settings, requested)
    print(
        "Demo restablecida: "
        f"{len(requested)} organizaciones, {dispatch_count or 0} despachos y "
        f"{removed_directories} directorios de storage eliminados; configuración preservada."
    )


if __name__ == "__main__":
    main()
