from sqlalchemy import select
from test_candidate_journey import journey_owner  # noqa: F401
from test_integration import call

from app.core.db import utcnow
from app.models import Application, Vacancy


def test_published_vacancy_report_counts_includes_zero_and_scopes_access(client, db, journey_owner, actors):  # noqa: F811
    owner, job, admin, create_job = journey_owner
    empty = create_job()
    draft = create_job()
    db.get(Vacancy, draft["id"]).status = "DRAFT"
    db.get(Vacancy, draft["id"]).published_at = None
    for item in [job, empty]:
        vacancy = db.get(Vacancy, item["id"])
        vacancy.published_at = utcnow()
        vacancy.status = "PUBLISHED"
    db.commit()
    person = call(client, "get", "/candidates/me", owner)
    record = Application(candidate_id=person["id"], vacancy_id=job["id"],
                         stage_id=job["stages"][0]["id"], stage_entered_at=utcnow(),
                         answers={}, test_questionnaire={}, profile_snapshot={}, utm={}, closure_reason="")
    db.add(record)
    db.commit()
    application = {"id": record.id}
    result = call(client, "get", "/analytics/vacancies", admin)
    rows = {row["id"]: row for row in result["items"]}
    assert rows[job["id"]]["candidates"] == 1
    assert rows[job["id"]]["in_progress"] == 1
    assert sum(stage["count"] for stage in rows[job["id"]]["stages"]) == 1
    assert rows[empty["id"]]["candidates"] == 0
    assert draft["id"] not in rows
    assert result["summary"]["applications"] == 1
    db.get(Application, application["id"]).status = "REJECTED"
    db.get(Vacancy, job["id"]).status = "CLOSED"
    db.commit()
    closed = call(client, "get", "/analytics/vacancies?status=CLOSED", admin)
    assert closed["items"][0]["rejected"] == 1
    assert closed["items"][0]["in_progress"] == 0
    assert closed["items"][0]["stages"] == []
    assert closed["summary"]["vacancies"] == 1
    search = call(client, "get", "/analytics/vacancies?q=" + empty["code"], admin)
    assert search["total"] == 1 and search["items"][0]["id"] == empty["id"]
    response = client.get("/api/v1/analytics/vacancies", headers=actors["outsider"]["headers"])
    assert response.status_code == 403 or response.status_code == 200 and response.json()["total"] == 0
    assert db.scalar(select(Application.status).where(Application.id == application["id"])) == "REJECTED"
