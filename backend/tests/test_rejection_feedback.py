from types import SimpleNamespace

from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.models import Outbox


def test_rh_queues_automatic_return_on_rejection_once(client, db, actors, monkeypatch):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_candidate(client, notice)
    application = call(client, "post", "/applications", owner,
        {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    monkeypatch.setattr("app.services.rejection_feedback.smtp_runtime", lambda db: SimpleNamespace(enabled=True))
    admin = actors["admin"]["headers"]
    rejected = call(client, "post", "/applications/" + application["id"] + "/decision", admin,
        {"version": application["version"], "decision": "REJECTED",
         "reason": "Justificativa interna reservada", "send_rejection_email": True})
    assert rejected["status"] == "REJECTED"
    entries = db.scalars(select(Outbox).where(Outbox.dedup_key == "rejection-feedback:" + application["id"])).all()
    assert len(entries) == 1
    assert entries[0].payload["recipient"] == candidate["email"]
    assert vacancy["title"] in entries[0].payload["body"]
    assert "Justificativa interna" not in entries[0].payload["body"]
    endpoint = "/applications/" + application["id"] + "/rejection-email"
    original = entries[0].payload.copy()
    call(client, "post", endpoint, admin, {"subject": "Outro retorno", "body": "Uma nova mensagem de retorno."})
    assert entries[0].payload == original
    assert call(client, "get", endpoint, admin)["status"] == "PENDING"
    assert client.post("/api/v1" + endpoint, headers=owner,
        json={"subject": "Retorno", "body": "Envio sem permissão"}).status_code == 403
    assert client.get("/api/v1" + endpoint, headers=actors["outsider"]["headers"]).status_code == 403


def test_rh_can_send_custom_return_after_rejection_and_cannot_send_to_active(client, db, actors, monkeypatch):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, _, _ = register_candidate(client, notice)
    application = call(client, "post", "/applications", owner,
        {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    admin = actors["admin"]["headers"]
    endpoint = "/applications/" + application["id"] + "/rejection-email"
    monkeypatch.setattr("app.services.rejection_feedback.smtp_runtime", lambda db: SimpleNamespace(enabled=True))
    message = {"subject": "Retorno da seleção", "body": "Agradecemos sua participação. Neste momento, seguimos com outro perfil."}
    assert client.post("/api/v1" + endpoint, headers=admin, json=message).status_code == 409
    call(client, "post", "/applications/" + application["id"] + "/decision", admin,
        {"version": application["version"], "decision": "REJECTED", "reason": "Outro perfil selecionado"})
    assert call(client, "get", endpoint, admin)["status"] == "NOT_REQUESTED"
    call(client, "post", endpoint, admin, message)
    entry = db.scalar(select(Outbox).where(Outbox.dedup_key == "rejection-feedback:" + application["id"]))
    assert entry.payload["subject"] == message["subject"]
    assert entry.payload["body"] == message["body"]


def test_disabled_email_does_not_queue_or_close_application(client, db, actors, monkeypatch):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, _, _ = register_candidate(client, notice)
    application = call(client, "post", "/applications", owner,
        {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    monkeypatch.setattr("app.services.rejection_feedback.smtp_runtime", lambda db: SimpleNamespace(enabled=False))
    admin = actors["admin"]["headers"]
    response = client.post("/api/v1/applications/" + application["id"] + "/decision", headers=admin,
        json={"version": application["version"], "decision": "REJECTED",
              "reason": "Outro perfil selecionado", "send_rejection_email": True})
    assert response.status_code == 409
    assert call(client, "get", "/applications/" + application["id"], admin)["status"] == "ACTIVE"
    assert not db.scalar(select(Outbox.id).where(Outbox.dedup_key == "rejection-feedback:" + application["id"]))
