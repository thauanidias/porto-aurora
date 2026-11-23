"""Confirmed quick applications and atomic import batches."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "03_intake"
down_revision = "02_audit_guards"
branch_labels = None
depends_on = None


def common():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
    ]


def upgrade():
    op.create_table(
        "quick_applications",
        sa.Column("vacancy_id", sa.String(36), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("notice_id", sa.String(36), sa.ForeignKey("config_records.id"), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("answers", postgresql.JSONB, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *common(),
    )
    op.create_index("ix_quick_applications_vacancy_id", "quick_applications", ["vacancy_id"])
    op.create_index("ix_quick_applications_email", "quick_applications", ["email"])
    op.create_table(
        "import_batches",
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("rows", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        *common(),
    )


def downgrade():
    op.drop_table("import_batches")
    op.drop_table("quick_applications")
