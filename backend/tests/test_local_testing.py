from urllib.parse import parse_qs, urlsplit

import pytest
from consent_helpers import consent_signature
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.models import ConfigRecord, Outbox, User
from app.schemas.auth import Register
from app.services.smtp_config import smtp_runtime


def test_local_mail_overrides_corporate_settings(db, actors, monkeypatch):
    monkeypatch.setattr(settings(), "test_email_enabled", True)
    db.add(ConfigRecord(kind="smtp-settings", name="SMTP", data={"enabled": True}, created_by=actors["admin"]["id"]))
    db.flush()
    cfg = smtp_runtime(db)
    assert cfg.enabled and cfg.host == "mailpit" and cfg.port == 1025
    assert not cfg.starttls and cfg.auth_mode == "basic"


def test_local_email_rejected_in_production(monkeypatch):
    monkeypatch.setattr(settings(), "test_email_enabled", True)
    monkeypatch.setattr(settings(), "environment", "production")
    with pytest.raises(ValueError, match="teste"):
        settings().secure_configuration()


def test_signup_and_password_reset_using_local_mail(client, db, monkeypatch):
    monkeypatch.setattr(settings(), "test_email_enabled", True)
    email = "local-flows@example.com"
    receipt = client.post("/api/v1/public/consent-receipts", json={
        "name": "Pessoa de Teste Local", "email": email, "context": "CADASTRO", "accepted": True, "signature_image": consent_signature(),
    }).json()
    result = client.post("/api/v1/auth/register", json={
        "name": "Pessoa de Teste Local", "email": email, "receipt_id": receipt["id"],
        "consent": True, "return_to": "/carreiras/vagas/operador",
    })
    assert result.status_code == 201, result.text
    assert result.json()["email_delivery_enabled"] and not result.json()["test_setup_url"]

    def token_from_outbox(purpose):
        rows = db.scalars(select(Outbox).where(Outbox.kind == "EMAIL")).all()
        body = next(row.payload["body"] for row in rows if "purpose=" + purpose in row.payload["body"])
        return parse_qs(urlsplit(body.split()[-1]).fragment)

    setup = token_from_outbox("SETUP")
    assert setup["next"] == ["/carreiras/vagas/operador"]
    resent = client.post("/api/v1/auth/request-link", json={
        "email": email, "purpose": "VERIFY", "return_to": "/carreiras/vagas/operador",
    })
    assert resent.status_code == 200
    messages = db.scalars(select(Outbox).where(Outbox.kind == "EMAIL")).all()
    assert sum("purpose=SETUP" in item.payload["body"] for item in messages) == 2
    password = "It42!?"
    response = client.post("/api/v1/auth/consume-link", json={"token": setup["token"][0], "password": password})
    assert response.status_code == 200, response.text
    old_access = response.json()["access_token"]
    assert db.scalar(select(User).where(User.email == email)).email_verified
    result = client.post("/api/v1/auth/request-link", json={"email": email, "purpose": "RESET"})
    assert result.status_code == 200
    reset = token_from_outbox("RESET")["token"][0]
    new_password = "Ct42!?"
    assert client.post("/api/v1/auth/consume-link", json={"token": reset, "password": new_password}).status_code == 200
    assert client.post("/api/v1/auth/consume-link", json={"token": reset, "password": new_password}).status_code == 400
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + old_access}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": password}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": email, "password": new_password}).status_code == 200


def test_registration_rejects_external_return_path():
    with pytest.raises(ValidationError):
        Register(name="Pessoa Teste", email="test@example.com", consent=True, return_to="//example.com")
