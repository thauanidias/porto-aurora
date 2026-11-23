"""Per-application screening reviews and encrypted external forms."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "17_process_workflow"
down_revision = "16_external_doc_links"
branch_labels = None
depends_on = None


def entity_columns():
    return [sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table("stage_reviews", *entity_columns(),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("stage_id", sa.String(36), sa.ForeignKey("pipeline_stages.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("status IN ('APPROVED', 'REJECTED', 'PENDING')", name="stage_review_status_valid"))
    op.create_index("ix_stage_reviews_application_id", "stage_reviews", ["application_id"])
    op.create_table("process_forms", *entity_columns(),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("encrypted_data", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("status IN ('SENT', 'PENDING', 'COMPLETED')", name="process_form_status_valid"))
    op.drop_constraint("candidate_phase_valid", "pipeline_stages", type_="check")
    op.create_check_constraint("candidate_phase_valid", "pipeline_stages",
        "candidate_phase IS NULL OR candidate_phase IN ('RECRUITMENT', 'SELECTION', 'FORM', 'INTERVIEW', 'TEST', 'ADMISSION')")


def downgrade():
    op.execute("UPDATE pipeline_stages SET candidate_phase = 'SELECTION' WHERE candidate_phase = 'FORM'")
    op.drop_constraint("candidate_phase_valid", "pipeline_stages", type_="check")
    op.create_check_constraint("candidate_phase_valid", "pipeline_stages",
        "candidate_phase IS NULL OR candidate_phase IN ('RECRUITMENT', 'SELECTION', 'INTERVIEW', 'TEST', 'ADMISSION')")
    op.drop_table("process_forms")
    op.drop_table("stage_reviews")
