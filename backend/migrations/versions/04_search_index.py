"""Align the professional search index with the authorized search expression."""

from alembic import op

revision = "04_search_index"
down_revision = "03_intake"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index("candidate_search_idx", table_name="candidates")
    op.execute(
        "CREATE INDEX candidate_search_idx ON candidates USING GIN (to_tsvector('portuguese', name || ' ' || city || ' ' || profile::text))"
    )


def downgrade():
    op.drop_index("candidate_search_idx", table_name="candidates")
    op.execute(
        "CREATE INDEX candidate_search_idx ON candidates USING GIN (to_tsvector('portuguese', name || ' ' || city))"
    )
