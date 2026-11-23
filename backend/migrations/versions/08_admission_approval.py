"""Require RH approval before admission document uploads."""
import sqlalchemy as sa
from alembic import op

revision = "08_admission_approval"
down_revision = "07_manager_access"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidates", sa.Column("admission_documents_approved", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("candidates", "admission_documents_approved")
