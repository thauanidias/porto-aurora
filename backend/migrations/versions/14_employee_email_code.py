"""Confirm employee registration using a single-use email code."""
import sqlalchemy as sa
from alembic import op

revision = "14_employee_email_code"
down_revision = "13_employee_access"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("email_confirmed_at", "email_code_expires_at", "email_code_sent_at"):
        op.add_column("employee_access_requests", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("employee_access_requests", sa.Column("email_code_hash", sa.String(64)))
    op.add_column("employee_access_requests", sa.Column("email_code_attempts", sa.Integer(), nullable=False, server_default="0"))
    # Existing employees already validated their corporate identity through AD.
    op.execute("UPDATE employee_access_requests SET email_confirmed_at = updated_at WHERE status = 'VERIFIED'")


def downgrade():
    for name in ("email_code_attempts", "email_code_hash", "email_code_sent_at", "email_code_expires_at", "email_confirmed_at"):
        op.drop_column("employee_access_requests", name)
