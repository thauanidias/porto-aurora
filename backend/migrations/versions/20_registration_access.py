"""Allow RH roles to consult recruitment forms within their existing candidate scope."""
from alembic import op

revision = "20_registration_access"
down_revision = "19_directory_sessions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("INSERT INTO permissions (name,description) VALUES ('candidate.registration.view','Consultar fichas de inscrição dos candidatos vinculados') ON CONFLICT DO NOTHING")
    op.execute("INSERT INTO role_permissions (role_id,permission) SELECT id,'candidate.registration.view' FROM roles WHERE name IN ('SUPER_ADMIN','RH_ADMIN','RECRUTADOR','ANALISTA_RH') ON CONFLICT DO NOTHING")


def downgrade():
    op.execute("DELETE FROM role_permissions WHERE permission='candidate.registration.view'")
    op.execute("DELETE FROM permissions WHERE name='candidate.registration.view'")
