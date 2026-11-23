from types import SimpleNamespace

import pytest
from conftest import TEST_PASSWORD

from app.api import auth
from app.core.config import settings
from app.models import User


@pytest.fixture
def portals(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(cfg, "public_url", "https://talentos.portoaurora.example")
    monkeypatch.setattr(cfg, "rh_url", "https://rh-talentos.portoaurora.example")
    monkeypatch.setattr(cfg, "manager_url", "https://gestores-talentos.portoaurora.example")


@pytest.mark.parametrize("actor_key,host,status", [
    ("manager", "gestores-talentos.portoaurora.example", 200),
    ("manager", "rh-talentos.portoaurora.example", 403),
    ("manager", "talentos.portoaurora.example", 403),
    ("admin", "rh-talentos.portoaurora.example", 200),
    ("admin", "gestores-talentos.portoaurora.example", 403),
    ("admin", "unknown.example.com", 403),
])
def test_portal_checks_login_and_existing_token(client, actors, monkeypatch, actor_key, host, status):
    # Enable after the fixture creates its isolated users and sessions.
    for name, value in [("public_url", "https://talentos.portoaurora.example"),
                        ("rh_url", "https://rh-talentos.portoaurora.example"),
                        ("manager_url", "https://gestores-talentos.portoaurora.example")]:
        monkeypatch.setattr(settings(), name, value)
    user = actors[actor_key]
    response = client.post("/api/v1/auth/login", headers={"Host": host}, json={
        "email": user["email"], "password": TEST_PASSWORD,
    })
    assert response.status_code == status, response.text
    if status == 403:
        assert "tgpm_refresh" not in response.cookies
    response = client.get("/api/v1/auth/me", headers={**user["headers"], "Host": host})
    assert response.status_code == status, response.text


def test_internal_email_uses_own_portal(client, db, actors, monkeypatch):
    monkeypatch.setattr(settings(), "rh_url", "https://rh-talentos.portoaurora.example")
    monkeypatch.setattr(settings(), "manager_url", "https://gestores-talentos.portoaurora.example")
    monkeypatch.setattr(auth, "smtp_runtime", lambda _: SimpleNamespace(enabled=True, public_url="https://talentos.portoaurora.example"))
    sent = []
    monkeypatch.setattr(auth, "email", lambda *args: sent.append(args))
    for key, host in [("admin", "rh-talentos"), ("manager", "gestores-talentos")]:
        auth.issue_link(db, db.get(User, actors[key]["id"]), "RESET")
        assert "https://" + host + ".portoaurora.example/confirmar#token=" in sent[-1][3]


def test_manager_recovery_and_refresh_are_bound_to_domain(client, actors, monkeypatch):
    manager = actors["manager"]
    login = client.post("/api/v1/auth/login", json={"email": manager["email"], "password": TEST_PASSWORD})
    cookie = login.cookies["tgpm_refresh"]
    monkeypatch.setattr(settings(), "public_url", "https://talentos.portoaurora.example")
    monkeypatch.setattr(settings(), "rh_url", "https://rh-talentos.portoaurora.example")
    monkeypatch.setattr(settings(), "manager_url", "https://gestores-talentos.portoaurora.example")
    monkeypatch.setattr(auth, "smtp_runtime", lambda _: SimpleNamespace(enabled=True))
    sent = []
    monkeypatch.setattr(auth, "issue_link", lambda *args: sent.append(args))
    for host, expected_count in [("rh-talentos", 0), ("gestores-talentos", 1)]:
        response = client.post("/api/v1/auth/request-link", headers={"Host": host + ".portoaurora.example"},
                               json={"email": manager["email"], "purpose": "RESET"})
        assert response.status_code == 200
        assert len(sent) == expected_count
    response = client.post("/api/v1/auth/refresh", headers={
        "Host": "talentos.portoaurora.example", "Cookie": "tgpm_refresh=" + cookie,
    })
    assert response.status_code == 403
