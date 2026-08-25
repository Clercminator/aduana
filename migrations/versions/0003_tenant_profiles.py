"""Own client configuration by organization and persist agency profile metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_tenant_profiles"
down_revision = "0002_client_config_monthly_fx"
branch_labels = None
depends_on = None

DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    org_columns = {item["name"] for item in inspector.get_columns("org")}
    if "profile" not in org_columns:
        op.add_column(
            "org",
            sa.Column(
                "profile",
                postgresql.JSONB(),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    client_columns = {
        item["name"] for item in sa.inspect(bind).get_columns("client_config_version")
    }
    if "org_id" not in client_columns:
        op.add_column(
            "client_config_version",
            sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.execute(
            sa.text("update client_config_version set org_id = cast(:org_id as uuid)").bindparams(
                org_id=DEMO_ORG_ID
            )
        )
        op.alter_column("client_config_version", "org_id", nullable=False)
        op.create_foreign_key(
            "fk_client_config_version_org_id",
            "client_config_version",
            "org",
            ["org_id"],
            ["id"],
        )

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("client_config_version")}
    if "ix_client_config_version_org_id" not in indexes:
        op.create_index("ix_client_config_version_org_id", "client_config_version", ["org_id"])

    uniques = {
        item["name"] for item in sa.inspect(bind).get_unique_constraints("client_config_version")
    }
    if "client_config_version_content_hash_key" in uniques:
        op.drop_constraint(
            "client_config_version_content_hash_key", "client_config_version", type_="unique"
        )
    if "uq_client_config_org_hash" not in uniques:
        op.create_unique_constraint(
            "uq_client_config_org_hash",
            "client_config_version",
            ["org_id", "content_hash"],
        )


def downgrade() -> None:
    op.drop_constraint("uq_client_config_org_hash", "client_config_version", type_="unique")
    op.drop_index("ix_client_config_version_org_id", table_name="client_config_version")
    op.create_unique_constraint(
        "client_config_version_content_hash_key", "client_config_version", ["content_hash"]
    )
    op.drop_constraint(
        "fk_client_config_version_org_id", "client_config_version", type_="foreignkey"
    )
    op.drop_column("client_config_version", "org_id")
    op.drop_column("org", "profile")
