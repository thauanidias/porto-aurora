"""Immutable document acceptance receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "05_consent_receipts"
down_revision = "04_search_index"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "consent_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(60), unique=True, nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("ip", sa.String(45), nullable=False),
        sa.Column("context", sa.String(30), nullable=False),
        sa.Column("document_code", sa.String(50), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("document_snapshot", postgresql.JSONB(), nullable=False),
    )
    op.create_index("ix_consent_receipts_email", "consent_receipts", ["email"])
    op.execute(
        "CREATE TRIGGER consent_receipts_immutable BEFORE UPDATE OR DELETE ON consent_receipts FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
    )


def downgrade():
    op.drop_table("consent_receipts")
