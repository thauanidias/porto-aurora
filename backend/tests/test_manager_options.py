from uuid import uuid4

from app.models import User


def test_manager_organization_options_only_include_own_structure(client, db, actors):
    manager = actors["manager"]
    response = client.get("/api/v1/org", headers=manager["headers"])
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["items"]] == [actors["org"]]
    admin = client.get("/api/v1/org", headers=actors["admin"]["headers"])
    assert {actors["org"], actors["other_org"]} <= {row["id"] for row in admin.json()["items"]}
    db.get(User, manager["id"]).org_unit_id = None
    db.commit()
    assert client.get("/api/v1/org", headers=manager["headers"]).json()["items"] == []


def test_vacancy_people_options_keep_directory_managers_out_of_recruiters(client, db, actors):
    directory_manager = User(
        email=f"directory-{uuid4().hex[:8]}@example.com",
        name="Gestora do Diretório",
        kind="INTERNAL",
        active=True,
        auth_source="DIRECTORY_REFERENCE",
        password_hash="",
        preferences={"directory_manager": True},
    )
    rh_recruiter = User(
        email=f"rh-{uuid4().hex[:8]}@example.com",
        name="Recrutadora do RH",
        kind="INTERNAL",
        active=True,
        auth_source="DIRECTORY_REFERENCE",
        password_hash="",
        preferences={"directory_recruiter": True},
    )
    db.add_all([directory_manager, rh_recruiter])
    db.commit()

    headers = actors["admin"]["headers"]
    managers = client.get("/api/v1/managers", headers=headers)
    recruiters = client.get("/api/v1/recruiters", headers=headers)

    assert managers.status_code == 200
    assert recruiters.status_code == 200
    assert directory_manager.id in {row["id"] for row in managers.json()["items"]}
    assert actors["manager"]["id"] in {row["id"] for row in managers.json()["items"]}
    assert directory_manager.id not in {row["id"] for row in recruiters.json()["items"]}
    assert rh_recruiter.id in {row["id"] for row in recruiters.json()["items"]}
    assert actors["admin"]["id"] not in {row["id"] for row in recruiters.json()["items"]}
