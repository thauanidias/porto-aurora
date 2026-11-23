from datetime import timedelta
from uuid import uuid4

import pytest
from consent_helpers import consent_signature
from sqlalchemy import delete, select, text
from test_integration import call

from app.core.db import utcnow
from app.models import Application, Notification, PipelineStage, StageHistory


def register_basic_candidate(client):
    address = "journey-" + uuid4().hex[:8] + "@example.com"
    registration = call(client, "post", "/auth/register", {}, {
        "name": "Pessoa da Jornada", "email": address, "consent": False,
        "defer_consent_to_profile": True,
    }, 201)
    token = registration["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    session = call(client, "post", "/auth/consume-link", {}, {"token": token, "password": "Jt42!?"})
    owner = {"Authorization": "Bearer " + session["access_token"]}
    call(client, "post", "/public/consent-receipts", owner, {"name": "Pessoa da Jornada", "email": address,
         "context": "CADASTRO", "accepted": True, "read_to_end": True}, 201)
    return owner, call(client, "get", "/candidates/me", owner), address


@pytest.fixture
def journey_owner(client, actors):
    admin = actors["admin"]["headers"]
    notice = call(client, "post", "/configuration/privacy-notices", admin, {
        "name": "Privacidade " + uuid4().hex[:6], "reason": "Teste do fluxo por etapas",
        "data": {"text": "Dados utilizados neste processo seletivo de teste.",
                 "purpose": "Recrutamento", "contact": "privacy@example.com", "talent_months": 12},
    }, 201)

    def vacancy():
        result = call(client, "post", "/vacancies", admin, {
            "title": "Operador " + uuid4().hex[:6], "org_unit_id": actors["org"],
            "recruiter_id": actors["admin"]["id"], "manager_id": actors["manager"]["id"],
            "description": "Processo seletivo com atividades liberadas por etapa.",
            "city": "Belém", "state": "PA", "quantity": 1, "publish_on_save": False,
            "deadline": (utcnow() + timedelta(days=30)).isoformat(),
            "details": {"notice_id": notice["id"], "requirements": "Competências profissionais da função", "questions": [
                {"key": "interest", "label": "Por que deseja participar?", "kind": "TEXT", "required": True},
            ]},
        }, 201)
        # Keep coverage for pre-existing custom pipelines without the new strict gates.
        call(client, "put", "/vacancies/" + result["id"] + "/pipeline", admin, {
            "version": result["version"], "stages": [
                {"name": name, "kind": kind, "candidate_phase": phase, "position": position}
                for position, (name, kind, phase) in enumerate([
                    ("Inscritos", "SCREENING", "RECRUITMENT"),
                    ("Seleção de currículo", "SCREENING", "SELECTION"),
                    ("Entrevista", "INTERVIEW", "INTERVIEW"), ("Testes", "TEST", "TEST"),
                    ("Finalistas", "FINALIST", "ADMISSION"), ("Proposta", "OFFER", "ADMISSION"),
                    ("Contratado", "HIRED", "ADMISSION"),
                ])],
        })
        draft = call(client, "get", "/vacancies/" + result["id"], admin)
        call(client, "post", "/vacancies/" + result["id"] + "/status", admin,
            {"version": draft["version"], "status": "PUBLISHED"})
        return call(client, "get", "/vacancies/" + result["id"], admin)

    job = vacancy()
    owner, _, _ = register_basic_candidate(client)
    return owner, job, admin, vacancy


def enroll(client, owner, job):
    from readiness_helpers import ready_candidate
    ready_candidate(client, owner)
    return call(client, "post", "/applications", owner, {"vacancy_id": job["id"], "enrollment": True}, 201)


def advance(client, admin, application, job, kind):
    stage = next(stage for stage in job["stages"] if stage["kind"] == kind) if kind != "SELECTION" else job["stages"][1]
    current = call(client, "get", "/applications/" + application["id"], admin)
    return call(client, "post", "/applications/" + application["id"] + "/move", admin,
                {"stage_id": stage["id"], "version": current["version"]})


def test_registration_recruitment_selection_and_notices(client, db, journey_owner):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    application = advance(client, admin, application, job, "SELECTION")
    endpoint = "/candidates/me/journey"
    locked = call(client, "get", endpoint, owner)
    for section in ["selection_registration", "messages", "questions", "interviews", "tests", "admission"]:
        assert locked["sections"][section]["enabled"] is False
    call(client, "post", "/applications/" + application["id"] + "/stage-reviews", admin,
         {"version": application["version"], "status": "APPROVED", "reason": "Currículo aprovado pelo RH."}, 201)
    assert call(client, "get", endpoint, owner)["sections"]["selection_registration"]["enabled"] is False
    application = advance(client, admin, application, job, "INTERVIEW")
    access = call(client, "get", endpoint, owner)["sections"]
    assert not access["selection_registration"]["enabled"] and access["messages"]["enabled"]
    assert access["questions"]["enabled"] and access["interviews"]["enabled"]
    assert not access["tests"]["enabled"] and not access["admission"]["enabled"]
    application = advance(client, admin, application, job, "TEST")
    assert call(client, "get", endpoint, owner)["sections"]["tests"]["enabled"]
    assert not call(client, "get", endpoint, owner)["sections"]["admission"]["enabled"]

def test_tests_follow_each_application_and_relock_when_moved_back(client, journey_owner):
    owner, job, admin, another_vacancy = journey_owner
    application = enroll(client, owner, job)
    second_job = another_vacancy()
    second = enroll(client, owner, second_job)
    assessment = call(client, "post", "/tests", admin, {"name": "Teste da jornada",
        "questions": [{"key": "safe", "text": "Resposta correta?", "kind": "BOOLEAN", "correct": True}]}, 201)

    def assign(app, external=""):
        return call(client, "post", "/tests/" + assessment["id"] + "/assign", admin, {
            "application_id": app["id"], "opens_at": (utcnow() - timedelta(minutes=5)).isoformat(),
            "due_at": (utcnow() + timedelta(days=1)).isoformat(), "external_url": external,
        }, 201)

    first_test = assign(application)
    second_test = assign(second, "https://example.com/test")
    assert client.post("/api/v1/test-assignments/" + first_test["id"] + "/start", headers=owner).status_code == 403
    application = advance(client, admin, application, job, "INTERVIEW")
    assert client.post("/api/v1/test-assignments/" + first_test["id"] + "/start", headers=owner).status_code == 403
    application = advance(client, admin, application, job, "TEST")
    assert client.put("/api/v1/applications/" + second["id"] + "/questions", headers=owner,
        json={"version": second["version"], "answers": {"interest": "Outra vaga"}}).status_code == 403
    assert client.put("/api/v1/applications/" + application["id"] + "/questions", headers=owner,
        json={"version": application["version"], "answers": {"interest": "Aceite inicial já registrado"}}).status_code == 200
    available = call(client, "get", "/test-assignments", owner)["items"]
    assert next(item for item in available if item["id"] == first_test["id"])["stage_unlocked"] is True
    blocked = next(item for item in available if item["id"] == second_test["id"])
    assert blocked["stage_unlocked"] is False and "external_url" not in blocked["snapshot"]
    attempt = call(client, "post", "/test-assignments/" + first_test["id"] + "/start", owner)
    assert client.post("/api/v1/test-assignments/" + second_test["id"] + "/start", headers=owner).status_code == 403
    advance(client, admin, application, job, "INTERVIEW")
    assert client.post("/api/v1/test-attempts/" + attempt["id"] + "/submit", headers=owner,
        json={"version": attempt["version"], "answers": {"safe": True}}).status_code == 403
    assert not call(client, "get", "/candidates/me/journey", owner)["sections"]["tests"]["enabled"]


def test_rh_configures_access_without_replacing_pipeline_or_history(client, db, actors, journey_owner):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    stages = job["stages"]
    phases = {stage["id"]: "RECRUITMENT" for stage in stages}
    phases[stages[0]["id"]] = "SELECTION"
    payload = {"version": job["version"], "phases": phases}
    assert client.put("/api/v1/vacancies/" + job["id"] + "/candidate-flow",
                      headers=actors["manager"]["headers"], json=payload).status_code == 403
    call(client, "put", "/vacancies/" + job["id"] + "/candidate-flow", admin, payload)
    assert db.get(Application, application["id"]).stage_id == application["stage_id"]
    configured = call(client, "get", "/candidates/me/journey", owner)
    assert configured["sections"]["consent"]["enabled"]
    assert not configured["sections"]["questions"]["enabled"]
    other_owner, _, _ = register_basic_candidate(client)
    assert client.post("/api/v1/applications", headers=other_owner,
        json={"vacancy_id": job["id"], "notice_id": job["details"]["notice_id"],
              "consent": True, "answers": {"interest": "Resposta antes de testes"}}).status_code == 422
    current = call(client, "get", "/vacancies/" + job["id"], admin)
    assert {s["id"] for s in current["stages"]} == {s["id"] for s in stages}
    assert client.put("/api/v1/vacancies/" + job["id"] + "/candidate-flow", headers=admin,
        json={"version": current["version"], "phases": {"invalid": "TEST"}}).status_code == 422
    assert client.get("/api/v1/candidates/me/journey", headers=actors["admin"]["headers"]).status_code == 403
    assert client.get("/api/v1/candidates/me/journey").status_code == 401


@pytest.mark.parametrize("missing_stages", [False, True])
def test_existing_pipeline_migration_preserves_application_and_history(client, db, journey_owner, missing_stages):
    import importlib.util
    from pathlib import Path

    owner, job, _, _ = journey_owner
    application = enroll(client, owner, job)
    history_id = db.scalar(select(StageHistory.id).where(StageHistory.application_id == application["id"]))
    if missing_stages:
        db.execute(delete(PipelineStage).where(PipelineStage.vacancy_id == job["id"],
            PipelineStage.id.in_([job["stages"][0]["id"], next(s["id"] for s in job["stages"] if s["kind"] == "TEST")])))
    else:
        # Legacy pipelines placed tests before interviews.
        db.execute(text("UPDATE pipeline_stages SET position=position+100 WHERE vacancy_id=:id"), {"id": job["id"]})
        for position, stage in enumerate(sorted(job["stages"], key=lambda s: (0 if s["kind"] == "SCREENING" else 1 if s["kind"] == "TEST" else 2 if s["kind"] == "INTERVIEW" else 3, s["position"]))):
            db.execute(text("UPDATE pipeline_stages SET position=:p WHERE id=:id"), {"p": position, "id": stage["id"]})
    original = set(db.scalars(select(PipelineStage.id).where(PipelineStage.vacancy_id == job["id"])))
    spec = importlib.util.spec_from_file_location("candidate_journey_migration",
        Path(__file__).parents[1] / "migrations/versions/10_candidate_journey.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.migrate_existing_stages(db.connection())
    stages = db.execute(text("SELECT id, kind FROM pipeline_stages WHERE vacancy_id=:v ORDER BY position"), {"v": job["id"]}).mappings().all()
    assert original <= {stage["id"] for stage in stages}
    kinds = [stage["kind"] for stage in stages]
    assert kinds.count("SCREENING") >= 2
    assert kinds.index("INTERVIEW") < kinds.index("TEST")
    assert db.get(Application, application["id"]).stage_id == application["stage_id"]
    assert db.get(StageHistory, history_id).stage_id == application["stage_id"]
