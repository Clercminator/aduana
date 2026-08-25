"""Reset only the seeded demo organization's transactional records."""

from __future__ import annotations

import uuid

from sqlalchemy import delete

from app.config import get_settings
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


def main() -> None:
    org_id = uuid.UUID(get_settings().demo_org_id)
    with session_factory()() as db:
        dispatch_ids = db.scalars(
            Dispatch.__table__.select()
            .with_only_columns(Dispatch.id)
            .where(Dispatch.org_id == org_id)
        ).all()
        if dispatch_ids:
            document_ids = db.scalars(
                Document.__table__.select()
                .with_only_columns(Document.id)
                .where(Document.dispatch_id.in_(dispatch_ids))
            ).all()
            if document_ids:
                db.execute(delete(ExtractionRun).where(ExtractionRun.document_id.in_(document_ids)))
            for model in (
                ExceptionResult,
                GeneratedArtifact,
                AuditEvent,
                FieldCorrection,
                Job,
                CalculationRun,
            ):
                db.execute(delete(model).where(model.dispatch_id.in_(dispatch_ids)))
            db.execute(delete(Document).where(Document.dispatch_id.in_(dispatch_ids)))
            db.execute(delete(Dispatch).where(Dispatch.id.in_(dispatch_ids)))
        db.commit()
    print(f"Demo restablecida: {len(dispatch_ids)} despachos eliminados; configuración preservada.")


if __name__ == "__main__":
    main()
