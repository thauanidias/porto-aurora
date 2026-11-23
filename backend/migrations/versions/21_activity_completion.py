"""Record candidate confirmation of external test completion."""
from alembic import op
import sqlalchemy as sa
revision = "21_activity_completion"
down_revision = "20_registration_access"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("candidate_activity_links", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

def downgrade():
    op.drop_column("candidate_activity_links", "completed_at")
