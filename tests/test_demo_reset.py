import uuid
from pathlib import Path

from app.config import Settings
from scripts.reset_demo import _configured_org_ids, _remove_org_storage, _safe_org_path

ROOT = Path(__file__).parents[1]
IMR_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PACIFICO_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def test_reset_targets_every_configured_demo_organization(tmp_path):
    settings = Settings(agency_root=ROOT / "agencies")
    assert _configured_org_ids(settings) == {IMR_ORG_ID, PACIFICO_ORG_ID}


def test_reset_removes_only_tenant_storage_directories(tmp_path):
    document_root = tmp_path / "documents"
    artifact_root = tmp_path / "artifacts"
    settings = Settings(
        agency_root=ROOT / "agencies",
        document_root=document_root,
        artifact_root=artifact_root,
    )
    for root in (document_root, artifact_root):
        tenant_path = _safe_org_path(root, PACIFICO_ORG_ID)
        tenant_path.mkdir(parents=True)
        (tenant_path / "demo.bin").write_bytes(b"demo")
        (root / "preservar.txt").write_text("keep", encoding="utf-8")

    assert _remove_org_storage(settings, {PACIFICO_ORG_ID}) == 2
    for root in (document_root, artifact_root):
        assert not (root / str(PACIFICO_ORG_ID)).exists()
        assert (root / "preservar.txt").read_text(encoding="utf-8") == "keep"
