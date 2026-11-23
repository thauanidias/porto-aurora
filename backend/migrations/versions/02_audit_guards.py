"""Protect critical history against update and deletion."""

from alembic import op

revision = "02_audit_guards"
down_revision = "d4d8a2739feb"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Critical history is append-only'; END;
        $$;
    """)
    for table in (
        "audit_logs",
        "scoring_model_versions",
        "application_scores",
        "config_revisions",
        "approvals",
        "consents",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )
    op.execute(
        "CREATE INDEX candidate_search_idx ON candidates USING GIN (to_tsvector('portuguese', name || ' ' || city))"
    )


def downgrade():
    op.drop_index("candidate_search_idx", table_name="candidates")
    for table in (
        "audit_logs",
        "scoring_model_versions",
        "application_scores",
        "config_revisions",
        "approvals",
        "consents",
    ):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
    op.execute("DROP FUNCTION reject_history_mutation()")
