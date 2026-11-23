"""Employee registration activated by directory authentication."""
import sqlalchemy as sa
from alembic import op

revision = "13_employee_access"
down_revision = "12_test_questionnaire"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("employee_access_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("network_username", sa.String(180), nullable=False, unique=True),
        sa.Column("department", sa.String(180), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
    )


def downgrade():
    op.drop_table("employee_access_requests")
