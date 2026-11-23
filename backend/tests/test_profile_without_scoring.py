from uuid import uuid4

from sqlalchemy import func, select
from test_candidate_journey import register_basic_candidate
from test_integration import call

from app.core.db import utcnow
from app.models import Application, ApplicationScore, PipelineStage, Vacancy


def test_profile_save_updates_snapshot_without_a_scoring_model(client, db, actors):
    owner, person, _ = register_basic_candidate(client)
    code = uuid4().hex
    vacancy = Vacancy(code=code, slug=code, title="Vaga sem modelo", org_unit_id=actors["org"],
                      recruiter_id=actors["admin"]["id"], manager_id=actors["manager"]["id"],
                      quantity=1, status="PUBLISHED", description="Vaga ficticia sem modelo configurado")
    db.add(vacancy)
    db.flush()
    stage = PipelineStage(vacancy_id=vacancy.id, name="Recrutamento", position=0,
                          kind="SCREENING", candidate_phase="RECRUITMENT")
    db.add(stage)
    db.flush()
    application = Application(candidate_id=person["id"], vacancy_id=vacancy.id, stage_id=stage.id,
                              stage_entered_at=utcnow(), profile_snapshot={})
    db.add(application)
    db.commit()
    saved = call(client, "put", "/candidates/me", owner,
                 {"name": "Pessoa atualizada", "city": "Belem", "state": "PA",
                  "phone": "91999999999", "profile": {"skills": ["Logistica"]}, "version": person["version"]})
    assert saved["profile"]["skills"] == ["Logistica"]
    assert db.get(Application, application.id).profile_snapshot["skills"] == ["Logistica"]
    assert db.scalar(select(func.count()).select_from(ApplicationScore).where(ApplicationScore.application_id == application.id)) == 0
