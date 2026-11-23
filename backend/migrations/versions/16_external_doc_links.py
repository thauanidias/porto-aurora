"""Link reviewed external document snapshots to internal employee profiles."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "16_external_doc_links"
down_revision = "15_application_recruitment_type"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("candidate_document_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("source_candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("linked_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("documents", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("candidate_id", "source_candidate_id"))
    op.create_index("ix_candidate_document_sources_candidate_id", "candidate_document_sources", ["candidate_id"])


def downgrade():
    op.drop_table("candidate_document_sources")
