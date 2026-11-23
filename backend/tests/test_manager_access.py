from uuid import uuid4

import pytest
from sqlalchemy import select
from test_integration import call

from app.models import Candidate, ConfigRecord, ManagerAccessRequest, User


@pytest.mark.parametrize("domain", ["gmail.com", "portoaurora.example.evil.com", "sub.portoaurora.example", "pontadamontanha.net"])
def test_manager_rejects_noncorporate_email(client, db, domain):
    address = "gestor@" + domain
    call(client, "post", "/auth/register-manager", {}, {
        "name": "Gestor Teste", "email": address, "department": "TI",
    }, 422)
    assert not db.scalar(select(ManagerAccessRequest.id).where(ManagerAccessRequest.email == address))


def test_manager_accepts_uppercase_corporate_domain(client, db):
    address = "gestor-" + uuid4().hex[:8] + "@PONTADAMONTANHA.COM"
    call(client, "post", "/auth/register-manager", {}, {
        "name": "Gestor Teste", "email": address, "department": "TI",
    }, 201)
    assert db.scalar(select(ManagerAccessRequest.id).where(ManagerAccessRequest.email == address.lower()))


def test_manager_self_registration_requires_rh_approval(client, db, actors):
    address = "manager-access-" + uuid4().hex[:8] + "@portoaurora.example"
    payload = {"name": "Gestor Solicitante", "email": address, "department": "Operações"}
    call(client, "post", "/auth/register-manager", {}, payload, 201)
    assert not db.scalar(select(User.id).where(User.email == address))
    assert not db.scalar(select(Candidate.id).where(Candidate.email == address))
    call(client, "post", "/auth/register-manager", {}, payload, 409)
    row = db.scalar(select(ManagerAccessRequest).where(ManagerAccessRequest.email == address))
    call(client, "get", "/manager-access-requests", {}, expected=401)
    call(client, "get", "/manager-access-requests", actors["manager"]["headers"], expected=403)
    approved = call(client, "post", "/manager-access-requests/" + row.id + "/review",
        actors["admin"]["headers"], {"version": row.version, "org_unit_id": actors["org"]})
    assert approved["status"] == "APPROVED"
    assert "%2Fgestor" in approved["test_setup_url"]
    token = approved["test_setup_url"].split("#token=")[1].split("&")[0]
    login = call(client, "post", "/auth/consume-link", {}, {"token": token, "password": "Tg@123"})
    headers = {"Authorization": "Bearer " + login["access_token"]}
    session = call(client, "get", "/auth/me", headers)
    assert session["user"]["kind"] == "INTERNAL"
    assert session["user"]["org_unit_id"] == actors["org"]
    assert "request.create" in session["permissions"]
    assert "user.manage" not in session["permissions"]
    assert "request.approve" not in session["permissions"]
    assert not db.scalar(select(Candidate.id).where(Candidate.email == address))
    assert db.scalar(select(ConfigRecord.id).where(ConfigRecord.kind == "workflows", ConfigRecord.data["target"].astext == "REQUEST"))
    call(client, "post", "/manager-access-requests/" + row.id + "/review",
        actors["admin"]["headers"], {"version": approved["version"], "org_unit_id": actors["org"]}, 409)


def test_rejected_manager_request_does_not_create_access(client, db, actors):
    address = "rejected-" + uuid4().hex[:8] + "@portoaurora.example"
    call(client, "post", "/auth/register-manager", {}, {"name": "Outro Gestor", "email": address, "department": "Outro setor"}, 201)
    row = db.scalar(select(ManagerAccessRequest).where(ManagerAccessRequest.email == address))
    rejected = call(client, "post", "/manager-access-requests/" + row.id + "/review",
        actors["admin"]["headers"], {"version": row.version, "approve": False, "reason": "Solicitante não identificado como gestor"})
    assert rejected["status"] == "REJECTED"
    assert not db.scalar(select(User.id).where(User.email == address))


@pytest.mark.parametrize("actor_key,area,expected", [
    ("manager", "GESTOR", 200),
    ("manager", "RH", 403),
    ("admin", "RH", 200),
    ("admin", "GESTOR", 403),
    ("manager", "CANDIDATO", 403),
])
def test_login_requires_matching_area(client, db, actors, actor_key, area, expected):
    from conftest import TEST_PASSWORD
    from sqlalchemy import func

    from app.models import AuthSession

    user = actors[actor_key]
    count = db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user["id"]))
    response = call(client, "post", "/auth/login", {}, {
        "email": user["email"], "password": TEST_PASSWORD, "area": area,
    }, expected)
    if expected == 403:
        assert response["code"] == "WRONG_ACCESS_AREA"
        assert db.scalar(select(func.count()).select_from(AuthSession).where(AuthSession.user_id == user["id"])) == count
