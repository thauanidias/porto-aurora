from sqlalchemy import select
from test_candidate_journey import journey_owner, enroll, advance  # noqa: F401
from test_integration import call
from app.models import ProcessForm


def test_rh_edits_unstarted_questions_and_candidate_answers_without_repeating_profile(client, db, journey_owner, actors):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    application = advance(client, admin, application, job, "INTERVIEW")
    issued = call(client, "post", f"/applications/{application['id']}/process-form", admin, {"version": application["version"]})
    token = issued["link"].split("#token=")[1]
    endpoint = f"/vacancies/{job['id']}/questions"
    questions = [{"key": "turno", "label": "Pode trabalhar pela manhã?", "kind": "BOOLEAN", "required": True, "options": []}]
    version = call(client, "get", f"/vacancies/{job['id']}", admin)["version"]
    updated = call(client, "put", endpoint, admin, {"version": version, "questions": questions})
    assert updated["updated_unstarted_forms"] == 1
    lookup = call(client, "post", "/public/process-forms/lookup", {}, {"token": token})
    assert lookup["questions"] == questions
    before = call(client, "get", "/candidates/me/journey", owner)["sections"]
    assert before["messages"]["enabled"]
    assert not before["selection_registration"]["enabled"]
    assert client.put("/api/v1/candidates/me/selection-registration", headers=owner, json={}).status_code in {403, 422}
    sent = call(client, "post", "/public/process-forms/submit", {}, {"token": token, "answers": {"turno": False}, "consent": True, "submit": True})
    assert sent["status"] == "COMPLETED"
    assert sent["registration_released"] is True
    assert call(client, "get", "/candidates/me/journey", owner)["sections"]["selection_registration"]["enabled"]
    form = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application["id"]))
    assert form.questions == questions
    replacement = [{"key": "aprendizado", "label": "O que você deseja aprender?", "kind": "TEXT", "required": True, "options": []}]
    call(client, "put", endpoint, admin, {"version": updated["version"], "questions": replacement})
    db.refresh(form)
    assert form.questions == questions
    assert client.put("/api/v1" + endpoint, headers=owner, json={"version": updated["version"], "questions": []}).status_code == 403
    assert client.put("/api/v1" + endpoint, headers=actors["outsider"]["headers"], json={"version": updated["version"], "questions": []}).status_code in {403, 404}


def test_invalid_question_choices_and_duplicate_keys_are_rejected(client, journey_owner):
    _, job, admin, _ = journey_owner
    question = {"key": "turno", "label": "Escolha um turno", "kind": "SINGLE", "options": ["Manhã"]}
    endpoint = f"/api/v1/vacancies/{job['id']}/questions"
    assert client.put(endpoint, headers=admin, json={"version": job["version"], "questions": [question]}).status_code == 422
    question |= {"options": ["Manhã", "Tarde"]}
    assert client.put(endpoint, headers=admin, json={"version": job["version"], "questions": [question, question]}).status_code == 422
