from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_rh_directory import identity, login, policy  # noqa: F401

from app.models import Outbox
from app.services.rh_welcome import queue_welcome, welcome_message


@pytest.mark.usefixtures("policy")
def test_successful_rh_login_queues_one_welcome_and_refresh_does_not(client, db, monkeypatch):
    person = identity()
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: person)
    runtime = SimpleNamespace(enabled=True, public_url="https://talentos.example", test_mode=True)
    monkeypatch.setattr("app.services.rh_welcome.smtp_runtime", lambda db: runtime)
    monkeypatch.setattr("app.services.smtp_config.smtp_runtime", lambda db=None: runtime)
    first = login(client)
    assert first.status_code == 200
    entries = list(db.scalars(select(Outbox).where(Outbox.dedup_key.like("rh-welcome:%"))))
    assert len(entries) == 1
    entry = entries[0]
    assert entry.payload["recipient"] == person["email"]
    assert entry.payload["template"] == "rh-welcome"
    assert "Equipe Porto Aurora Talentos" in entry.payload["body"] and "Pessoa" in entry.payload["subject"]
    assert "network-password" not in str(entry.payload)
    assert client.post("/api/v1/auth/refresh").status_code == 200
    assert len(list(db.scalars(select(Outbox).where(Outbox.dedup_key.like("rh-welcome:%"))))) == 1
    assert login(client).status_code == 200
    assert len(list(db.scalars(select(Outbox).where(Outbox.dedup_key.like("rh-welcome:%"))))) == 1


@pytest.mark.usefixtures("policy")
def test_rejected_login_does_not_send_welcome(client, db, monkeypatch):
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: identity("TI"))
    assert login(client).status_code == 403
    assert not db.scalar(select(Outbox.id).where(Outbox.dedup_key.like("rh-welcome:%")))


def test_duplicate_session_does_not_duplicate_welcome_and_disabled_email_is_respected(db, actors, monkeypatch):
    from app.models import User
    user = db.get(User, actors["admin"]["id"])
    runtime = SimpleNamespace(enabled=False, public_url="http://localhost:8088", test_mode=True)
    monkeypatch.setattr("app.services.rh_welcome.smtp_runtime", lambda db: runtime)
    monkeypatch.setattr("app.services.smtp_config.smtp_runtime", lambda db=None: runtime)
    assert queue_welcome(db, user, "a-session") is False
    assert queue_welcome(db, user, "another-session") is False
    runtime.enabled = True
    assert queue_welcome(db, user, "a-session") is True
    assert queue_welcome(db, user, "a-session") is False
    assert queue_welcome(db, user, "another-session") is False
    entry = db.scalar(select(Outbox).where(Outbox.dedup_key == "rh-welcome:user:" + user.id))
    assert "localhost" not in entry.payload["body"]


def test_previous_session_welcome_is_not_sent_again(db, actors, monkeypatch):
    from app.models import User
    user = db.get(User, actors["admin"]["id"])
    db.add(Outbox(kind="EMAIL", dedup_key="rh-welcome:legacy-session", payload={"recipient": user.email, "template": "rh-welcome"}))
    db.flush()
    assert queue_welcome(db, user, "new-session") is False
    assert user.preferences["rh_welcome_queued_at"]


def test_welcome_name_and_copy_are_personal_and_cheerful():
    content = welcome_message("Thauani Gabrielle Pontes Dias", "https://rh.example")
    assert "Olá, Thauani!" in content["body"]
    assert "dia leve" in content["body"]
    assert "https://rh.example/app/vagas" in content["body"]
