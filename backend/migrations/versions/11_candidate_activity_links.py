"""RH links and instructions for an individual application."""
import sqlalchemy as sa
from alembic import op

revision = "11_candidate_activity_links"
down_revision = "10_candidate_journey"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("candidate_activity_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("applications.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("kind IN ('INTERVIEW', 'TEST')", name="activity_link_kind_valid"))
    op.create_index("ix_candidate_activity_links_application_id", "candidate_activity_links", ["application_id"])


def downgrade():
    op.drop_table("candidate_activity_links")
