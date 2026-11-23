from uuid import uuid4

import pytest
from sqlalchemy import select
from test_candidate_journey import journey_owner  # noqa: F401
from test_integration import call

from app.models import Candidate, Document, Outbox, Role, StageReview, UserRole, Vacancy


@pytest.fixture(params=[False, True])
def screening_case(client, db, journey_owner, request):  # noqa: F811
    owner, job, admin, _ = journey_owner
    person = call(client, "get", "/candidates/me", owner)
    candidate = db.get(Candidate, person["id"])
    candidate.phone, candidate.city, candidate.state, candidate.country = "91999999999", "Belém", "PA", "BR"
    candidate.profile = {"education": [{"course": "Ensino médio"}], "skills": ["Logística"], "shift": "Manhã"}
    db.add(Document(candidate_id=candidate.id, uploaded_by=candidate.user_id, type_name="CURRICULO",
                    filename="teste.pdf", storage_key=uuid4().hex, sha256="a" * 64, size=20,
                    mime="application/pdf", revision=1, scan_status="CLEAN", status="APPROVED"))
    if request.param:
        db.get(Vacancy, job["id"]).audience = "INTERNAL"
        role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
        db.add(UserRole(user_id=candidate.user_id, role_id=role.id))
    db.commit()
    application = call(client, "post", "/applications", owner, {"vacancy_id": job["id"], "enrollment": True}, 201)
    stage = next(item for item in job["stages"] if item["candidate_phase"] == "SELECTION")
    path = "/applications/" + application["id"]
    application = call(client, "post", path + "/move", admin, {"stage_id": stage["id"], "version": application["version"]})
    return owner, job, admin, application, candidate


def test_approve_screening_atomically_moves_out_of_queue(client, db, screening_case, actors):
    owner, job, admin, application, _ = screening_case
    path = "/applications/" + application["id"] + "/approve-screening"
    payload = {"version": application["version"], "reason": "Atende aos requisitos profissionais da vaga"}
    approved_list = "/applications?vacancy_id=" + job["id"] + "&passed_screening=true"
    assert call(client, "get", approved_list, admin)["total"] == 0
    call(client, "post", path, owner, payload, 403)
    call(client, "post", path, actors["outsider"]["headers"], payload, 403)
    updated = call(client, "post", path, admin, payload)
    assert updated["candidate_access"]["phase"] == "INTERVIEW"
    assert call(client, "get", approved_list, admin)["items"][0]["id"] == application["id"]
    assert call(client, "get", approved_list + "&group_by_vacancy=true", admin)["items"][0]["application_count"] == 1
    reviews = list(db.scalars(select(StageReview).where(StageReview.application_id == application["id"])))
    assert len(reviews) == 1 and reviews[0].status == "APPROVED"
    queue = call(client, "get", "/applications?vacancy_id=" + job["id"] + "&screening_only=true", admin)
    assert queue["total"] == 0
    call(client, "post", path, admin, payload, 409)
    assert call(client, "get", "/candidates/me/journey", owner)["sections"]["interviews"]["enabled"]
    call(client, "post", "/applications/" + application["id"] + "/decision", admin,
         {"version": updated["version"], "decision": "REJECTED", "reason": "Encerramento fictício após triagem"})
    assert call(client, "get", approved_list, admin)["total"] == 0


def test_screening_ranking_is_paginated_and_scoped_to_rh(client, screening_case, actors):
    owner, job, admin, application, _ = screening_case
    path = "/applications?vacancy_id=" + job["id"] + "&screening_only=true&order_by=compatibility&page_size=1"
    result = call(client, "get", path, admin)
    assert result["total"] == 1 and result["items"][0]["id"] == application["id"]
    assert result["items"][0]["compatibility_rank"] is None
    assert call(client, "get", path, actors["outsider"]["headers"])["total"] == 0
    call(client, "get", path, owner, expected=403)
    assert call(client, "get", path + "&page_number=2", admin)["items"] == []


def test_grouped_vacancies_count_only_authorized_matching_applications(client, screening_case, actors):
    owner, job, admin, application, _ = screening_case
    path = "/applications?group_by_vacancy=true&recruitment_type=" + application["recruitment_type"]
    result = call(client, "get", path, admin)
    assert result["total"] == 1
    assert result["items"][0]["id"] == job["id"]
    assert result["items"][0]["application_count"] == 1
    assert "candidate" not in result["items"][0]
    assert call(client, "get", path, actors["outsider"]["headers"])["total"] == 0
    call(client, "get", path, owner, expected=403)


def test_directory_rank_includes_other_pages_and_ignores_search_for_position(client, db, screening_case):
    from app.core.db import utcnow
    from app.models import Application, ApplicationScore, ScoringVersion, User
    _, job, admin, application, candidate = screening_case
    vacancy = db.get(Vacancy, job["id"])
    user = User(name="Outra Pessoa Fictícia", email=uuid4().hex + "@example.invalid", kind="CANDIDATO")
    db.add(user)
    db.flush()
    other = Candidate(user_id=user.id, name=user.name, email=user.email)
    db.add(other)
    db.flush()
    competitor = Application(candidate_id=other.id, vacancy_id=job["id"], stage_id=application["stage_id"], stage_entered_at=utcnow(), recruitment_type=application["recruitment_type"])
    model = ScoringVersion(vacancy_id=job["id"], number=99, criteria=[{"key": "demo", "name": "Experiência", "field": "experience_years", "kind": "NUMBER_MIN", "weight": 100, "expected": 2, "justification": "Teste de ranking"}], composition={"OBJECTIVE": 100}, created_by=vacancy.recruiter_id)
    db.add_all([competitor, model])
    db.flush()
    for row, total in [(application, 85), ({"id": competitor.id}, 95)]:
        db.add(ApplicationScore(application_id=row["id"], model_id=model.id, total=total, knockout=False, created_by=vacancy.recruiter_id,
            breakdown={"items": [{"name": "Experiência", "applicable": True, "value": 2}], "pending_components": []}))
    db.commit()
    path = "/applications?include_ranking=true&page_size=1&q=" + candidate.name + "&recruitment_type=" + application["recruitment_type"]
    result = call(client, "get", path, admin)
    assert result["total"] == 1 and result["items"][0]["compatibility_rank"] == 2
    rejected = call(client, "post", "/applications/" + application["id"] + "/decision", admin,
        {"version": application["version"], "decision": "REJECTED", "reason": "Encerramento fictício para teste"})
    assert rejected["status"] == "REJECTED"
    assert call(client, "get", path, admin)["items"][0]["compatibility_rank"] is None


def test_failed_advance_rolls_back_review_and_keeps_queue(client, db, screening_case):
    _, job, admin, application, _ = screening_case
    db.get(Vacancy, job["id"]).status = "CLOSED"
    db.commit()
    call(client, "post", "/applications/" + application["id"] + "/approve-screening", admin,
         {"version": application["version"], "reason": "Perfil conferido pelo RH"}, 409)
    assert not db.scalar(select(StageReview.id).where(StageReview.application_id == application["id"]))
    assert call(client, "get", "/applications/" + application["id"], admin)["stage_id"] == application["stage_id"]


def test_screening_rejection_queues_return_without_internal_reason(client, db, screening_case, monkeypatch):
    from types import SimpleNamespace
    _, job, admin, application, candidate = screening_case
    monkeypatch.setattr("app.services.rejection_feedback.smtp_runtime", lambda db: SimpleNamespace(enabled=True))
    path = "/applications/" + application["id"] + "/decision"
    payload = {"version": application["version"], "decision": "REJECTED", "reason": "Análise interna reservada do RH", "send_rejection_email": True}
    call(client, "post", path, admin, payload)
    entry = db.scalar(select(Outbox).where(Outbox.dedup_key == "rejection-feedback:" + application["id"]))
    assert entry and entry.payload["recipient"] == candidate.email
    assert "sua candidatura não avançará nesta seleção" in entry.payload["body"]
    assert payload["reason"] not in entry.payload["body"]
    assert db.get(Candidate, candidate.id)
    call(client, "post", path, admin, payload, 409)


@pytest.mark.parametrize("internal", [False, True])
def test_rh_release_updates_only_the_target_application_and_owner_panel(
    client, db, journey_owner, actors, internal  # noqa: F811
):
    owner, job, admin, _ = journey_owner
    person = call(client, "get", "/candidates/me", owner)
    candidate = db.get(Candidate, person["id"])
    candidate.phone = "91999999999"
    candidate.city = "Belém"
    candidate.state = "PA"
    candidate.country = "BR"
    candidate.profile = {"education": [{"course": "Ensino médio"}],
                         "skills": ["Operação"], "shift": "Manhã"}
    db.add(Document(candidate_id=candidate.id, uploaded_by=candidate.user_id,
                    type_name="CURRICULO", filename="teste.pdf", storage_key=uuid4().hex,
                    sha256="a" * 64, size=20, mime="application/pdf", revision=1,
                    scan_status="CLEAN", status="APPROVED"))
    if internal:
        db.get(Vacancy, job["id"]).audience = "INTERNAL"
        role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
        db.add(UserRole(user_id=candidate.user_id, role_id=role.id))
    db.commit()
    application = call(client, "post", "/applications", owner,
                       {"vacancy_id": job["id"], "enrollment": True}, 201)
    assert application["recruitment_type"] == ("INTERNAL" if internal else "EXTERNAL")
    path = "/applications/" + application["id"]
    interview = next(stage for stage in job["stages"] if stage["kind"] == "INTERVIEW")
    payload = {"stage_id": interview["id"], "version": application["version"],
               "reason": "Liberação explícita do RH"}
    call(client, "post", path + "/move", owner, payload, 403)
    call(client, "post", path + "/move", actors["outsider"]["headers"], payload, 403)
    before = call(client, "get", "/candidates/me/journey", owner)
    assert not before["sections"]["interviews"]["enabled"]
    updated = call(client, "post", path + "/move", admin, payload)
    assert updated["candidate_access"]["permissions"]["interviews"]
    after = call(client, "get", "/candidates/me/journey", owner)
    assert after["sections"]["interviews"]["enabled"]
    assert not after["sections"]["tests"]["enabled"]
    call(client, "post", path + "/move", admin, payload, 409)
    current = call(client, "get", path, admin)
    call(client, "post", path + "/stage-reviews", admin,
         {"status": "APPROVED", "reason": "Atende aos requisitos profissionais da etapa",
          "version": current["version"]}, 201)
    current = call(client, "get", path, admin)
    assert current["screening_review"]["status"] == "APPROVED"
    assert current["status"] == "ACTIVE"
    call(client, "post", path + "/decision", admin,
         {"decision": "REJECTED", "reason": "Requisito profissional da vaga não comprovado",
          "version": current["version"], "send_rejection_email": False})
    closed = call(client, "get", path, admin)
    assert closed["status"] == "REJECTED"
    assert db.get(Candidate, candidate.id) is not None
    assert db.scalar(select(Document.id).where(Document.candidate_id == candidate.id))
    archived = call(client, "get", "/applications?vacancy_id=" + job["id"] + "&status=REJECTED", admin)
    assert application["id"] in {item["id"] for item in archived["items"]}
