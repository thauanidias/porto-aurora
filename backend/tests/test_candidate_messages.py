from test_integration import call, register_candidate, release_test_stage, setup_vacancy


def test_candidate_rh_conversation_is_private_and_notifies_both_sides(client, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, _, _ = register_candidate(client, notice)
    other, _, _ = register_candidate(client, notice)
    admin = actors["admin"]["headers"]
    application = call(client, "post", "/applications", owner, {
        "vacancy_id": vacancy["id"], "notice_id": notice["id"], "consent": True,
        "answers": {"interest": "Participar do processo"},
    }, 201)
    release_test_stage(client, application["id"])
    path = "/applications/" + application["id"] + "/messages"
    sent = call(client, "post", path, owner, {
        "subject": "Dúvida", "body": "Qual o próximo passo?", "visibility": "CANDIDATE",
    }, 201)
    notifications = call(client, "get", "/notifications", admin)["items"]
    assert any(n["category"] == "MESSAGE" and n["link"].endswith(application["id"] + "?aba=messages") for n in notifications)
    reply = call(client, "post", path, admin, {
        "subject": "Resposta", "body": "Aguarde o agendamento da entrevista.", "visibility": "CANDIDATE",
    }, 201)
    assert any(n["category"] == "MESSAGE" for n in call(client, "get", "/notifications", owner)["items"])
    note = call(client, "post", path, admin, {"subject": "Nota interna", "body": "Conteúdo reservado ao RH", "visibility": "RH"}, 201)
    assert call(client, "get", "/messages/unread-count", owner)["unread"] == 1
    assert call(client, "get", "/messages/unread-count", admin)["unread"] == 1
    assert call(client, "get", "/messages/unread-count", other)["unread"] == 0
    call(client, "post", path + "/read", owner, {"message_id": reply["id"]})
    assert call(client, "get", "/messages/unread-count", owner)["unread"] == 0
    assert call(client, "get", "/messages/unread-count", admin)["unread"] == 1
    call(client, "post", path + "/read", admin, {"message_id": reply["id"]})
    assert call(client, "get", "/messages/unread-count", admin)["unread"] == 0
    assert client.post("/api/v1" + path + "/read", headers=other, json={"message_id": reply["id"]}).status_code == 403
    assert client.post("/api/v1" + path + "/read", headers=owner, json={"message_id": note["id"]}).status_code == 404
    for headers in [owner, admin]:
        messages = call(client, "get", path + "?conversation_only=true", headers)["items"]
        assert {m["id"] for m in messages} == {sent["id"], reply["id"]}
        assert all(m["sender_name"] and m["sender_kind"] for m in messages)
        assert note["id"] not in {m["id"] for m in messages}
    assert note["id"] in {m["id"] for m in call(client, "get", path, admin)["items"]}
    assert client.get("/api/v1" + path, headers=other).status_code == 403
    assert client.post("/api/v1" + path, headers=other, json={"subject": "Olá", "body": "Tentativa"}).status_code == 403
    assert client.post("/api/v1" + path, headers=owner, json={"subject": "Nota", "body": "Tentativa", "visibility": "RH"}).status_code == 422
