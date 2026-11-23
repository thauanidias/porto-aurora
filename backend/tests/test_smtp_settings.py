from uuid import uuid4

from consent_helpers import consent_signature
from sqlalchemy import select

from app.core.security import decrypt
from app.models import ConfigRecord, Outbox
from app.services.smtp_config import smtp_runtime


def test_rh_smtp_settings_encrypt_secret_and_drive_registration(client, db, actors, monkeypatch):
    monkeypatch.setattr("app.integrations.delivery.send_email", lambda *args, **kwargs: None)
    admin = actors["admin"]["headers"]
    assert client.get("/api/v1/smtp-settings", headers=actors["manager"]["headers"]).status_code == 403
    initial = client.get("/api/v1/smtp-settings", headers=admin)
    assert initial.status_code == 200
    assert not initial.json()["enabled"]

    sender = "tgpm.talentos@portoaurora.example"
    payload = {
        "enabled": True,
        "sender": sender,
        "tenant_id": str(uuid4()),
        "client_id": str(uuid4()),
        "client_secret": "testing-client-secret",
        "public_url": "https://talentos.portoaurora.example",
        "version": None,
    }
    saved = client.put("/api/v1/smtp-settings", json=payload, headers=admin)
    assert saved.status_code == 200, saved.text
    assert saved.json()["secret_configured"]
    assert "testing-client-secret" not in saved.text
    current = client.get("/api/v1/smtp-settings", headers=admin)
    assert current.status_code == 200
    assert "testing-client-secret" not in current.text
    record = db.scalar(select(ConfigRecord).where(ConfigRecord.kind == "smtp-settings"))
    assert record is not None
    assert record.data["encrypted_secret"] != "testing-client-secret"
    assert decrypt(record.data["encrypted_secret"]) == "testing-client-secret"
    runtime = smtp_runtime(db)
    assert runtime.enabled and runtime.sender == sender
    assert client.get("/api/v1/settings", headers=admin).json()["smtp"]

    receipt = client.post(
        "/api/v1/public/consent-receipts",
        json={
            "name": "Pessoa Teste SMTP",
            "email": "smtp-candidate@example.com",
            "context": "CADASTRO",
            "accepted": True, "signature_image": consent_signature(),
        },
    ).json()
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Pessoa Teste SMTP",
            "email": "smtp-candidate@example.com",
            "receipt_id": receipt["id"],
            "consent": True,
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["email_delivery_enabled"]
    assert registered.json()["test_setup_url"] is None
    delivery = db.scalar(
        select(Outbox).where(Outbox.payload["recipient"].astext == "smtp-candidate@example.com")
    )
    assert delivery is not None
    assert "https://talentos.portoaurora.example/confirmar#token=" in delivery.payload["body"]
    test_message = client.post("/api/v1/smtp-settings/test", headers=admin)
    assert test_message.status_code == 200
    assert test_message.json()["recipient"] == actors["admin"]["email"]
    assert client.post(
        "/api/v1/smtp-settings/test", headers=actors["manager"]["headers"]
    ).status_code == 403

    updated = client.put(
        "/api/v1/smtp-settings",
        json={**payload, "enabled": False, "client_secret": "", "version": client.get("/api/v1/smtp-settings", headers=admin).json()["version"]},
        headers=admin,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["secret_configured"]
    assert not client.get("/api/v1/settings", headers=admin).json()["smtp"]


def test_password_settings_replace_local_mode_and_notification_emails_are_queued(client, db, actors, monkeypatch):
    from app.core.config import settings
    from app.services.events import notify

    monkeypatch.setattr(settings(), "test_email_enabled", True)
    pending = Outbox(kind="EMAIL", dedup_key="old-local-mail", payload={"recipient": "old@example.com", "subject": "Local", "body": "Test"})
    db.add(pending)
    db.flush()
    admin = actors["admin"]["headers"]
    body = {"enabled": True, "host": "smtp.example.com", "port": 587, "auth_mode": "basic",
            "sender": "talentos@example.com", "username": "talentos@example.com", "password": "secret-SMTP-password",
            "public_url": "https://talentos.example.com", "test_recipient": "teste@example.com"}
    result = client.put("/api/v1/smtp-settings", headers=admin, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["configured"] and result.json()["password_configured"] and not result.json()["test_mode"]
    assert "secret-SMTP-password" not in result.text
    record = db.scalar(select(ConfigRecord).where(ConfigRecord.kind == "smtp-settings"))
    assert decrypt(record.data["encrypted_password"]) == body["password"]
    assert pending.payload["delivery_mode"] == "test"
    notify(db, actors["admin"]["id"], "Nova etapa", "Seu processo foi atualizado.", "SYSTEM")
    db.flush()
    notification = db.scalar(select(Outbox).where(Outbox.kind == "EMAIL", Outbox.dedup_key.like("notification:%")))
    assert notification.payload["delivery_mode"] == "real"
    assert notification.payload["recipient"] == actors["admin"]["email"]
    saved = client.put("/api/v1/smtp-settings", headers=admin, json={**body, "password": "", "version": result.json()["version"]})
    assert saved.status_code == 200 and smtp_runtime(db).password == body["password"]
    called = []
    monkeypatch.setattr("app.integrations.delivery.send_email", lambda payload, key, db=None: called.append(payload))
    tested = client.post("/api/v1/smtp-settings/test", headers=admin, json={"recipient": "teste@example.com"})
    assert tested.status_code == 200 and called[0]["recipient"] == "teste@example.com"
    assert client.get("/api/v1/smtp-settings", headers=admin).json()["last_test_at"]
