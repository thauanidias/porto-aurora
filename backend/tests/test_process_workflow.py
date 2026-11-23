from datetime import timedelta

from sqlalchemy import select
from test_candidate_journey import enroll, journey_owner  # noqa: F401
from test_integration import call
from test_resume_profile import resume_pdf

from app.core.db import utcnow
from app.models import Application, ProcessForm, Vacancy


def test_complete_process_from_registration_to_test_with_separate_form(client, db, journey_owner, actors):  # noqa: F811
    owner, job, admin, another_vacancy = journey_owner
    # Explicitly enable strict rules even when reusing a compatibility fixture.
    vacancy = db.get(Vacancy, job["id"])
    vacancy.details = vacancy.details | {"structured_workflow": False}
    db.commit()
    call(client, "post", "/vacancies/" + vacancy.id + "/structured-workflow", admin, {"version": vacancy.version})
    job = call(client, "get", "/vacancies/" + job["id"], admin)
    phases = {stage["candidate_phase"]: stage for stage in job["stages"] if stage["candidate_phase"]}
    application = enroll(client, owner, job)

    def current():
        return call(client, "get", "/applications/" + application["id"], admin)

    def move(phase, expected=200):
        return call(client, "post", "/applications/" + application["id"] + "/move", admin,
            {"stage_id": phases[phase]["id"], "version": current()["version"]}, expected)

    assert current()["candidate_access"]["phase"] == "SELECTION"
    assert current()["history"][0]["stage_id"] == phases["SELECTION"]["id"]
    own_form = "/applications/" + application["id"] + "/my-process-form"
    call(client, "post", own_form, owner, {}, 409)
    call(client, "post", own_form, actors["outsider"]["headers"], {}, 404)
    # The validated resume required for enrollment already satisfies this gate.
    uploaded = client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
        files={"file": ("curriculo.pdf", resume_pdf(), "application/pdf")})
    assert uploaded.status_code == 201, uploaded.text
    move("SELECTION")
    review_path = "/applications/" + application["id"] + "/stage-reviews"
    call(client, "post", review_path, admin, {"version": current()["version"], "status": "PENDING", "reason": "Aguardando análise do currículo"}, 201)
    move("FORM", 409)
    call(client, "post", review_path, admin, {"version": current()["version"], "status": "APPROVED", "reason": "Currículo aprovado após análise do RH"}, 201)
    assert current()["stage_id"] == phases["SELECTION"]["id"]
    move("FORM")
    sections = call(client, "get", "/candidates/me/journey", owner)["sections"]
    assert all(sections[key]["enabled"] for key in ["messages", "questions"])
    assert not sections["selection_registration"]["enabled"]
    from external_helpers import complete_data
    call(client, "put", "/candidates/me/selection-registration", owner, {"data": complete_data(), "version": 0}, 403)
    assert not any(sections[key]["enabled"] for key in ["interviews", "tests", "admission"])
    call(client, "post", "/candidates/" + current()["candidate_id"] + "/approve-document-uploads", admin, {}, 409)
    move("INTERVIEW", 409)
    endpoint = "/applications/" + application["id"] + "/process-form"
    first = call(client, "post", own_form, owner, {})
    obsolete = first["link"].split("#token=")[1]
    issued = call(client, "post", endpoint, admin, {"version": current()["version"]})
    token = issued["link"].split("#token=")[1]
    assert client.post("/api/v1/public/process-forms/lookup", json={"token": obsolete}).status_code == 404
    lookup = call(client, "post", "/public/process-forms/lookup", {}, {"token": token})
    assert "candidate_id" not in lookup and "registration" not in lookup and "email" not in lookup
    assert client.get("/api/v1" + endpoint, headers=owner).status_code == 403
    assert client.get("/api/v1" + endpoint, headers=actors["outsider"]["headers"]).status_code in {403, 404}
    registration = {"name": "Pessoa da Jornada", "email": "private@example.com", "phone": "91999999999",
        "desired_position": "Operador", "education": "Ensino médio completo", "experience": "Primeiro emprego"}
    payload = {"token": token, "registration": registration, "answers": {}, "consent": True, "submit": False}
    assert call(client, "post", "/public/process-forms/submit", {}, payload)["status"] == "PENDING"
    assert not call(client, "get", "/candidates/me/journey", owner)["sections"]["selection_registration"]["enabled"]
    move("INTERVIEW", 409)
    payload |= {"submit": True, "answers": {"interest": "Desejo participar desta oportunidade"}}
    assert call(client, "post", "/public/process-forms/submit", {}, payload)["status"] == "COMPLETED"
    assert call(client, "get", "/candidates/me/journey", owner)["sections"]["selection_registration"]["enabled"]
    task_path = "/applications/" + application["id"] + "/stage-task-status"
    tasks = call(client, "get", task_path, admin)
    assert [item["key"] for item in tasks["tasks"]] == ["questions", "registration"]
    assert next(item for item in tasks["tasks"] if item["key"] == "questions")["status"] == "COMPLETED"
    assert next(item for item in tasks["tasks"] if item["key"] == "registration")["status"] == "PENDING"
    move("INTERVIEW", 409)
    from external_helpers import complete_data
    call(client, "put", "/candidates/me/selection-registration", owner, {"data": complete_data(), "version": 0})
    assert call(client, "get", task_path, admin)["status"] == "COMPLETED"
    assert client.get("/api/v1" + task_path, headers=actors["outsider"]["headers"]).status_code == 404
    assert call(client, "get", "/applications/" + application["id"], owner)["process_form_status"] == "COMPLETED"
    call(client, "post", own_form, owner, {}, 409)
    assert client.post("/api/v1/public/process-forms/submit", json=payload).status_code == 404
    form = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application["id"]))
    assert "private@example.com" not in form.encrypted_data
    assert call(client, "get", endpoint, admin)["registration"] == registration | {"notes": ""}
    move("INTERVIEW")
    assert call(client, "get", task_path, admin)["status"] == "PENDING"
    move("TEST", 409)
    interview = call(client, "post", "/interviews", admin, {"vacancy_id": job["id"], "title": "Entrevista do processo",
        "kind": "ONLINE", "starts_at": (utcnow() + timedelta(days=1)).isoformat(),
        "ends_at": (utcnow() + timedelta(days=1, hours=1)).isoformat(), "location": "Sala virtual",
        "interviewers": [actors["admin"]["id"]], "application_ids": [application["id"]]}, 201)
    call(client, "post", "/interviews/" + interview["id"] + "/status", admin,
        {"version": interview["version"], "status": "COMPLETED", "reason": "Entrevista realizada com o candidato"})
    assert call(client, "get", task_path, admin)["status"] == "COMPLETED"
    move("TEST", 409)
    call(client, "post", review_path, admin, {"version": current()["version"], "status": "APPROVED", "reason": "Entrevista validada pelo RH com parecer favorável ao avanço"}, 201)
    from app.services.process_workflow import workflow_blockers
    from app.models import PipelineStage
    active_application = db.get(Application, application["id"])
    assert workflow_blockers(db, active_application, vacancy,
        db.get(PipelineStage, active_application.stage_id), db.get(PipelineStage, phases["TEST"]["id"])) == []
    move("TEST")
    assert current()["stage_id"] == phases["TEST"]["id"]
    scorecard = call(client, "post", "/configuration/scorecards", admin, {"name": "Ficha de entrevista do fluxo", "reason": "Critérios da entrevista",
        "data": {"criteria": [{"key": "communication", "name": "Comunicação", "weight": 1}]}}, 201)
    evaluation = call(client, "post", "/evaluations", admin, {"application_id": application["id"], "interview_id": interview["id"],
        "evaluator_id": actors["admin"]["id"], "scorecard_id": scorecard["id"]}, 201)
    call(client, "post", "/evaluations/" + evaluation["id"] + "/submit", admin,
        {"version": evaluation["version"], "answers": {"communication": {"value": 3, "comment": "Comunicação adequada"}}, "recommendation": "ADVANCE"})
    assessment = call(client, "post", "/tests", admin, {"name": "Teste do processo", "pass_score": 60,
        "questions": [{"key": "safe", "text": "Conferir a segurança antes de operar?", "kind": "BOOLEAN", "correct": True}]}, 201)
    assignment = call(client, "post", "/tests/" + assessment["id"] + "/assign", admin,
        {"application_id": application["id"], "opens_at": (utcnow() - timedelta(minutes=1)).isoformat(), "due_at": (utcnow() + timedelta(days=1)).isoformat()}, 201)
    attempt = call(client, "post", "/test-assignments/" + assignment["id"] + "/start", owner)
    attempt = call(client, "post", "/test-attempts/" + attempt["id"] + "/submit", owner, {"version": attempt["version"], "answers": {"safe": True}})
    assert attempt["score"] == 100 and attempt["status"] == "GRADED"
    assigned = call(client, "get", "/test-assignments?application_id=" + application["id"], admin)["items"]
    assert assigned[0]["result"] == "APPROVED"
    assert call(client, "get", task_path, admin)["status"] == "COMPLETED"
    admission_stage = next(stage for stage in job["stages"] if stage["candidate_phase"] == "ADMISSION")
    call(client, "post", "/applications/" + application["id"] + "/move", admin,
        {"stage_id": admission_stage["id"], "version": current()["version"]})
    assert call(client, "get", "/candidates/me/journey", owner)["sections"]["admission"]["enabled"]
    assert call(client, "get", "/documents/admission-checklist", owner)["can_upload"]
    history = current()["history"]
    assert len(history) >= 4 and all("changed_by" in item for item in history)
    second_job = another_vacancy()
    second = enroll(client, owner, second_job)
    assert call(client, "get", "/applications/" + second["id"] + "/process-form", admin)["status"] == "NOT_SENT"
    assert db.get(Application, second["id"]).answers == {}
    dashboard = call(client, "get", "/dashboard", admin)
    assert dashboard["stage_counts"] and dashboard["recent_activity"]


def test_rh_candidate_registration_duplicate_validation_and_edit(client, db, actors):
    from uuid import uuid4

    from app.models import Candidate, User
    admin = actors["admin"]["headers"]
    payload = {"name": "Pessoa cadastrada pelo RH", "email": "rh-profile-" + uuid4().hex[:8] + "@example.com",
        "phone": "(91) 99999-1234", "profile": {"desired_position": "Operador", "notes": "Cadastro recebido por indicação"}, "source": "WHATSAPP"}
    created = call(client, "post", "/candidates", admin, payload, 201)
    candidate = db.get(Candidate, created["id"])
    user = db.get(User, candidate.user_id)
    assert not user.email_verified and not user.password_hash and not candidate.talent_consent_until
    assert not db.scalar(select(Application.id).where(Application.candidate_id == candidate.id))
    assert candidate.source == "WHATSAPP"
    assert client.post("/api/v1/candidates", headers=admin, json=payload).status_code == 409
    assert client.post("/api/v1/candidates", headers=actors["outsider"]["headers"], json=payload).status_code == 403
    edited = call(client, "put", "/candidates/" + candidate.id + "/rh-profile", admin,
        {"version": candidate.version, "name": candidate.name, "phone": "91988887777", "city": "Belém", "profile": {"desired_position": "Técnico"}})
    assert edited["phone"] == "91988887777" and edited["profile"]["desired_position"] == "Técnico"
    assert client.put("/api/v1/candidates/" + candidate.id + "/rh-profile", headers=admin,
        json={"version": 1, "name": candidate.name, "profile": {}}).status_code == 409


def test_external_form_expiration_privacy_and_no_automatic_movement(client, db, journey_owner):  # noqa: F811
    from app.models import PipelineStage
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    vacancy = db.get(Vacancy, job["id"])
    call(client, "post", "/vacancies/" + vacancy.id + "/structured-workflow", admin, {"version": vacancy.version})
    form_stage = db.scalar(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy.id, PipelineStage.candidate_phase == "FORM"))
    row = db.get(Application, application["id"])
    row.stage_id = form_stage.id
    db.commit()
    endpoint = "/applications/" + row.id + "/process-form"
    issued = call(client, "post", endpoint, admin, {"version": row.version})
    token = issued["link"].split("#token=")[1]
    stored = db.scalar(select(ProcessForm).where(ProcessForm.application_id == row.id))
    assert token != stored.token_hash and token not in str(call(client, "get", endpoint, admin))
    stored.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.post("/api/v1/public/process-forms/lookup", json={"token": token}).status_code == 404
    issued = call(client, "post", endpoint, admin, {"version": row.version})
    token = issued["link"].split("#token=")[1]
    submission = {"token": token, "registration": {"name": "Pessoa com dados privados", "email": "private@example.com", "phone": "91999999999", "desired_position": "Operador", "education": "Ensino médio", "experience": "Primeiro emprego"}, "answers": {"interest": "Participar da oportunidade"}, "consent": True}
    assert client.post("/api/v1/public/process-forms/submit", json=submission | {"consent": False}).status_code == 422
    call(client, "post", "/public/process-forms/submit", {}, submission)
    assert row.stage_id == form_stage.id
    vacancy.blind = True
    form_stage.reveal_identity = False
    db.commit()
    hidden = call(client, "get", endpoint, admin)
    assert hidden["restricted"] and hidden["registration"] is None
    assert "private@example.com" not in str(hidden)
