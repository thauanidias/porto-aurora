from datetime import timedelta

import pytest
from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.core.db import utcnow
from app.core.permissions import Actor
from app.models import (
    Application,
    Candidate,
    PipelineStage,
    Role,
    StageHistory,
    User,
    UserRole,
    Vacancy,
)
from app.services.talent_bank import compatible_profile, enroll_talents


@pytest.mark.parametrize("audience", ["INTERNAL", "EXTERNAL", "BOTH"])
def test_automatic_enrollment_respects_audience_consent_and_history(client, db, actors, audience):
    vacancy_data, notice, _, _ = setup_vacancy(client, actors)
    vacancy = db.get(Vacancy, vacancy_data["id"])
    vacancy.audience = audience
    previous_data, _, _, _ = setup_vacancy(client, actors)
    previous_stage = db.scalar(select(PipelineStage.id)
        .where(PipelineStage.vacancy_id == previous_data["id"]).limit(1))
    candidates = []
    for index in range(9):
        headers, data, _ = register_candidate(client, notice)
        candidate = db.get(Candidate, data["id"])
        candidate.profile = {"facts": {"experience_years": 10 if index != 2 else 0}}
        candidate.talent_consent_until = utcnow() + timedelta(days=30) if index != 3 else None
        if index == 0:
            role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
            db.add(UserRole(user_id=candidate.user_id, role_id=role.id))
        if index != 5:
            status = {6: "ACTIVE", 7: "HIRED", 8: "WITHDRAWN"}.get(index, "REJECTED")
            db.add(Application(candidate_id=candidate.id, vacancy_id=previous_data["id"],
                stage_id=previous_stage, status=status, profile_snapshot={}, stage_entered_at=utcnow()))
        candidates.append((headers, candidate))
    # An earlier application is retained and never reactivated or duplicated.
    stage_id = db.scalar(select(PipelineStage.id)
        .where(PipelineStage.vacancy_id == vacancy.id).limit(1))
    old = Application(candidate_id=candidates[4][1].id, vacancy_id=vacancy.id, stage_id=stage_id,
        status="REJECTED", profile_snapshot={}, stage_entered_at=utcnow())
    db.add(old)
    db.flush()
    admin = db.get(User, actors["admin"]["id"])
    actor = Actor(admin, {"vacancy.publish"}, "test", "", "test")
    expected = 2 if audience == "BOTH" else 1
    vacancy.status = "PAUSED"
    db.commit()
    call(client, "post", "/vacancies/" + vacancy.id + "/status", actors["admin"]["headers"],
         {"status": "PUBLISHED", "version": vacancy.version})
    automatic = db.scalars(select(Application).where(Application.vacancy_id == vacancy.id,
        Application.source == "BANCO_TALENTOS")).all()
    assert len(automatic) == expected
    assert enroll_talents(db, actor, vacancy) == 0
    assert old.status == "REJECTED"
    bank = call(client, "get", "/candidates?talent_bank=true", actors["admin"]["headers"])
    bank_ids = {item["id"] for item in bank["items"]}
    assert all(candidate.id in bank_ids for _, candidate in candidates[:5])
    assert all(candidate.id not in bank_ids for _, candidate in candidates[5:])
    assert not any(item.candidate_id in {c.id for _, c in candidates[5:]} for item in automatic)
    for headers, candidate in candidates[:2]:
        applications = call(client, "get", "/applications", headers)["items"]
        relevant = [item for item in applications if item["vacancy_id"] == vacancy.id]
        internal = candidate == candidates[0][1]
        eligible = audience == "BOTH" or audience == ("INTERNAL" if internal else "EXTERNAL")
        assert len(relevant) == int(eligible)
        if eligible:
            assert relevant[0]["recruitment_type"] == ("INTERNAL" if internal else "EXTERNAL")
            assert db.scalar(select(StageHistory.id).where(StageHistory.application_id == relevant[0]["id"]))
    listing = call(client, "get", "/candidates?recruitment_type=INTERNAL", actors["admin"]["headers"])
    assert candidates[0][1].id in {item["id"] for item in listing["items"]}
    assert candidates[1][1].id not in {item["id"] for item in listing["items"]}
    vacancy.confidential = True
    assert enroll_talents(db, actor, vacancy) == 0


def test_manual_model_does_not_enroll_everyone():
    criterion = {"key": "manual", "name": "Análise manual", "field": "skills",
        "kind": "MULTI_CHOICE", "weight": 100, "expected": ["Manual"],
        "not_applicable": True, "justification": "Avaliação manual"}
    assert not compatible_profile([criterion], {"skills": ["Manual"]})
