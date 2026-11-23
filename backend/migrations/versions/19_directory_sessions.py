"""Bind corporate sessions to a verified read-only AD identity."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "19_directory_sessions"
down_revision = "18_registration_phase"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("auth_sessions", sa.Column("directory_auth", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column("auth_sessions", "directory_auth")
