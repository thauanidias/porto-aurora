"""Store candidate feedback for RH evaluation."""
from alembic import op
import sqlalchemy as sa
revision = "22_candidate_feedback"
down_revision = "21_activity_completion"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("candidate_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("candidates.id"), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="candidate_feedback_rating_valid"))
    op.create_index("ix_candidate_feedback_candidate_id", "candidate_feedback", ["candidate_id"])
    op.create_index("ix_candidate_feedback_application_id", "candidate_feedback", ["application_id"])

def downgrade():
    op.drop_table("candidate_feedback")
