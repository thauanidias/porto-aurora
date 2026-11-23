from test_integration import call, register_candidate, setup_vacancy

from app.models import Vacancy


def test_candidate_list_shows_submitted_vacancies_with_access_scope(client, db, actors):
    first, notice, _, _ = setup_vacancy(client, actors)
    second, second_notice, _, _ = setup_vacancy(client, actors)
    headers, candidate, _ = register_candidate(client, notice)
    _, unregistered, _ = register_candidate(client, notice)
    for vacancy, accepted_notice in [(first, notice), (second, second_notice)]:
        call(client, "post", "/applications", headers, {
            "vacancy_id": vacancy["id"], "notice_id": accepted_notice["id"], "consent": True,
            "answers": {"interest": "Participar do processo seletivo"},
        }, 201)
    restricted = db.get(Vacancy, second["id"])
    restricted.title = "Outra vaga restrita"
    # Sharing a sector must not expose another manager's vacancy or its candidates.
    restricted.org_unit_id = actors["org"]
    restricted.manager_id = actors["outsider"]["id"]
    restricted.recruiter_id = actors["outsider"]["id"]
    db.commit()

    def listing(actor):
        return {row["id"]: row for row in call(client, "get", "/candidates", actor)["items"]}

    admin = listing(actors["admin"]["headers"])
    assert admin[candidate["id"]]["vacancy_titles"] == ["Outra vaga restrita", first["title"]]
    assert admin[unregistered["id"]]["vacancy_titles"] == []
    manager = listing(actors["manager"]["headers"])
    assert manager[candidate["id"]]["vacancy_titles"] == [first["title"]]
    processes = call(client, "get", "/applications?candidate_id=" + candidate["id"], actors["manager"]["headers"])
    assert processes["total"] == 1
    assert processes["items"][0]["vacancy_id"] == first["id"]
    all_processes = call(client, "get", "/applications?candidate_id=" + candidate["id"], actors["admin"]["headers"])
    assert all_processes["total"] == 2
    assert call(client, "get", "/applications?candidate_id=" + unregistered["id"], actors["admin"]["headers"])["total"] == 0
