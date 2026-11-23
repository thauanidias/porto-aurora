from test_candidate_journey import journey_owner, enroll, register_basic_candidate  # noqa: F401
from test_integration import call


def test_candidate_feedback_is_persisted_and_scoped_to_responsible_rh(client, journey_owner, actors):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    other, _, _ = register_basic_candidate(client)
    payload = {"application_id": application["id"], "message": "Fui bem orientado nas etapas do processo.", "rating": 5}
    call(client, "post", "/candidate-feedback", other, payload, 404)
    saved = call(client, "post", "/candidate-feedback", owner, payload, 201)
    result = call(client, "get", "/candidate-feedback", admin)
    entry = next(item for item in result["items"] if item["id"] == saved["id"])
    assert entry["message"] == payload["message"]
    assert entry["rating"] == 5
    assert entry["vacancy_title"] == job["title"]
    assert entry["candidate_name"] == "Pessoa da Jornada"
    outsider = client.get("/api/v1/candidate-feedback", headers=actors["outsider"]["headers"])
    assert outsider.status_code == 403 or outsider.json()["total"] == 0
    call(client, "get", "/candidate-feedback", owner, expected=403)
    assert client.post("/api/v1/candidate-feedback", headers=owner, json=payload | {"message": "  "}).status_code == 422
