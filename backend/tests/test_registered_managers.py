from uuid import uuid4

from test_integration import call

from app.models import ManagerAccessRequest, Role, User, UserRole


def test_registered_managers_only_lists_real_manager_accounts(client, db, actors):
    admin = actors["admin"]["headers"]
    reference = User(name="Referência sem conta", email=uuid4().hex + "@example.com",
                     kind="INTERNAL", auth_source="DIRECTORY_REFERENCE", active=True)
    db.add(reference)
    db.flush()
    role = db.query(Role).filter(Role.name == "GESTOR").one()
    db.add(UserRole(user_id=reference.id, role_id=role.id))
    db.add(ManagerAccessRequest(name="Cadastro pendente", email=uuid4().hex + "@example.com", department="TI"))
    db.commit()
    result = call(client, "get", "/registered-managers", admin)
    ids = {row["id"] for row in result["items"]}
    assert ids == {actors["manager"]["id"], actors["outsider"]["id"]}
    assert all(set(row) == {"id", "name", "email", "org_unit_name", "active", "version", "created_at"} for row in result["items"])
    assert all(row["org_unit_name"] != "Setor não informado" for row in result["items"])
    assert call(client, "get", "/registered-managers?q=Cadastro%20pendente", admin)["total"] == 0
    db.get(User, actors["manager"]["id"]).active = False
    db.commit()
    inactive = call(client, "get", "/registered-managers?active=false", admin)
    assert [row["id"] for row in inactive["items"]] == [actors["manager"]["id"]]
    assert call(client, "get", "/registered-managers?active=true", admin)["total"] == 1
    assert call(client, "get", "/registered-managers?page_size=1&page_number=2", admin)["page"] == 2
    call(client, "get", "/registered-managers", actors["outsider"]["headers"], expected=403)
    call(client, "get", "/registered-managers", {}, expected=401)


def test_rh_creates_manager_and_controls_access(client, db, actors):
    email = uuid4().hex + "@portoaurora.example"
    admin = actors["admin"]["headers"]
    body = {"name": "Gestor cadastrado pelo RH", "email": email, "password": "Tg@123",
            "roles": ["GESTOR"], "org_unit_id": actors["org"], "auth_source": "LOCAL"}
    created = call(client, "post", "/users", admin, body, 201)
    result = call(client, "get", "/registered-managers?q=" + email, admin)
    assert result["total"] == 1
    manager = result["items"][0]
    assert manager["id"] == created["id"]
    call(client, "post", "/auth/login", {}, {"email": email, "password": "Tg@123", "area": "GESTOR"})
    manager = call(client, "get", "/registered-managers?q=" + email, admin)["items"][0]
    call(client, "put", "/users/" + created["id"] + "/status", admin,
         {"active": False, "version": manager["version"], "reason": "Acesso de teste desativado"})
    assert not db.get(User, created["id"]).active


def test_manager_creation_requires_corporate_email_and_sector(client, actors):
    admin = actors["admin"]["headers"]
    body = {"name": "Gestor teste", "email": uuid4().hex + "@example.com", "password": "Tg@123",
            "roles": ["GESTOR"], "org_unit_id": actors["org"]}
    call(client, "post", "/users", admin, body, 422)
    body["email"] = uuid4().hex + "@portoaurora.example"
    body["org_unit_id"] = None
    call(client, "post", "/users", admin, body, 422)
    call(client, "post", "/users", actors["outsider"]["headers"], body, 403)
