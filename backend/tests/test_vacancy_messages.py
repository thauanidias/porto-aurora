from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.models import Notification


def test_manager_and_rh_private_conversation(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    candidate, _, _ = register_candidate(client, notice)
    path = "/vacancies/" + vacancy["id"] + "/messages"
    manager = actors["manager"]["headers"]
    rh = actors["admin"]["headers"]
    sent = call(client, "post", path, manager, {"body": "Mensagem de teste para RH"}, 201)
    reply = call(client, "post", path, rh, {"body": "Resposta de teste para gestor"}, 201)
    for headers in [manager, rh]:
        result = call(client, "get", path, headers)
        assert result["total"] == 2
        assert {item["id"] for item in result["items"]} == {sent["id"], reply["id"]}
        assert all(item["sender_name"] for item in result["items"])
    for headers in [candidate, actors["outsider"]["headers"]]:
        assert client.get("/api/v1" + path, headers=headers).status_code in {403, 404}
        assert client.post("/api/v1" + path, headers=headers, json={"body": "Nao autorizado"}).status_code in {403, 404}
    assert client.get("/api/v1" + path).status_code == 401
    assert client.post("/api/v1" + path, headers=manager, json={"body": "  "}).status_code == 422
    assert db.scalar(select(Notification.id).where(Notification.user_id == actors["manager"]["id"], Notification.category == "VACANCY_MESSAGE"))
