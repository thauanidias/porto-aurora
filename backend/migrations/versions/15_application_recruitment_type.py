"""Separate internal and external applications while preserving their origin."""
import sqlalchemy as sa
from alembic import op

revision = "15_application_recruitment_type"
down_revision = "14_employee_email_code"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("applications", sa.Column("recruitment_type", sa.String(20), nullable=False, server_default="EXTERNAL"))
    op.execute("""
        UPDATE applications AS a SET recruitment_type = 'INTERNAL'
        FROM vacancies AS v, candidates AS c
        WHERE a.vacancy_id = v.id AND a.candidate_id = c.id AND (
            v.audience = 'INTERNAL' OR (v.audience = 'BOTH' AND EXISTS (
                SELECT 1 FROM user_roles ur JOIN role_permissions rp ON rp.role_id = ur.role_id
                WHERE ur.user_id = c.user_id AND rp.permission = 'internal.view'
            ))
        )
    """)
    op.create_check_constraint("application_recruitment_type_valid", "applications", "recruitment_type IN ('INTERNAL', 'EXTERNAL')")
    op.create_index("ix_applications_recruitment_type", "applications", ["recruitment_type"])


def downgrade():
    op.drop_index("ix_applications_recruitment_type", table_name="applications")
    op.drop_constraint("application_recruitment_type_valid", "applications", type_="check")
    op.drop_column("applications", "recruitment_type")
