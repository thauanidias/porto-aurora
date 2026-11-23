"""Explicit candidate access phase for each pipeline stage."""
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "10_candidate_journey"
down_revision = "09_vacancy_messages"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pipeline_stages", sa.Column("candidate_phase", sa.String(20), nullable=True))
    op.create_check_constraint("candidate_phase_valid", "pipeline_stages",
        "candidate_phase IS NULL OR candidate_phase IN ('RECRUITMENT', 'SELECTION', 'INTERVIEW', 'TEST', 'ADMISSION')")
    migrate_existing_stages(op.get_bind())


def migrate_existing_stages(connection):
    vacancy_ids = connection.execute(sa.text("SELECT DISTINCT vacancy_id FROM pipeline_stages")).scalars().all()
    ranks = {"SCREENING": 0, "INTERVIEW": 1, "TEST": 2, "FINALIST": 3, "OFFER": 4, "HIRED": 5}
    for vacancy_id in vacancy_ids:
        stages = [dict(row) for row in connection.execute(sa.text(
            "SELECT id, position, kind FROM pipeline_stages WHERE vacancy_id=:v ORDER BY position"), {"v": vacancy_id}).mappings()]
        screening_count = sum(row["kind"] == "SCREENING" for row in stages)
        missing = []
        if screening_count == 0:
            missing.append(("Inscritos", "SCREENING", "RECRUITMENT"))
        if screening_count < 2:
            missing.append(("Seleção de currículo", "SCREENING", "SELECTION"))
        if not any(row["kind"] == "INTERVIEW" for row in stages):
            missing.append(("Entrevistas", "INTERVIEW", "INTERVIEW"))
        if not any(row["kind"] == "TEST" for row in stages):
            missing.append(("Testes", "TEST", "TEST"))
        for name, kind, phase in missing:
            stage_id = str(uuid4())
            position = max(row["position"] for row in stages) + 1
            connection.execute(sa.text("""INSERT INTO pipeline_stages
                (id, vacancy_id, name, position, kind, candidate_phase, required, reveal_identity,
                 sla_hours, rules, version, created_at, updated_at)
                VALUES (:id, :v, :name, :p, :kind, :phase, false, true, 72, '{}'::jsonb, 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""),
                {"id": stage_id, "v": vacancy_id, "p": position, "name": name, "kind": kind, "phase": phase})
            stages.append({"id": stage_id, "position": position, "kind": kind})
        ordered = sorted(stages, key=lambda row: (ranks.get(row["kind"], 0), row["position"]))
        offset = max(row["position"] for row in stages) + len(stages) + 1
        connection.execute(sa.text("UPDATE pipeline_stages SET position=position+:offset WHERE vacancy_id=:v"),
                           {"offset": offset, "v": vacancy_id})
        for position, row in enumerate(ordered):
            connection.execute(sa.text("UPDATE pipeline_stages SET position=:p WHERE id=:id"),
                               {"p": position, "id": row["id"]})


def downgrade():
    op.drop_constraint("candidate_phase_valid", "pipeline_stages", type_="check")
    op.drop_column("pipeline_stages", "candidate_phase")
