import test_candidate_journey
from test_candidate_journey import (
    advance,
    enroll,
    register_basic_candidate,
)
from test_integration import call

journey_owner = test_candidate_journey.journey_owner

def test_test_directory_and_private_editable_questionnaire(client, db, actors, journey_owner):
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    assert call(client, "get", "/test-candidates", admin)["items"] == []
    assert call(client, "get", "/test-questionnaires/me", owner)["items"] == []
    advance(client, admin, application, job, "TEST")
    row = call(client, "get", "/test-candidates", admin)["items"][0]
    assert row["id"] == application["id"]
    assert call(client, "get", "/test-candidates", actors["outsider"]["headers"])["items"] == []
    assert client.get("/api/v1/test-candidates", headers=owner).status_code == 403
    path = "/applications/" + row["id"] + "/test-questionnaire"
    body = {"version": row["version"], "questions": [{"key": "experience", "text": "  Descreva sua experiência.  ", "required": True}]}
    saved = call(client, "put", path, admin, body)
    assert saved["questionnaire"]["questions"][0]["text"] == "Descreva sua experiência."
    assert client.put("/api/v1" + path, headers=admin, json=body).status_code == 409
    own = call(client, "get", "/test-questionnaires/me", owner)["items"][0]
    answer = {"version": own["version"], "revision": 1, "answers": {"experience": "  Atuei em operações.  "}}
    assert client.put("/api/v1" + path + "/answers", headers=owner, json=answer | {"answers": {}}).status_code == 422
    assert client.put("/api/v1" + path + "/answers", headers=admin, json=answer).status_code == 403
    result = call(client, "put", path + "/answers", owner, answer)
    assert result["questionnaire"]["answers"] == {"experience": "Atuei em operações."}
    updated = call(client, "put", path, admin, {"version": result["version"], "questions": [{"key": "experience", "text": "Descreva suas competências.", "required": False}]})
    assert updated["questionnaire"]["revision"] == 2
    assert updated["questionnaire"]["answers"]["experience"] == "Atuei em operações."
    assert updated["questionnaire"]["answered_questions"][0]["text"] == "Descreva sua experiência."
    assert client.put("/api/v1" + path + "/answers", headers=owner, json=answer | {"version": updated["version"]}).status_code == 409
    other, _, _ = register_basic_candidate(client)
    assert call(client, "get", "/test-questionnaires/me", other)["items"] == []
    assert client.put("/api/v1" + path + "/answers", headers=other, json=answer).status_code == 403
    call(client, "post", "/candidate-activity-links", admin, {"application_id": row["id"], "kind": "TEST", "title": "Teste prático",
        "description": "Realize até amanhã às 10h.", "url": "https://example.com/teste"}, 201)
    assert len(call(client, "get", "/test-candidates", admin)["items"][0]["test_links"]) == 1
    current = call(client, "get", "/applications/" + row["id"], admin)
    call(client, "post", "/applications/" + row["id"] + "/decision", admin,
         {"version": current["version"], "decision": "REJECTED", "reason": "Encerramento para teste de liberação"})
    assert call(client, "get", "/test-candidates", admin)["items"] == []
    assert call(client, "get", "/test-questionnaires/me", owner)["items"] == []
