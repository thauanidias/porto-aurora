"""Self-service manager access requests, reviewed by RH."""
import sqlalchemy as sa
from alembic import op

revision = "07_manager_access"
down_revision = "06_document_consent"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("manager_access_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("department", sa.String(180), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("reason", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("manager_access_requests")
