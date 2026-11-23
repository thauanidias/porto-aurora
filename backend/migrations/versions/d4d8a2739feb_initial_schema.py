"""initial_schema"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d4d8a2739feb"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "applications",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("utm", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_reason", sa.Text(), nullable=False),
        sa.Column("cv_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "vacancy_id"),
    )
    op.create_index(
        op.f("ix_applications_candidate_id"), "applications", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_applications_stage_id"), "applications", ["stage_id"], unique=False)
    op.create_index(op.f("ix_applications_status"), "applications", ["status"], unique=False)
    op.create_index(
        op.f("ix_applications_vacancy_id"), "applications", ["vacancy_id"], unique=False
    )
    op.create_table(
        "documents",
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("uploaded_by", sa.String(length=36), nullable=False),
        sa.Column("type_name", sa.String(length=180), nullable=False),
        sa.Column("filename", sa.String(length=180), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("scan_status", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_documents_candidate_id"), "documents", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_documents_sha256"), "documents", ["sha256"], unique=False)
    op.create_table(
        "org_units",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_org_units_parent_id"), "org_units", ["parent_id"], unique=False)
    op.create_table(
        "outbox",
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("dedup_key", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key"),
    )
    op.create_index(op.f("ix_outbox_kind"), "outbox", ["kind"], unique=False)
    op.create_index(op.f("ix_outbox_status"), "outbox", ["status"], unique=False)
    op.create_table(
        "permissions",
        sa.Column("name", sa.String(length=90), nullable=False),
        sa.Column("description", sa.String(length=180), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission", sa.String(length=90), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission"),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("auth_source", sa.String(), nullable=False),
        sa.Column("first_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("org_unit_id", sa.String(length=36), nullable=True),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="email_normalized"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "assessments",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("attempts_allowed", sa.Integer(), nullable=False),
        sa.Column("pass_score", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("shuffle", sa.Boolean(), nullable=False),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        op.f("ix_auth_sessions_previous_hash"), "auth_sessions", ["previous_hash"], unique=False
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "auth_tokens",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)
    op.create_table(
        "candidates",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("social_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("talent_consent_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_into_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_candidates_phone"), "candidates", ["phone"], unique=False)
    op.create_table(
        "checklist_items",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checklist_items_application_id"),
        "checklist_items",
        ["application_id"],
        unique=False,
    )
    op.create_table(
        "config_records",
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "name"),
    )
    op.create_index(op.f("ix_config_records_kind"), "config_records", ["kind"], unique=False)
    op.create_table(
        "messages",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("sender_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_messages_application_id"), "messages", ["application_id"], unique=False
    )
    op.create_table(
        "notifications",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("link", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    op.create_table(
        "offers",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_ip", sa.String(), nullable=False),
        sa.Column("response_reason", sa.Text(), nullable=False),
        sa.Column("workflow_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "number"),
    )
    op.create_index(op.f("ix_offers_application_id"), "offers", ["application_id"], unique=False)
    op.create_table(
        "talent_pools",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_table(
        "vacancy_requests",
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="request_quantity_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_vacancy_requests_org_unit_id"), "vacancy_requests", ["org_unit_id"], unique=False
    )
    op.create_index(
        op.f("ix_vacancy_requests_requested_by"), "vacancy_requests", ["requested_by"], unique=False
    )
    op.create_index(
        op.f("ix_vacancy_requests_status"), "vacancy_requests", ["status"], unique=False
    )
    op.create_table(
        "webhooks",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("events", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "automation_executions",
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_id", "event_id"),
    )
    op.create_table(
        "candidate_labels",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "user_id", "kind", "label"),
    )
    op.create_index(
        op.f("ix_candidate_labels_candidate_id"), "candidate_labels", ["candidate_id"], unique=False
    )
    op.create_table(
        "candidate_sensitive",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("encrypted_data", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_table(
        "config_revisions",
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_id", "revision"),
    )
    op.create_index(
        op.f("ix_config_revisions_record_id"), "config_revisions", ["record_id"], unique=False
    )
    op.create_table(
        "consents",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("notice_id", sa.String(length=36), nullable=False),
        sa.Column("notice_version", sa.Integer(), nullable=False),
        sa.Column("notice_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consents_candidate_id"), "consents", ["candidate_id"], unique=False)
    op.create_table(
        "data_subject_requests",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("handled_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_subject_requests_candidate_id"),
        "data_subject_requests",
        ["candidate_id"],
        unique=False,
    )
    op.create_table(
        "survey_responses",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("survey_id", sa.String(length=36), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "survey_id"),
    )
    op.create_table(
        "talent_pool_members",
        sa.Column("pool_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("added_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pool_id", "candidate_id"),
    )
    op.create_index(
        op.f("ix_talent_pool_members_candidate_id"),
        "talent_pool_members",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_talent_pool_members_pool_id"), "talent_pool_members", ["pool_id"], unique=False
    )
    op.create_table(
        "test_assignments",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("assessment_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "assessment_id"),
    )
    op.create_index(
        op.f("ix_test_assignments_application_id"),
        "test_assignments",
        ["application_id"],
        unique=False,
    )
    op.create_table(
        "vacancies",
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("slug", sa.String(length=230), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("org_unit_id", sa.String(length=36), nullable=False),
        sa.Column("recruiter_id", sa.String(length=36), nullable=False),
        sa.Column("manager_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("audience", sa.String(), nullable=False),
        sa.Column("confidential", sa.Boolean(), nullable=False),
        sa.Column("blind", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
        sa.Column("modality", sa.String(), nullable=False),
        sa.Column("contract_type", sa.String(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="vacancy_quantity_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_vacancies_org_unit_id"), "vacancies", ["org_unit_id"], unique=False)
    op.create_index(op.f("ix_vacancies_recruiter_id"), "vacancies", ["recruiter_id"], unique=False)
    op.create_index(op.f("ix_vacancies_status"), "vacancies", ["status"], unique=False)
    op.create_index(op.f("ix_vacancies_title"), "vacancies", ["title"], unique=False)
    op.create_table(
        "approvals",
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("vacancy_id", sa.String(length=36), nullable=True),
        sa.Column("offer_id", sa.String(length=36), nullable=True),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.String(length=36), nullable=False),
        sa.Column("delegated_from", sa.String(length=36), nullable=True),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(request_id, vacancy_id, offer_id) = 1", name="approval_one_parent"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_approvals_offer_id"), "approvals", ["offer_id"], unique=False)
    op.create_index(op.f("ix_approvals_request_id"), "approvals", ["request_id"], unique=False)
    op.create_index(op.f("ix_approvals_vacancy_id"), "approvals", ["vacancy_id"], unique=False)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("vacancy_id", sa.String(length=36), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_id"), "audit_logs", ["entity_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_vacancy_id"), "audit_logs", ["vacancy_id"], unique=False)
    op.create_table(
        "interviews",
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("template", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("ends_at > starts_at AND capacity > 0", name="interview_valid"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_interviews_starts_at"), "interviews", ["starts_at"], unique=False)
    op.create_index(op.f("ix_interviews_vacancy_id"), "interviews", ["vacancy_id"], unique=False)
    op.create_table(
        "pipeline_stages",
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("reveal_identity", sa.Boolean(), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("sla_hours > 0", name="stage_sla_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "position"),
    )
    op.create_index(
        op.f("ix_pipeline_stages_vacancy_id"), "pipeline_stages", ["vacancy_id"], unique=False
    )
    op.create_table(
        "referrals",
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("referred_by", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "email"),
    )
    op.create_index(op.f("ix_referrals_vacancy_id"), "referrals", ["vacancy_id"], unique=False)
    op.create_table(
        "scoring_model_versions",
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("composition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bands", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "number"),
    )
    op.create_index(
        op.f("ix_scoring_model_versions_vacancy_id"),
        "scoring_model_versions",
        ["vacancy_id"],
        unique=False,
    )
    op.create_table(
        "tasks",
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("assigned_to", sa.String(length=36), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("vacancy_id", sa.String(length=36), nullable=True),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("priority", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_assigned_to"), "tasks", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_tasks_due_at"), "tasks", ["due_at"], unique=False)
    op.create_index(op.f("ix_tasks_vacancy_id"), "tasks", ["vacancy_id"], unique=False)
    op.create_table(
        "test_attempts",
        sa.Column("assignment_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("grading", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("graded_by", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "number"),
    )
    op.create_index(
        op.f("ix_test_attempts_assignment_id"), "test_attempts", ["assignment_id"], unique=False
    )
    op.create_table(
        "vacancy_assignments",
        sa.Column("vacancy_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "user_id"),
    )
    op.create_index(
        op.f("ix_vacancy_assignments_user_id"), "vacancy_assignments", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_vacancy_assignments_vacancy_id"),
        "vacancy_assignments",
        ["vacancy_id"],
        unique=False,
    )
    op.create_table(
        "application_scores",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=36), nullable=False),
        sa.Column("total", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("knockout", sa.Boolean(), nullable=False),
        sa.Column("breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint("total >= 0 AND total <= 100", name="score_bounds"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_scores_application_id"),
        "application_scores",
        ["application_id"],
        unique=False,
    )
    op.create_table(
        "application_stage_history",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=36), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("changed_by", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_stage_history_application_id"),
        "application_stage_history",
        ["application_id"],
        unique=False,
    )
    op.create_table(
        "evaluations",
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("interview_id", sa.String(length=36), nullable=True),
        sa.Column("evaluator_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("independent", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("recommendation", sa.String(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", "evaluator_id", "category"),
    )
    op.create_index(
        op.f("ix_evaluations_application_id"), "evaluations", ["application_id"], unique=False
    )
    op.create_index(
        op.f("ix_evaluations_evaluator_id"), "evaluations", ["evaluator_id"], unique=False
    )
    op.create_table(
        "interview_participants",
        sa.Column("interview_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id", "user_id"),
    )
    op.create_index(
        op.f("ix_interview_participants_interview_id"),
        "interview_participants",
        ["interview_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_participants_user_id"),
        "interview_participants",
        ["user_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_applications_candidate_id", "applications", "candidates", ["candidate_id"], ["id"]
    )
    op.create_foreign_key("fk_applications_cv_id", "applications", "documents", ["cv_id"], ["id"])
    op.create_foreign_key(
        "fk_applications_stage_id", "applications", "pipeline_stages", ["stage_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_applications_vacancy_id", "applications", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_documents_application_id", "documents", "applications", ["application_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_documents_candidate_id", "documents", "candidates", ["candidate_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_documents_request_id", "documents", "vacancy_requests", ["request_id"], ["id"]
    )
    op.create_foreign_key("fk_documents_reviewed_by", "documents", "users", ["reviewed_by"], ["id"])
    op.create_foreign_key("fk_documents_uploaded_by", "documents", "users", ["uploaded_by"], ["id"])
    op.create_foreign_key("fk_org_units_parent_id", "org_units", "org_units", ["parent_id"], ["id"])
    op.create_foreign_key(
        "fk_role_permissions_permission",
        "role_permissions",
        "permissions",
        ["permission"],
        ["name"],
    )
    op.create_foreign_key(
        "fk_role_permissions_role_id", "role_permissions", "roles", ["role_id"], ["id"]
    )
    op.create_foreign_key("fk_users_org_unit_id", "users", "org_units", ["org_unit_id"], ["id"])
    op.create_foreign_key(
        "fk_assessments_created_by", "assessments", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key("fk_auth_sessions_user_id", "auth_sessions", "users", ["user_id"], ["id"])
    op.create_foreign_key("fk_auth_tokens_user_id", "auth_tokens", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_candidates_merged_into_id", "candidates", "candidates", ["merged_into_id"], ["id"]
    )
    op.create_foreign_key("fk_candidates_user_id", "candidates", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_checklist_items_application_id",
        "checklist_items",
        "applications",
        ["application_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_checklist_items_reviewed_by", "checklist_items", "users", ["reviewed_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_config_records_created_by", "config_records", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_messages_application_id", "messages", "applications", ["application_id"], ["id"]
    )
    op.create_foreign_key("fk_messages_sender_id", "messages", "users", ["sender_id"], ["id"])
    op.create_foreign_key("fk_notifications_user_id", "notifications", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_offers_application_id", "offers", "applications", ["application_id"], ["id"]
    )
    op.create_foreign_key("fk_offers_created_by", "offers", "users", ["created_by"], ["id"])
    op.create_foreign_key(
        "fk_talent_pools_created_by", "talent_pools", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key("fk_user_roles_role_id", "user_roles", "roles", ["role_id"], ["id"])
    op.create_foreign_key("fk_user_roles_user_id", "user_roles", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_vacancy_requests_org_unit_id", "vacancy_requests", "org_units", ["org_unit_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_vacancy_requests_requested_by", "vacancy_requests", "users", ["requested_by"], ["id"]
    )
    op.create_foreign_key("fk_webhooks_created_by", "webhooks", "users", ["created_by"], ["id"])
    op.create_foreign_key(
        "fk_automation_executions_rule_id",
        "automation_executions",
        "config_records",
        ["rule_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_candidate_labels_candidate_id",
        "candidate_labels",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_candidate_labels_user_id", "candidate_labels", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_candidate_sensitive_candidate_id",
        "candidate_sensitive",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_config_revisions_created_by", "config_revisions", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_config_revisions_record_id", "config_revisions", "config_records", ["record_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_consents_candidate_id", "consents", "candidates", ["candidate_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_consents_notice_id", "consents", "config_records", ["notice_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_data_subject_requests_candidate_id",
        "data_subject_requests",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_data_subject_requests_handled_by",
        "data_subject_requests",
        "users",
        ["handled_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_survey_responses_candidate_id",
        "survey_responses",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_survey_responses_survey_id", "survey_responses", "config_records", ["survey_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_talent_pool_members_added_by", "talent_pool_members", "users", ["added_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_talent_pool_members_candidate_id",
        "talent_pool_members",
        "candidates",
        ["candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_talent_pool_members_pool_id", "talent_pool_members", "talent_pools", ["pool_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_test_assignments_application_id",
        "test_assignments",
        "applications",
        ["application_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_test_assignments_assessment_id",
        "test_assignments",
        "assessments",
        ["assessment_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_test_assignments_created_by", "test_assignments", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key("fk_vacancies_manager_id", "vacancies", "users", ["manager_id"], ["id"])
    op.create_foreign_key(
        "fk_vacancies_org_unit_id", "vacancies", "org_units", ["org_unit_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_vacancies_recruiter_id", "vacancies", "users", ["recruiter_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_vacancies_request_id", "vacancies", "vacancy_requests", ["request_id"], ["id"]
    )
    op.create_foreign_key("fk_approvals_approver_id", "approvals", "users", ["approver_id"], ["id"])
    op.create_foreign_key(
        "fk_approvals_delegated_from", "approvals", "users", ["delegated_from"], ["id"]
    )
    op.create_foreign_key("fk_approvals_offer_id", "approvals", "offers", ["offer_id"], ["id"])
    op.create_foreign_key(
        "fk_approvals_request_id", "approvals", "vacancy_requests", ["request_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_approvals_vacancy_id", "approvals", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key("fk_audit_logs_user_id", "audit_logs", "users", ["user_id"], ["id"])
    op.create_foreign_key(
        "fk_audit_logs_vacancy_id", "audit_logs", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key("fk_interviews_created_by", "interviews", "users", ["created_by"], ["id"])
    op.create_foreign_key(
        "fk_interviews_vacancy_id", "interviews", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_pipeline_stages_vacancy_id", "pipeline_stages", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_referrals_candidate_id", "referrals", "candidates", ["candidate_id"], ["id"]
    )
    op.create_foreign_key("fk_referrals_referred_by", "referrals", "users", ["referred_by"], ["id"])
    op.create_foreign_key(
        "fk_referrals_vacancy_id", "referrals", "vacancies", ["vacancy_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_scoring_model_versions_created_by",
        "scoring_model_versions",
        "users",
        ["created_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_scoring_model_versions_vacancy_id",
        "scoring_model_versions",
        "vacancies",
        ["vacancy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_tasks_application_id", "tasks", "applications", ["application_id"], ["id"]
    )
    op.create_foreign_key("fk_tasks_assigned_to", "tasks", "users", ["assigned_to"], ["id"])
    op.create_foreign_key("fk_tasks_created_by", "tasks", "users", ["created_by"], ["id"])
    op.create_foreign_key("fk_tasks_vacancy_id", "tasks", "vacancies", ["vacancy_id"], ["id"])
    op.create_foreign_key(
        "fk_test_attempts_assignment_id",
        "test_attempts",
        "test_assignments",
        ["assignment_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_test_attempts_graded_by", "test_attempts", "users", ["graded_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_vacancy_assignments_user_id", "vacancy_assignments", "users", ["user_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_vacancy_assignments_vacancy_id",
        "vacancy_assignments",
        "vacancies",
        ["vacancy_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_application_scores_application_id",
        "application_scores",
        "applications",
        ["application_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_application_scores_created_by", "application_scores", "users", ["created_by"], ["id"]
    )
    op.create_foreign_key(
        "fk_application_scores_model_id",
        "application_scores",
        "scoring_model_versions",
        ["model_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_application_stage_history_application_id",
        "application_stage_history",
        "applications",
        ["application_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_application_stage_history_changed_by",
        "application_stage_history",
        "users",
        ["changed_by"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_application_stage_history_stage_id",
        "application_stage_history",
        "pipeline_stages",
        ["stage_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_evaluations_application_id", "evaluations", "applications", ["application_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_evaluations_evaluator_id", "evaluations", "users", ["evaluator_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_evaluations_interview_id", "evaluations", "interviews", ["interview_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_interview_participants_application_id",
        "interview_participants",
        "applications",
        ["application_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_interview_participants_interview_id",
        "interview_participants",
        "interviews",
        ["interview_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_interview_participants_user_id", "interview_participants", "users", ["user_id"], ["id"]
    )


def downgrade():
    op.drop_constraint(
        "fk_interview_participants_user_id", "interview_participants", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_interview_participants_interview_id", "interview_participants", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_interview_participants_application_id", "interview_participants", type_="foreignkey"
    )
    op.drop_constraint("fk_evaluations_interview_id", "evaluations", type_="foreignkey")
    op.drop_constraint("fk_evaluations_evaluator_id", "evaluations", type_="foreignkey")
    op.drop_constraint("fk_evaluations_application_id", "evaluations", type_="foreignkey")
    op.drop_constraint(
        "fk_application_stage_history_stage_id", "application_stage_history", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_application_stage_history_changed_by", "application_stage_history", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_application_stage_history_application_id",
        "application_stage_history",
        type_="foreignkey",
    )
    op.drop_constraint("fk_application_scores_model_id", "application_scores", type_="foreignkey")
    op.drop_constraint("fk_application_scores_created_by", "application_scores", type_="foreignkey")
    op.drop_constraint(
        "fk_application_scores_application_id", "application_scores", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_vacancy_assignments_vacancy_id", "vacancy_assignments", type_="foreignkey"
    )
    op.drop_constraint("fk_vacancy_assignments_user_id", "vacancy_assignments", type_="foreignkey")
    op.drop_constraint("fk_test_attempts_graded_by", "test_attempts", type_="foreignkey")
    op.drop_constraint("fk_test_attempts_assignment_id", "test_attempts", type_="foreignkey")
    op.drop_constraint("fk_tasks_vacancy_id", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_created_by", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_assigned_to", "tasks", type_="foreignkey")
    op.drop_constraint("fk_tasks_application_id", "tasks", type_="foreignkey")
    op.drop_constraint(
        "fk_scoring_model_versions_vacancy_id", "scoring_model_versions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_scoring_model_versions_created_by", "scoring_model_versions", type_="foreignkey"
    )
    op.drop_constraint("fk_referrals_vacancy_id", "referrals", type_="foreignkey")
    op.drop_constraint("fk_referrals_referred_by", "referrals", type_="foreignkey")
    op.drop_constraint("fk_referrals_candidate_id", "referrals", type_="foreignkey")
    op.drop_constraint("fk_pipeline_stages_vacancy_id", "pipeline_stages", type_="foreignkey")
    op.drop_constraint("fk_interviews_vacancy_id", "interviews", type_="foreignkey")
    op.drop_constraint("fk_interviews_created_by", "interviews", type_="foreignkey")
    op.drop_constraint("fk_audit_logs_vacancy_id", "audit_logs", type_="foreignkey")
    op.drop_constraint("fk_audit_logs_user_id", "audit_logs", type_="foreignkey")
    op.drop_constraint("fk_approvals_vacancy_id", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approvals_request_id", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approvals_offer_id", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approvals_delegated_from", "approvals", type_="foreignkey")
    op.drop_constraint("fk_approvals_approver_id", "approvals", type_="foreignkey")
    op.drop_constraint("fk_vacancies_request_id", "vacancies", type_="foreignkey")
    op.drop_constraint("fk_vacancies_recruiter_id", "vacancies", type_="foreignkey")
    op.drop_constraint("fk_vacancies_org_unit_id", "vacancies", type_="foreignkey")
    op.drop_constraint("fk_vacancies_manager_id", "vacancies", type_="foreignkey")
    op.drop_constraint("fk_test_assignments_created_by", "test_assignments", type_="foreignkey")
    op.drop_constraint("fk_test_assignments_assessment_id", "test_assignments", type_="foreignkey")
    op.drop_constraint("fk_test_assignments_application_id", "test_assignments", type_="foreignkey")
    op.drop_constraint("fk_talent_pool_members_pool_id", "talent_pool_members", type_="foreignkey")
    op.drop_constraint(
        "fk_talent_pool_members_candidate_id", "talent_pool_members", type_="foreignkey"
    )
    op.drop_constraint("fk_talent_pool_members_added_by", "talent_pool_members", type_="foreignkey")
    op.drop_constraint("fk_survey_responses_survey_id", "survey_responses", type_="foreignkey")
    op.drop_constraint("fk_survey_responses_candidate_id", "survey_responses", type_="foreignkey")
    op.drop_constraint(
        "fk_data_subject_requests_handled_by", "data_subject_requests", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_data_subject_requests_candidate_id", "data_subject_requests", type_="foreignkey"
    )
    op.drop_constraint("fk_consents_notice_id", "consents", type_="foreignkey")
    op.drop_constraint("fk_consents_candidate_id", "consents", type_="foreignkey")
    op.drop_constraint("fk_config_revisions_record_id", "config_revisions", type_="foreignkey")
    op.drop_constraint("fk_config_revisions_created_by", "config_revisions", type_="foreignkey")
    op.drop_constraint(
        "fk_candidate_sensitive_candidate_id", "candidate_sensitive", type_="foreignkey"
    )
    op.drop_constraint("fk_candidate_labels_user_id", "candidate_labels", type_="foreignkey")
    op.drop_constraint("fk_candidate_labels_candidate_id", "candidate_labels", type_="foreignkey")
    op.drop_constraint(
        "fk_automation_executions_rule_id", "automation_executions", type_="foreignkey"
    )
    op.drop_constraint("fk_webhooks_created_by", "webhooks", type_="foreignkey")
    op.drop_constraint("fk_vacancy_requests_requested_by", "vacancy_requests", type_="foreignkey")
    op.drop_constraint("fk_vacancy_requests_org_unit_id", "vacancy_requests", type_="foreignkey")
    op.drop_constraint("fk_user_roles_user_id", "user_roles", type_="foreignkey")
    op.drop_constraint("fk_user_roles_role_id", "user_roles", type_="foreignkey")
    op.drop_constraint("fk_talent_pools_created_by", "talent_pools", type_="foreignkey")
    op.drop_constraint("fk_offers_created_by", "offers", type_="foreignkey")
    op.drop_constraint("fk_offers_application_id", "offers", type_="foreignkey")
    op.drop_constraint("fk_notifications_user_id", "notifications", type_="foreignkey")
    op.drop_constraint("fk_messages_sender_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_messages_application_id", "messages", type_="foreignkey")
    op.drop_constraint("fk_config_records_created_by", "config_records", type_="foreignkey")
    op.drop_constraint("fk_checklist_items_reviewed_by", "checklist_items", type_="foreignkey")
    op.drop_constraint("fk_checklist_items_application_id", "checklist_items", type_="foreignkey")
    op.drop_constraint("fk_candidates_user_id", "candidates", type_="foreignkey")
    op.drop_constraint("fk_candidates_merged_into_id", "candidates", type_="foreignkey")
    op.drop_constraint("fk_auth_tokens_user_id", "auth_tokens", type_="foreignkey")
    op.drop_constraint("fk_auth_sessions_user_id", "auth_sessions", type_="foreignkey")
    op.drop_constraint("fk_assessments_created_by", "assessments", type_="foreignkey")
    op.drop_constraint("fk_users_org_unit_id", "users", type_="foreignkey")
    op.drop_constraint("fk_role_permissions_role_id", "role_permissions", type_="foreignkey")
    op.drop_constraint("fk_role_permissions_permission", "role_permissions", type_="foreignkey")
    op.drop_constraint("fk_org_units_parent_id", "org_units", type_="foreignkey")
    op.drop_constraint("fk_documents_uploaded_by", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_reviewed_by", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_request_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_candidate_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_application_id", "documents", type_="foreignkey")
    op.drop_constraint("fk_applications_vacancy_id", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_stage_id", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_cv_id", "applications", type_="foreignkey")
    op.drop_constraint("fk_applications_candidate_id", "applications", type_="foreignkey")
    op.drop_index(op.f("ix_interview_participants_user_id"), table_name="interview_participants")
    op.drop_index(
        op.f("ix_interview_participants_interview_id"), table_name="interview_participants"
    )
    op.drop_table("interview_participants")
    op.drop_index(op.f("ix_evaluations_evaluator_id"), table_name="evaluations")
    op.drop_index(op.f("ix_evaluations_application_id"), table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index(
        op.f("ix_application_stage_history_application_id"), table_name="application_stage_history"
    )
    op.drop_table("application_stage_history")
    op.drop_index(op.f("ix_application_scores_application_id"), table_name="application_scores")
    op.drop_table("application_scores")
    op.drop_index(op.f("ix_vacancy_assignments_vacancy_id"), table_name="vacancy_assignments")
    op.drop_index(op.f("ix_vacancy_assignments_user_id"), table_name="vacancy_assignments")
    op.drop_table("vacancy_assignments")
    op.drop_index(op.f("ix_test_attempts_assignment_id"), table_name="test_attempts")
    op.drop_table("test_attempts")
    op.drop_index(op.f("ix_tasks_vacancy_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_due_at"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_assigned_to"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_scoring_model_versions_vacancy_id"), table_name="scoring_model_versions")
    op.drop_table("scoring_model_versions")
    op.drop_index(op.f("ix_referrals_vacancy_id"), table_name="referrals")
    op.drop_table("referrals")
    op.drop_index(op.f("ix_pipeline_stages_vacancy_id"), table_name="pipeline_stages")
    op.drop_table("pipeline_stages")
    op.drop_index(op.f("ix_interviews_vacancy_id"), table_name="interviews")
    op.drop_index(op.f("ix_interviews_starts_at"), table_name="interviews")
    op.drop_table("interviews")
    op.drop_index(op.f("ix_audit_logs_vacancy_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_entity_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_approvals_vacancy_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_request_id"), table_name="approvals")
    op.drop_index(op.f("ix_approvals_offer_id"), table_name="approvals")
    op.drop_table("approvals")
    op.drop_index(op.f("ix_vacancies_title"), table_name="vacancies")
    op.drop_index(op.f("ix_vacancies_status"), table_name="vacancies")
    op.drop_index(op.f("ix_vacancies_recruiter_id"), table_name="vacancies")
    op.drop_index(op.f("ix_vacancies_org_unit_id"), table_name="vacancies")
    op.drop_table("vacancies")
    op.drop_index(op.f("ix_test_assignments_application_id"), table_name="test_assignments")
    op.drop_table("test_assignments")
    op.drop_index(op.f("ix_talent_pool_members_pool_id"), table_name="talent_pool_members")
    op.drop_index(op.f("ix_talent_pool_members_candidate_id"), table_name="talent_pool_members")
    op.drop_table("talent_pool_members")
    op.drop_table("survey_responses")
    op.drop_index(op.f("ix_data_subject_requests_candidate_id"), table_name="data_subject_requests")
    op.drop_table("data_subject_requests")
    op.drop_index(op.f("ix_consents_candidate_id"), table_name="consents")
    op.drop_table("consents")
    op.drop_index(op.f("ix_config_revisions_record_id"), table_name="config_revisions")
    op.drop_table("config_revisions")
    op.drop_table("candidate_sensitive")
    op.drop_index(op.f("ix_candidate_labels_candidate_id"), table_name="candidate_labels")
    op.drop_table("candidate_labels")
    op.drop_table("automation_executions")
    op.drop_table("webhooks")
    op.drop_index(op.f("ix_vacancy_requests_status"), table_name="vacancy_requests")
    op.drop_index(op.f("ix_vacancy_requests_requested_by"), table_name="vacancy_requests")
    op.drop_index(op.f("ix_vacancy_requests_org_unit_id"), table_name="vacancy_requests")
    op.drop_table("vacancy_requests")
    op.drop_table("user_roles")
    op.drop_table("talent_pools")
    op.drop_index(op.f("ix_offers_application_id"), table_name="offers")
    op.drop_table("offers")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_messages_application_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_config_records_kind"), table_name="config_records")
    op.drop_table("config_records")
    op.drop_index(op.f("ix_checklist_items_application_id"), table_name="checklist_items")
    op.drop_table("checklist_items")
    op.drop_index(op.f("ix_candidates_phone"), table_name="candidates")
    op.drop_table("candidates")
    op.drop_index(op.f("ix_auth_tokens_user_id"), table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_previous_hash"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("assessments")
    op.drop_table("users")
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_index(op.f("ix_outbox_status"), table_name="outbox")
    op.drop_index(op.f("ix_outbox_kind"), table_name="outbox")
    op.drop_table("outbox")
    op.drop_index(op.f("ix_org_units_parent_id"), table_name="org_units")
    op.drop_table("org_units")
    op.drop_index(op.f("ix_documents_sha256"), table_name="documents")
    op.drop_index(op.f("ix_documents_candidate_id"), table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_applications_vacancy_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_status"), table_name="applications")
    op.drop_index(op.f("ix_applications_stage_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_candidate_id"), table_name="applications")
    op.drop_table("applications")
