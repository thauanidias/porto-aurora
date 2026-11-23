import re
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_integration import call

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.security import digest, hash_password
from app.models import AuthToken, Candidate, EmployeeAccessRequest, Outbox, User


@pytest.fixture(autouse=True)
def employee_mail(monkeypatch):
    monkeypatch.setattr("app.services.employee_access.smtp_runtime", lambda db: SimpleNamespace(enabled=True))


def latest_code(db, address):
    entry = db.scalar(select(Outbox).where(Outbox.kind == "EMAIL", Outbox.payload["recipient"].astext == address).order_by(Outbox.created_at.desc()))
    return re.search(r"\b([0-9]{6})\b", entry.payload["body"]).group(1)


@pytest.mark.parametrize("domain", ["portoaurora.example", "example.com"])
def test_name_email_password_registration_requires_code_before_activation(client, db, domain):
    address = "staged-" + uuid4().hex[:8] + "@" + domain
    initial = call(client, "post", "/auth/register-employee", {}, {"name": "Colaborador Teste", "email": address}, 201)
    row = db.get(EmployeeAccessRequest, initial["registration_id"])
    assert row.network_username.startswith("pending-") and not row.email_confirmed_at
    assert not db.scalar(select(User.id).where(User.email == address))
    details = {"password": "Ep42!?"}
    call(client, "post", "/auth/employee-registration/complete", {}, {**details, "completion_token": row.id}, 400)
    verified = call(client, "post", "/auth/employee-email-code/confirm", {}, {"registration_id": row.id, "code": latest_code(db, address)})
    call(client, "post", "/auth/login", {}, {"email": address, "password": "AD-password", "source": "LDAP"}, 403)
    call(client, "post", "/auth/employee-registration/complete", {}, {**details, "completion_token": verified["completion_token"]})
    user = db.get(User, row.user_id)
    assert user.auth_source == "LOCAL" and user.email_verified and user.password_hash != details["password"]
    assert row.status == "VERIFIED"
    call(client, "post", "/auth/employee-registration/complete", {}, {**details, "completion_token": verified["completion_token"]}, 409)
    credentials = {"email": address, "password": details["password"], "source": "LOCAL", "area": "CANDIDATO"}
    call(client, "post", "/auth/login", {}, {**credentials, "password": "Wrong-password"}, 401)
    result = call(client, "post", "/auth/login", {}, credentials)
    headers = {"Authorization": "Bearer " + result["access_token"]}
    assert "internal.view" in call(client, "get", "/auth/me", headers)["permissions"]
    call(client, "get", "/internal/vacancies", headers)
    call(client, "get", "/manager-access-requests", headers, expected=403)


def registration(client, domain="portoaurora.example", expected=201, confirm=True):
    username = "employee-" + uuid4().hex[:8]
    data = {"name": "Colaborador Teste", "email": username + "@" + domain,
            "network_username": username, "department": "Operações"}
    result = call(client, "post", "/auth/register-employee", {}, data, expected)
    if expected == 201 and confirm:
        call(client, "post", "/auth/employee-email-code/confirm", {}, {
            "registration_id": result["registration_id"], "code": latest_code(client.test_db, data["email"]),
        })
    return data


@pytest.mark.parametrize("domain", ["gmail.com", "portoaurora.example.evil.com", "sub.portoaurora.example"])
def test_employee_registration_accepts_personal_email(client, db, domain):
    data = registration(client, domain, 201, confirm=False)
    assert db.scalar(select(EmployeeAccessRequest.id).where(EmployeeAccessRequest.email == data["email"]))


def test_employee_ad_login_activates_only_after_directory_validation(client, db, monkeypatch):
    data = registration(client)
    assert not db.scalar(select(User.id).where(User.email == data["email"]))
    calls = []

    def authenticate(username, password, *, expected_email):
        calls.append((username, expected_email))
        return password == "Valid-AD-password"

    monkeypatch.setattr("app.integrations.ldap.authenticate", authenticate)
    credentials = {"email": data["network_username"], "password": "Wrong-password", "source": "LDAP", "area": "CANDIDATO"}
    call(client, "post", "/auth/login", {}, credentials, 401)
    assert not db.scalar(select(User.id).where(User.email == data["email"]))
    credentials["password"] = "Valid-AD-password"
    result = call(client, "post", "/auth/login", {}, credentials)
    headers = {"Authorization": "Bearer " + result["access_token"]}
    session = call(client, "get", "/auth/me", headers)
    assert session["user"]["kind"] == "CANDIDATO"
    assert session["user"]["email_verified"] is True
    assert session["permissions"] == ["internal.view", "referral.create"]
    user = db.scalar(select(User).where(User.email == data["email"]))
    assert user.auth_source == "LDAP" and not user.password_hash
    assert db.scalar(select(Candidate.id).where(Candidate.user_id == user.id))
    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.email == data["email"]))
    assert row.status == "VERIFIED" and row.user_id == user.id
    assert calls == [(data["network_username"], data["email"])] * 2
    call(client, "get", "/internal/vacancies", headers)
    call(client, "get", "/manager-access-requests", headers, expected=403)
    user.password_hash = hash_password(credentials["password"])
    db.flush()
    call(client, "post", "/auth/login", {}, {**credentials, "email": data["email"], "source": "LOCAL"}, 401)
    raw_token = uuid4().hex
    db.add(AuthToken(user_id=user.id, token_hash=digest(raw_token), purpose="RESET", expires_at=utcnow() + timedelta(minutes=10)))
    db.flush()
    call(client, "post", "/auth/consume-link", {}, {"token": raw_token, "password": "Np42!?"}, 403)
    call(client, "post", "/auth/password", headers, {"current_password": credentials["password"], "new_password": "Np42!?"}, 403)
    call(client, "post", "/auth/login", {}, credentials)
    assert len(list(db.scalars(select(Candidate.id).where(Candidate.user_id == user.id)))) == 1
    user.active = False
    db.flush()
    count = len(calls)
    call(client, "post", "/auth/login", {}, credentials, 401)
    assert len(calls) == count


def test_ad_unavailable_never_provisions_employee(client, db, monkeypatch):
    data = registration(client)

    def unavailable(*args, **kwargs):
        raise DomainError("AD indisponível", 503)

    monkeypatch.setattr("app.integrations.ldap.authenticate", unavailable)
    call(client, "post", "/auth/login", {}, {"email": data["network_username"], "password": "Password", "source": "LDAP"}, 503)
    assert not db.scalar(select(User.id).where(User.email == data["email"]))


def test_duplicate_employee_registration_is_rejected(client):
    data = registration(client)
    call(client, "post", "/auth/register-employee", {}, data, 409)


def test_email_code_required_before_ad_and_cannot_be_reused(client, db, monkeypatch):
    data = registration(client, confirm=False)
    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.email == data["email"]))
    from unittest.mock import Mock
    directory = Mock(return_value=True)
    monkeypatch.setattr("app.integrations.ldap.authenticate", directory)
    call(client, "post", "/auth/login", {}, {"email": data["network_username"], "password": "AD-password", "source": "LDAP"}, 403)
    directory.assert_not_called()
    assert not db.scalar(select(User.id).where(User.email == data["email"]))
    code = latest_code(db, row.email)
    assert row.email_code_hash != code
    payload = {"registration_id": row.id, "code": code}
    call(client, "post", "/auth/employee-email-code/confirm", {}, payload)
    assert row.email_confirmed_at and row.email_code_hash is None
    call(client, "post", "/auth/employee-email-code/confirm", {}, payload, 400)


def test_email_code_expiration_attempt_limit_and_resend(client, db):
    data = registration(client, confirm=False)
    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.email == data["email"]))
    code = latest_code(db, row.email)
    resend = {"registration_id": row.id}
    call(client, "post", "/auth/employee-email-code/resend", {}, resend, 429)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        call(client, "post", "/auth/employee-email-code/confirm", {}, {**resend, "code": wrong}, 400)
    assert row.email_code_attempts == 5
    call(client, "post", "/auth/employee-email-code/confirm", {}, {**resend, "code": code}, 429)
    row.email_code_sent_at = utcnow() - timedelta(seconds=61)
    db.flush()
    call(client, "post", "/auth/employee-email-code/resend", {}, resend)
    assert row.email_code_attempts == 0
    row.email_code_expires_at = utcnow() - timedelta(seconds=1)
    db.flush()
    call(client, "post", "/auth/employee-email-code/confirm", {}, {**resend, "code": latest_code(db, row.email)}, 400)
    assert not row.email_confirmed_at


def test_no_registration_claimed_when_smtp_is_disabled(client, db, monkeypatch):
    monkeypatch.setattr("app.services.employee_access.smtp_runtime", lambda db: SimpleNamespace(enabled=False))
    data = registration(client, expected=503, confirm=False)
    assert not db.scalar(select(EmployeeAccessRequest.id).where(EmployeeAccessRequest.email == data["email"]))


def test_resend_replaces_old_code_and_registration_can_resume(client, db, monkeypatch):
    monkeypatch.setattr("app.services.employee_access.secrets.randbelow", lambda n: 123456)
    data = registration(client, confirm=False)
    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.email == data["email"]))
    resumed = call(client, "post", "/auth/register-employee", {}, data, 201)
    assert resumed["registration_id"] == row.id
    row.email_code_sent_at = utcnow() - timedelta(seconds=61)
    db.flush()
    monkeypatch.setattr("app.services.employee_access.secrets.randbelow", lambda n: 654321)
    call(client, "post", "/auth/employee-email-code/resend", {}, {"registration_id": row.id})
    call(client, "post", "/auth/employee-email-code/confirm", {}, {"registration_id": row.id, "code": "123456"}, 400)
    call(client, "post", "/auth/employee-email-code/confirm", {}, {"registration_id": row.id, "code": "654321"})


def test_directory_email_must_match_before_password_bind(monkeypatch):
    from types import SimpleNamespace

    from app.integrations import ldap

    cfg = SimpleNamespace(ldap_enabled=True, ldap_url="ldaps://directory.example.com", ldap_ca_cert_file="",
                          ldap_bind_dn="service", ldap_bind_password=SimpleNamespace(get_secret_value=lambda: "secret"),
                          ldap_base_dn="dc=example,dc=com", ldap_user_filter="(sAMAccountName={username})")
    connections = []
    class Service:
        entries = [SimpleNamespace(entry_dn="cn=other", mail=SimpleNamespace(value="other@portoaurora.example"))]
        def search(self, *args, **kwargs):
            pass
        def unbind(self):
            pass

    def connection(*args, **kwargs):
        connections.append(kwargs)
        return Service()

    monkeypatch.setattr(ldap, "settings", lambda: cfg)
    monkeypatch.setattr(ldap, "Connection", connection)
    assert ldap.authenticate("employee", "Password", expected_email="employee@portoaurora.example") is False
    assert len(connections) == 1
