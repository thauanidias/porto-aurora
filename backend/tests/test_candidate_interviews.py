from datetime import timedelta

from test_candidate_journey import (  # noqa: F401
    advance,
    enroll,
    journey_owner,
    register_basic_candidate,
)
from test_integration import call

from app.core.db import utcnow
from app.models import Application, Interview


def test_interview_directory_lists_interview_and_test_phases(client, db, actors, journey_owner):  # noqa: F811
    owner, vacancy, admin, _ = journey_owner
    application = enroll(client, owner, vacancy)
    path = "/interviews/candidates"
    assert call(client, "get", path, admin)["items"] == []
    advance(client, admin, application, vacancy, "INTERVIEW")
    result = call(client, "get", path, admin)
    assert result["total"] == 1
    assert result["items"][0]["id"] == application["id"]
    assert result["items"][0]["candidate"]["name"] == "Pessoa da Jornada"
    assert call(client, "get", path + "?q=Pessoa", admin)["total"] == 1
    assert call(client, "get", path + "?q=inexistente", admin)["total"] == 0
    assert call(client, "get", path, actors["outsider"]["headers"])["items"] == []
    assert client.get("/api/v1" + path, headers=owner).status_code == 403
    advance(client, admin, application, vacancy, "TEST")
    assert call(client, "get", path, admin)["items"][0]["id"] == application["id"]
    content = {"application_id": application["id"], "kind": "INTERVIEW", "title": "Entrevista na fase de testes",
               "url": "https://example.com/interview-tests", "description": "Acesse no dia e horário combinados com o RH."}
    saved = call(client, "post", "/candidate-activity-links", admin, content, 201)
    assert saved["stage_unlocked"] is True
    listed = call(client, "get", path, admin)["items"][0]["interview_links"][0]
    assert listed["description"] == content["description"]
    own = call(client, "get", "/candidate-activity-links?kind=INTERVIEW", owner)["items"][0]
    assert own["url"] == content["url"] and own["stage_unlocked"] is True
    db.get(Application, application["id"]).status = "REJECTED"
    db.commit()
    assert call(client, "get", path, admin)["items"] == []


def test_interview_directory_displays_only_active_interview_links_and_captions(client, db, actors, journey_owner):  # noqa: F811
    owner, vacancy, admin, _ = journey_owner
    application = enroll(client, owner, vacancy)
    advance(client, admin, application, vacancy, "INTERVIEW")
    content = {"application_id": application["id"], "kind": "INTERVIEW", "title": "Entrevista com o RH",
               "url": "https://example.com/entrevista", "description": "Dia 20, às 10h. Acesse cinco minutos antes."}
    link = call(client, "post", "/candidate-activity-links", admin, content, 201)
    call(client, "post", "/candidate-activity-links", admin, content | {"kind": "TEST"}, 201)
    rows = call(client, "get", "/interviews/candidates", admin)["items"]
    assert len(rows) == 1
    assert rows[0]["interview_links"] == [{key: link[key] for key in ("id", "title", "description", "url")}]
    own = call(client, "get", "/candidate-activity-links?kind=INTERVIEW", owner)["items"][0]
    assert own["description"] == content["description"]
    assert own["stage_unlocked"] is True
    call(client, "put", "/candidate-activity-links/" + link["id"], admin,
         {key: link[key] for key in ("title", "description", "url", "version")} | {"active": False})
    assert call(client, "get", "/interviews/candidates", admin)["items"][0]["interview_links"] == []


def test_candidate_sees_only_own_scheduled_interview_details(client, db, actors, journey_owner):  # noqa: F811
    owner, vacancy, admin, _ = journey_owner
    other, _, _ = register_basic_candidate(client)
    application = enroll(client, owner, vacancy)
    interview = call(client, "post", "/interviews", actors["admin"]["headers"], {
        "vacancy_id": vacancy["id"], "title": "Entrevista técnica", "kind": "TECHNICAL",
        "starts_at": (utcnow() + timedelta(days=2)).isoformat(),
        "ends_at": (utcnow() + timedelta(days=2, hours=1)).isoformat(),
        "location": "Sala RH", "interviewers": [actors["interviewer"]["id"]],
        "application_ids": [application["id"]],
    }, 201)
    items = call(client, "get", "/interviews/me", owner)["items"]
    assert len(items) == 1
    assert set(items[0]) == {"id", "starts_at", "interviewers", "stage_unlocked"}
    assert items[0]["stage_unlocked"] is False
    assert items[0]["interviewers"] == ["Interviewer de Teste"]
    assert call(client, "get", "/interviews/me", other)["items"] == []
    advance(client, admin, application, vacancy, "INTERVIEW")
    assert call(client, "get", "/interviews/me", owner)["items"][0]["stage_unlocked"] is True
    db.get(Interview, interview["id"]).status = "CANCELLED"
    db.commit()
    assert call(client, "get", "/interviews/me", owner)["items"] == []


def test_manager_agenda_receives_responsible_vacancy_interviews_only(client, db, actors, journey_owner):
    owner, vacancy, admin, _ = journey_owner
    application = enroll(client, owner, vacancy)
    interview = call(client, "post", "/interviews", admin, {
        "vacancy_id": vacancy["id"], "title": "Conversa com o gestor", "kind": "ONLINE",
        "starts_at": (utcnow() + timedelta(days=2)).isoformat(),
        "ends_at": (utcnow() + timedelta(days=2, hours=1)).isoformat(),
        "location": "https://example.com/entrevista", "interviewers": [actors["admin"]["id"]],
        "application_ids": [application["id"]],
    }, 201)
    agenda = call(client, "get", "/interviews/manager-agenda", actors["manager"]["headers"])
    item = next(item for item in agenda["items"] if item["id"] == interview["id"])
    assert item["vacancy_title"] == vacancy["title"]
    assert item["candidates"][0]["name"] == "Pessoa da Jornada"
    assert item["location"] == "https://example.com/entrevista"
    assert call(client, "get", "/interviews/manager-agenda", actors["outsider"]["headers"])["total"] == 0
    assert client.get("/api/v1/interviews/manager-agenda", headers=owner).status_code == 403
    from app.models import Notification
    from sqlalchemy import select
    notification = db.scalar(select(Notification).where(Notification.user_id == actors["manager"]["id"], Notification.title == "Entrevista agendada para sua vaga"))
    assert notification is not None
