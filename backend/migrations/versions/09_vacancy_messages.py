"""Private manager and RH conversation per vacancy."""
import sqlalchemy as sa
from alembic import op

revision = "09_vacancy_messages"
down_revision = "08_admission_approval"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("vacancy_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.String(36), sa.ForeignKey("vacancies.id"), nullable=False),
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
    )
    op.create_index("ix_vacancy_messages_vacancy_id", "vacancy_messages", ["vacancy_id"])


def downgrade():
    op.drop_table("vacancy_messages")
