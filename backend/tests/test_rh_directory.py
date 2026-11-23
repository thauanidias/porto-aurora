from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.integrations.ldap import corporate_account
from app.models import AuthSession, User
from app.services.directory_access import directory_allowed, provision_rh


@pytest.fixture
def policy(monkeypatch):
    cfg = settings()
    monkeypatch.setattr(cfg, "ldap_enabled", True)
    monkeypatch.setattr(cfg, "ldap_rh_only", True)
    monkeypatch.setattr(cfg, "ldap_rh_access_mode", "directory")
    monkeypatch.setattr(cfg, "ldap_rh_store_password", False)
    monkeypatch.setattr(cfg, "ldap_upn_suffix", "company.example")
    monkeypatch.setattr(cfg, "ldap_netbios_domain", "COMPANY")
    monkeypatch.setattr(cfg, "ldap_rh_departments", "RH")
    monkeypatch.setattr(cfg, "ldap_rh_exception_ids", "")
    monkeypatch.setattr(cfg, "ldap_rh_role", "RECRUTADOR")
    return cfg


def identity(department="RH"):
    return {"directory_id": str(uuid4()), "account": "person.test", "name": "Pessoa Corporativa",
            "email": "directory-" + uuid4().hex + "@example.com", "department": department}


def login(client, source="LDAP"):
    return client.post("/api/v1/auth/login", json={"email": "person.test", "password": "network-password", "source": source, "area": "RH"})


def test_ad_department_provisions_a_network_account_without_password_or_candidate(client, db, policy, monkeypatch):
    person = identity()
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: person)
    response = login(client)
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert "vacancy.create" in me.json()["permissions"]
    user = db.scalar(select(User).where(User.email == person["email"]))
    assert user.auth_source == "LDAP" and not user.password_hash and user.kind == "INTERNAL"
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)).directory_auth["directory_id"] == person["directory_id"]
    again = login(client)
    assert again.status_code == 200
    assert len(list(db.scalars(select(User).where(User.email == person["email"])))) == 1


def test_people_outside_rh_are_denied_without_creating_users(client, db, policy, monkeypatch):
    person = identity("TI")
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: person)
    assert login(client).status_code == 403
    assert db.scalar(select(User.id).where(User.email == person["email"])) is None


def test_named_exception_uses_immutable_ad_id_not_a_claimed_name(client, policy, monkeypatch):
    person = identity("TI")
    monkeypatch.setattr(policy, "ldap_rh_exception_ids", person["directory_id"])
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: person)
    assert login(client).status_code == 200
    assert not directory_allowed({**person, "directory_id": str(uuid4())})


def test_bad_ad_password_does_not_fall_back_to_local_or_provision(client, db, policy, monkeypatch):
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: None)
    assert login(client).status_code == 401


def test_old_local_admin_tokens_and_refresh_cannot_bypass_ad(client, actors, monkeypatch):
    monkeypatch.setattr(settings(), "ldap_rh_only", True)
    result = client.get("/api/v1/auth/me", headers=actors["admin"]["headers"])
    assert result.status_code == 401
    # Candidate and manager policies are unchanged by the RH-only restriction.
    assert client.get("/api/v1/auth/me", headers=actors["manager"]["headers"]).status_code == 200


def test_ad_proof_expires_and_refresh_requires_network_reauthentication(client, db, policy, monkeypatch):
    person = identity()
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", lambda *args: person)
    response = login(client)
    assert response.status_code == 200
    user = db.scalar(select(User).where(User.email == person["email"]))
    session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    session.directory_auth = {**session.directory_auth, "verified_at": (utcnow() - timedelta(minutes=31)).isoformat()}
    db.commit()
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_network_identifier_formats_and_foreign_domains(policy):
    for account in ["person.test", "COMPANY\\person.test", "person.test@company.example"]:
        assert corporate_account(account) == ("person.test", "person.test@company.example")
    for account in ["OTHER\\person.test", "person.test@foreign.example", "person*)(name=*"]:
        with pytest.raises(DomainError):
            corporate_account(account)


def test_ad_integration_only_binds_and_reads_without_groups_or_directory_writes(policy, monkeypatch):
    from app.integrations import ldap
    policy.ldap_url = "ldaps://directory.company.example"
    policy.ldap_base_dn = "DC=company,DC=example"
    directory_id = str(uuid4())
    entry = SimpleNamespace(**{key: SimpleNamespace(value=value) for key, value in {
        "objectGUID": "{" + directory_id + "}", "displayName": "Pessoa RH", "mail": "person@company.example",
        "department": "RH", "sAMAccountName": "person.test", "userAccountControl": 512}.items()})
    connection = Mock(entries=[entry])
    connection_factory = Mock(return_value=connection)
    tls = Mock()
    monkeypatch.setattr(ldap, "Connection", connection_factory)
    monkeypatch.setattr(ldap, "Server", Mock())
    monkeypatch.setattr(ldap, "Tls", tls)
    result = ldap.authenticate_directory("person.test", "network-password")
    assert result["department"] == "RH" and result["directory_id"] == directory_id
    assert connection_factory.call_args.kwargs["user"] == "person.test@company.example"
    assert "memberOf" not in str(connection.search.call_args)
    for method in [connection.modify, connection.add, connection.delete, connection.modify_dn]:
        method.assert_not_called()
    connection.unbind.assert_called_once()
    assert tls.call_args.kwargs["validate"] == __import__("ssl").CERT_REQUIRED


def test_saved_account_stays_saved_without_department_lookup_and_without_thirty_minute_relogin(client, db, policy, monkeypatch):
    person = identity()
    user = provision_rh(db, person)
    db.flush()
    monkeypatch.setattr(policy, "ldap_rh_access_mode", "saved")
    directory = Mock(side_effect=AssertionError("A saved login must not fetch the AD profile"))
    credentials = Mock(return_value=True)
    monkeypatch.setattr("app.integrations.ldap.authenticate_directory", directory)
    monkeypatch.setattr("app.integrations.ldap.authenticate_saved_account", credentials)
    result = login(client)
    assert result.status_code == 200, result.text
    credentials.assert_called_once_with(person["account"], "network-password", person["directory_id"])
    directory.assert_not_called()
    session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
    session.directory_auth = {**session.directory_auth, "verified_at": (utcnow() - timedelta(hours=2)).isoformat()}
    db.commit()
    headers = {"Authorization": "Bearer " + result.json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/refresh").status_code == 200
    credentials.assert_called_once()
    directory.assert_not_called()
    assert user.name == person["name"] and user.email == person["email"]


def test_saved_access_never_imports_unlisted_accounts(client, db, policy, monkeypatch):
    monkeypatch.setattr(policy, "ldap_rh_access_mode", "saved")
    credentials = Mock()
    monkeypatch.setattr("app.integrations.ldap.authenticate_saved_account", credentials)
    before = len(list(db.scalars(select(User))))
    assert login(client).status_code == 403
    credentials.assert_not_called()
    assert len(list(db.scalars(select(User)))) == before


def test_saved_access_still_requires_the_network_password_and_local_enablement(client, db, policy, monkeypatch):
    user = provision_rh(db, identity())
    db.commit()
    monkeypatch.setattr(policy, "ldap_rh_access_mode", "saved")
    credentials = Mock(return_value=False)
    monkeypatch.setattr("app.integrations.ldap.authenticate_saved_account", credentials)
    assert login(client).status_code == 401
    user.active = False
    db.commit()
    credentials.reset_mock()
    assert login(client).status_code == 403
    credentials.assert_not_called()


def test_saved_bind_only_checks_the_persisted_identity_not_department(policy, monkeypatch):
    from app.integrations import ldap
    monkeypatch.setattr(policy, "ldap_url", "ldaps://directory.company.example")
    monkeypatch.setattr(policy, "ldap_base_dn", "DC=company,DC=example")
    connection = Mock(bound=True, entries=[Mock()])
    monkeypatch.setattr(ldap, "Connection", Mock(return_value=connection))
    monkeypatch.setattr(ldap, "Server", Mock())
    monkeypatch.setattr(ldap, "Tls", Mock())
    assert ldap.authenticate_saved_account("person.test", "network-password", str(uuid4()))
    assert connection.search.call_args.kwargs["attributes"] == ["objectGUID"]
    assert "department" not in str(connection.search.call_args)
    assert "memberOf" not in str(connection.search.call_args)
    connection.modify.assert_not_called()
    connection.add.assert_not_called()


def test_saved_password_is_argon2_and_later_logins_never_call_ad(client, db, policy, monkeypatch):
    from app.core.security import verify_password
    user = provision_rh(db, identity())
    db.commit()
    monkeypatch.setattr(policy, "ldap_rh_access_mode", "saved")
    monkeypatch.setattr(policy, "ldap_rh_store_password", True)
    credentials = Mock(return_value=True)
    monkeypatch.setattr("app.integrations.ldap.authenticate_saved_account", credentials)
    response = login(client)
    assert response.status_code == 200
    db.refresh(user)
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "network-password"
    assert verify_password("network-password", user.password_hash)
    assert "password_hash" not in response.json()["user"]
    assert "network-password" not in str(user.preferences)
    credentials.assert_called_once()
    credentials.reset_mock()
    assert login(client).status_code == 200
    wrong = client.post("/api/v1/auth/login", json={"email": "person.test", "password": "wrong-password", "source": "LDAP", "area": "RH"})
    assert wrong.status_code == 401
    credentials.assert_not_called()


def test_saved_password_update_requires_ad_and_revokes_old_sessions(client, db, policy, monkeypatch):
    from app.core.security import verify_password
    user = provision_rh(db, identity())
    db.commit()
    monkeypatch.setattr(policy, "ldap_rh_access_mode", "saved")
    monkeypatch.setattr(policy, "ldap_rh_store_password", True)
    credentials = Mock(return_value=True)
    monkeypatch.setattr("app.integrations.ldap.authenticate_saved_account", credentials)
    original = login(client)
    assert original.status_code == 200
    new_password = "AD123!xy"
    updated = client.post("/api/v1/auth/login", json={"email": "person.test", "password": new_password,
        "source": "LDAP", "area": "RH", "revalidate_network_password": True})
    assert updated.status_code == 200, updated.text
    db.refresh(user)
    assert verify_password(new_password, user.password_hash)
    assert not verify_password("network-password", user.password_hash)
    assert credentials.call_count == 2
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + original.json()["access_token"]}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + updated.json()["access_token"]}).status_code == 200


def test_reimporting_directory_data_preserves_an_enrolled_hash(db, policy, monkeypatch):
    from app.core.security import hash_verified_network_password
    person = identity()
    user = provision_rh(db, person)
    monkeypatch.setattr(policy, "ldap_rh_store_password", True)
    user.password_hash = hash_verified_network_password("network-password")
    user.preferences = {**user.preferences, "rh_password_enrolled_at": utcnow().isoformat()}
    db.flush()
    protected = user.password_hash
    assert provision_rh(db, person).password_hash == protected
