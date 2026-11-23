import pytest
from sqlalchemy import select
from test_candidate_journey import (  # noqa: F401
    advance,
    enroll,
    journey_owner,
    register_basic_candidate,
)
from test_integration import call

from app.models import AuditLog, Notification, Role, UserRole

PATH = "/candidate-activity-links"


def create_link(client, admin, application, kind="INTERVIEW"):
    return call(client, "post", PATH, admin, {"application_id": application["id"], "kind": kind,
        "title": "Entrevista com o RH" if kind == "INTERVIEW" else "Teste de conhecimentos",
        "description": "Leia as orientações e participe na data informada pelo RH.",
        "url": "https://example.com/activity?token=individual"}, 201)


def test_links_are_private_and_follow_each_application_stage(client, db, journey_owner):  # noqa: F811
    owner, job, admin, another = journey_owner
    application = enroll(client, owner, job)
    second_job = another()
    second = enroll(client, owner, second_job)
    interview = create_link(client, admin, application)
    assessment = create_link(client, admin, application, "TEST")
    other_test = create_link(client, admin, second, "TEST")
    blocked = call(client, "get", PATH, owner)["items"]
    assert len(blocked) == 3 and all("url" not in row and not row["stage_unlocked"] for row in blocked)
    assert blocked[0]["description"]
    other, _, _ = register_basic_candidate(client)
    assert call(client, "get", PATH, other)["items"] == []
    candidate_id = call(client, "get", "/candidates/me", owner)["id"]
    assert client.get("/api/v1" + PATH + "?candidate_id=" + candidate_id, headers=other).status_code == 403
    internal = call(client, "get", PATH + "?candidate_id=" + candidate_id, admin)["items"]
    assert all(row["url"] and row["can_manage"] for row in internal)
    application = advance(client, admin, application, job, "INTERVIEW")
    rows = {row["id"]: row for row in call(client, "get", PATH, owner)["items"]}
    assert rows[interview["id"]]["url"].endswith("token=individual")
    assert "url" not in rows[assessment["id"]]
    advance(client, admin, application, job, "TEST")
    rows = {row["id"]: row for row in call(client, "get", PATH, owner)["items"]}
    assert rows[assessment["id"]]["stage_unlocked"] and rows[assessment["id"]]["url"]
    assert not rows[other_test["id"]]["stage_unlocked"] and "url" not in rows[other_test["id"]]
    notifications = db.scalars(select(Notification).where(Notification.title == "Entrevista preparada pelo RH")).all()
    assert notifications and notifications[-1].link == "/candidato/entrevistas"


def test_rh_edits_deactivates_and_reactivates_with_version_control(client, db, journey_owner):  # noqa: F811
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    row = create_link(client, admin, application, "TEST")
    content = {key: row[key] for key in ("title", "description", "url", "active", "version")}
    content.update(description="Novas orientações de realização.", active=False)
    updated = call(client, "put", PATH + "/" + row["id"], admin, content)
    assert updated["version"] > row["version"]
    assert call(client, "get", PATH, owner)["items"] == []
    assert client.put("/api/v1" + PATH + "/" + row["id"], headers=admin, json=content).status_code == 409
    content.update(version=updated["version"], active=True)
    call(client, "put", PATH + "/" + row["id"], admin, content)
    own = call(client, "get", PATH + "?kind=TEST", owner)["items"][0]
    assert own["description"] == "Novas orientações de realização." and "url" not in own
    assert db.scalar(select(AuditLog.id).where(AuditLog.action == "candidate.activity_link_updated"))


def test_rh_links_remain_within_authorized_vacancy_scope(client, db, actors, journey_owner):  # noqa: F811
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    row = create_link(client, admin, application)
    role = db.scalar(select(Role).where(Role.name == "RECRUTADOR"))
    db.add(UserRole(user_id=actors["outsider"]["id"], role_id=role.id))
    db.commit()
    outsider = actors["outsider"]["headers"]
    body = {key: row[key] for key in ("title", "description", "url", "application_id", "kind")}
    assert client.post("/api/v1" + PATH, headers=outsider, json=body).status_code == 404
    candidate_id = call(client, "get", "/candidates/me", owner)["id"]
    assert client.get("/api/v1" + PATH + "?candidate_id=" + candidate_id, headers=outsider).status_code == 404
    update = {key: row[key] for key in ("title", "description", "url", "active", "version")}
    assert client.put("/api/v1" + PATH + "/" + row["id"], headers=outsider, json=update).status_code == 404


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///test", "https://user:secret@example.com", "invalid"])
def test_link_urls_and_permissions_are_validated(client, actors, journey_owner, url):  # noqa: F811
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    body = {"application_id": application["id"], "kind": "TEST", "title": "Atividade de teste",
            "description": "Orientações de teste.", "url": url}
    assert client.post("/api/v1" + PATH, headers=admin, json=body).status_code == 422
    body["url"] = "https://example.com"
    assert client.post("/api/v1" + PATH, headers=owner, json=body).status_code == 403
    assert client.post("/api/v1" + PATH, headers=actors["manager"]["headers"], json=body).status_code == 403
    body["description"] = "   "
    assert client.post("/api/v1" + PATH, headers=admin, json=body).status_code == 422
    assert client.get("/api/v1" + PATH).status_code == 401


def test_candidate_confirms_external_test_once_and_rh_sees_it(client, db, journey_owner):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    link = create_link(client, admin, application, "TEST")
    endpoint = PATH + "/" + link["id"] + "/complete"
    call(client, "post", endpoint, owner, {}, 409)
    other, _, _ = register_basic_candidate(client)
    call(client, "post", endpoint, other, {}, 404)
    advance(client, admin, application, job, "TEST")
    result = call(client, "post", endpoint, owner, {})
    assert result["completed_at"]
    assert call(client, "post", endpoint, owner, {})["completed_at"] == result["completed_at"]
    candidate_id = call(client, "get", "/candidates/me", owner)["id"]
    rh = call(client, "get", PATH + "?candidate_id=" + candidate_id, admin)["items"]
    assert next(row for row in rh if row["id"] == link["id"])["completed_at"]
    tasks = call(client, "get", "/applications/" + application["id"] + "/stage-task-status", admin)["tasks"]
    assert next(task for task in tasks if task["key"] == "external-test-" + link["id"])["status"] == "COMPLETED"
    notifications = db.scalars(select(Notification).where(Notification.title == "Candidato informou a conclusão do teste")).all()
    assert len(notifications) == 1


def test_rh_confirms_link_test_phase_and_advances_without_internal_grading(client, db, journey_owner, monkeypatch):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    create_link(client, admin, application, "TEST")
    application = advance(client, admin, application, job, "TEST")
    from app.models import PipelineStage
    stage = db.get(PipelineStage, application["stage_id"])
    stage.required = True
    db.commit()
    target = next(item for item in job["stages"] if item["kind"] == "FINALIST")
    endpoint = "/applications/" + application["id"]
    call(client, "post", endpoint + "/move", admin, {"version": application["version"], "stage_id": target["id"]}, 409)
    call(client, "post", endpoint + "/complete-external-tests", owner, {}, 403)
    assert call(client, "post", endpoint + "/complete-external-tests", admin, {})["status"] == "COMPLETED"
    current = call(client, "get", endpoint, admin)
    from types import SimpleNamespace
    from app.services import smtp_config
    monkeypatch.setattr(smtp_config, "smtp_runtime", lambda _: SimpleNamespace(enabled=True, notifications_enabled=True, public_url="https://example.com", test_mode=True))
    advanced = call(client, "post", endpoint + "/move", admin, {"version": current["version"], "stage_id": target["id"]})
    assert advanced["stage_id"] == target["id"]
    directory = call(client, "get", "/candidates", admin)["items"]
    profile = next(item for item in directory if item["id"] == advanced["candidate_id"])
    assert profile["finalist_history"][0]["vacancy_title"] == job["title"]
    assert profile["finalist_history"][0]["current"] is True
    assert profile["finalist_history"][0]["entered_at"]
    assert profile["process_history"][0]["application_id"] == advanced["id"]
    assert profile["process_history"][0]["status"] == "ACTIVE"
    assert profile["process_history"][0]["stage_kind"] == "FINALIST"

    tasks = call(client, "get", endpoint + "/stage-task-status", admin)["tasks"]
    optional_tasks = [task for task in tasks if task["key"].startswith("document-ADM_DEP_")]
    assert len(optional_tasks) == 7
    assert all(task["status"] == "NOT_APPLICABLE" for task in optional_tasks)

    proposal = next(item for item in job["stages"] if item["kind"] == "OFFER")
    call(client, "post", endpoint + "/move", admin, {"version": advanced["version"], "stage_id": proposal["id"]}, 409)
    from app.models import Outbox
    messages = db.scalars(select(Outbox).where(Outbox.kind == "EMAIL")).all()
    final_email = [item for item in messages if "Você está entre os finalistas" in item.payload.get("subject", "")]
    assert len(final_email) == 1
    assert job["title"] in final_email[0].payload["body"]
    assert "confirmação da contratação" in final_email[0].payload["body"]
    call(client, "post", endpoint + "/move", admin, {"version": advanced["version"], "stage_id": target["id"]})
    assert len([item for item in db.scalars(select(Outbox).where(Outbox.kind == "EMAIL")) if "Você está entre os finalistas" in item.payload.get("subject", "")]) == 1
