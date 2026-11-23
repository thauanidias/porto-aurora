import test_candidate_journey
from test_candidate_journey import advance, enroll
from test_integration import call

from app.models import Application, User, Vacancy

journey_owner = test_candidate_journey.journey_owner


def test_only_rh_finalists_from_manager_sector_are_visible(client, db, actors, journey_owner):
    owner, job, admin, make_job = journey_owner
    manager = actors["manager"]["headers"]
    application = enroll(client, owner, job)
    assert call(client, "get", "/manager-finalists", manager)["total"] == 0
    application = advance(client, admin, application, job, "FINALIST")
    vacancy = db.get(Vacancy, job["id"])
    vacancy.manager_id = actors["outsider"]["id"]
    db.commit()
    candidate_id = application["candidate_id"]
    other_job = make_job()
    other_application = enroll(client, owner, other_job)
    advance(client, admin, other_application, other_job, "FINALIST")
    db.get(Vacancy, other_job["id"]).org_unit_id = actors["other_org"]
    db.get(Vacancy, other_job["id"]).manager_id = actors["outsider"]["id"]
    db.commit()
    result = call(client, "get", "/manager-finalists", manager)
    assert result["total"] == 1
    finalist = result["items"][0]
    assert finalist["id"] == candidate_id and finalist["finalist"] is True
    assert finalist["vacancy_titles"] == [job["title"]]
    assert [p["application_id"] for p in finalist["finalist_processes"]] == [application["id"]]
    call(client, "get", "/candidates/" + candidate_id, manager)
    call(client, "get", "/applications/" + application["id"], manager)
    call(client, "get", "/vacancies/" + job["id"], manager)
    listed = call(client, "get", "/applications?candidate_id=" + candidate_id, manager)
    assert [row["id"] for row in listed["items"]] == [application["id"]]
    db.get(Application, application["id"]).status = "REJECTED"
    db.commit()
    assert call(client, "get", "/manager-finalists", manager)["total"] == 0
    call(client, "get", "/applications/" + application["id"], manager, expected=404)


def test_sector_finalists_respect_confidentiality_missing_sector_and_roles(client, db, actors, journey_owner):
    owner, job, admin, _ = journey_owner
    application = advance(client, admin, enroll(client, owner, job), job, "FINALIST")
    vacancy = db.get(Vacancy, job["id"])
    vacancy.confidential = True
    vacancy.manager_id = actors["outsider"]["id"]
    db.commit()
    manager = actors["manager"]["headers"]
    assert call(client, "get", "/manager-finalists", manager)["total"] == 0
    call(client, "get", "/candidates/" + application["candidate_id"], manager, expected=404)
    vacancy.manager_id = actors["manager"]["id"]
    db.commit()
    assert call(client, "get", "/manager-finalists", manager)["total"] == 1
    db.get(User, actors["manager"]["id"]).org_unit_id = None
    db.commit()
    assert call(client, "get", "/manager-finalists", manager)["total"] == 0
    call(client, "get", "/manager-finalists", owner, expected=403)
    call(client, "get", "/manager-finalists", {}, expected=401)
