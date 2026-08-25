"""Pin client configuration and monthly customs FX rates."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_client_config_monthly_fx"
down_revision = "0001_demo_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "client_config_version" not in tables:
        op.create_table(
            "client_config_version",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("client", sa.String(80), nullable=False, index=True),
            sa.Column("jurisdiction", sa.String(2), nullable=False, index=True),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("content", postgresql.JSONB(), nullable=False),
            sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if "customs_fx_rate" not in tables:
        op.create_table(
            "customs_fx_rate",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("org.id"), nullable=False
            ),
            sa.Column("base_currency", sa.String(3), nullable=False),
            sa.Column("quote_currency", sa.String(3), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("rate", sa.Numeric(20, 8), nullable=False),
            sa.Column("source", sa.String(200), nullable=False),
            sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("org_id", "base_currency", "quote_currency", "year", "month"),
        )
    dispatch_columns = {item["name"] for item in sa.inspect(bind).get_columns("dispatch")}
    if "client_config_version_id" not in dispatch_columns:
        op.add_column(
            "dispatch",
            sa.Column(
                "client_config_version_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("client_config_version.id"),
                nullable=True,
            ),
        )
    if "customs_fx_rate_id" not in dispatch_columns:
        op.add_column(
            "dispatch",
            sa.Column(
                "customs_fx_rate_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("customs_fx_rate.id"),
                nullable=True,
            ),
        )
    if "din_acceptance_date" not in dispatch_columns:
        op.add_column("dispatch", sa.Column("din_acceptance_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("dispatch", "din_acceptance_date")
    op.drop_column("dispatch", "customs_fx_rate_id")
    op.drop_column("dispatch", "client_config_version_id")
    op.drop_table("customs_fx_rate")
    op.drop_table("client_config_version")
