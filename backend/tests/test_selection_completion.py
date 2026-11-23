import pytest
from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.models import Application, Candidate, Outbox, PipelineStage, StageHistory, Vacancy


@pytest.mark.parametrize("email_enabled", [True, False])
def test_last_approval_rejects_only_remaining_people_and_prepares_emails(client, db, actors, monkeypatch, email_enabled):
    from types import SimpleNamespace

    vacancy_data, notice, _, _ = setup_vacancy(client, actors)
    vacancy = db.get(Vacancy, vacancy_data["id"])
    vacancy.quantity = 2
    for stage in db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy.id)):
        stage.required = False
    applications = []
    for _ in range(6):
        owner, profile, _ = register_candidate(client, notice)
        candidate = db.get(Candidate, profile["id"])
        candidate.profile = {"facts": {"experience_years": 10}}
        db.commit()
        application = call(client, "post", "/applications", owner,
            {"vacancy_id": vacancy.id, "enrollment": True}, 201)
        applications.append(db.get(Application, application["id"]))
    applications[3].status = "RESERVE"
    applications[4].status = "WITHDRAWN"
    applications[5].status = "HIRED"
    # One position is already occupied by the hired candidate.
    vacancy.quantity = 3
    db.commit()
    monkeypatch.setattr("app.services.rejection_feedback.smtp_runtime",
        lambda db: SimpleNamespace(enabled=email_enabled))
    admin = actors["admin"]["headers"]
    first = call(client, "post", "/applications/" + applications[0].id + "/decision", admin,
        {"version": applications[0].version, "decision": "SELECTED", "reason": "Perfil aprovado pelo RH"})
    assert first["remaining_rejected"] == 0
    assert applications[2].status == "ACTIVE"
    assert applications[3].status == "RESERVE"
    last = call(client, "post", "/applications/" + applications[1].id + "/decision", admin,
        {"version": applications[1].version, "decision": "SELECTED", "reason": "Perfil aprovado pelo RH"})
    assert last["remaining_rejected"] == 2
    assert [item.status for item in applications] == ["SELECTED", "SELECTED", "REJECTED", "REJECTED", "WITHDRAWN", "HIRED"]
    for application in applications[2:4]:
        assert application.closed_at
        assert not db.scalar(select(StageHistory.id).where(StageHistory.application_id == application.id,
            StageHistory.left_at.is_(None)))
        entry = db.scalar(select(Outbox).where(Outbox.dedup_key == "rejection-feedback:" + application.id))
        assert entry and entry.status == "PENDING"
    for application in applications[:2] + applications[4:]:
        assert not db.scalar(select(Outbox.id).where(Outbox.dedup_key == "rejection-feedback:" + application.id))
    response = client.post("/api/v1/applications/" + applications[1].id + "/decision", headers=admin,
        json={"version": applications[1].version, "decision": "SELECTED", "reason": "Tentativa duplicada pelo RH"})
    assert response.status_code == 409
