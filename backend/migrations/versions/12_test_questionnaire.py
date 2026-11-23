"""Individual mini questionnaires for the test phase."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "12_test_questionnaire"
down_revision = "11_candidate_activity_links"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("test_questionnaire", postgresql.JSONB(), nullable=False,
                                           server_default=sa.text("'{}'::jsonb")))


def downgrade():
    op.drop_column("applications", "test_questionnaire")
