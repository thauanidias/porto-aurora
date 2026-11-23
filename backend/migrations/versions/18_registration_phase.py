"""Represent registration explicitly without moving existing applications."""
from alembic import op

revision = "18_registration_phase"
down_revision = "17_process_workflow"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("candidate_phase_valid", "pipeline_stages", type_="check")
    op.create_check_constraint("candidate_phase_valid", "pipeline_stages",
        "candidate_phase IS NULL OR candidate_phase IN ('REGISTER', 'RECRUITMENT', 'SELECTION', 'FORM', 'INTERVIEW', 'TEST', 'ADMISSION')")


def downgrade():
    op.execute("UPDATE pipeline_stages SET candidate_phase = 'RECRUITMENT' WHERE candidate_phase = 'REGISTER'")
    op.drop_constraint("candidate_phase_valid", "pipeline_stages", type_="check")
    op.create_check_constraint("candidate_phase_valid", "pipeline_stages",
        "candidate_phase IS NULL OR candidate_phase IN ('RECRUITMENT', 'SELECTION', 'FORM', 'INTERVIEW', 'TEST', 'ADMISSION')")
