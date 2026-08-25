from app.db.models import (
    AuditEvent,
    CalculationRun,
    ClientConfigVersion,
    CustomsFxRate,
    Dispatch,
    Document,
    ExceptionResult,
    ExtractionRun,
    FieldCorrection,
    GeneratedArtifact,
    Job,
)


def test_every_tenant_owned_model_has_org_id():
    for model in [
        Dispatch,
        Document,
        ExtractionRun,
        FieldCorrection,
        Job,
        CalculationRun,
        ExceptionResult,
        AuditEvent,
        GeneratedArtifact,
        CustomsFxRate,
        ClientConfigVersion,
    ]:
        assert "org_id" in model.__table__.columns, model.__name__
