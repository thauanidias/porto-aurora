"""Allow consent to a document recorded by its immutable receipt."""

import sqlalchemy as sa
from alembic import op

revision = "06_document_consent"
down_revision = "05_consent_receipts"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("consents", "notice_id", existing_type=sa.String(36), nullable=True)


def downgrade():
    op.alter_column("consents", "notice_id", existing_type=sa.String(36), nullable=False)
