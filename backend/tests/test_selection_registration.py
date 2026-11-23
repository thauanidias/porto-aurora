import json

import pytest
from external_helpers import complete_data
from sqlalchemy import select
from test_candidate_journey import (  # noqa: F401
    advance,
    enroll,
    journey_owner,
    register_basic_candidate,
)
from test_integration import call

from app.core.security import decrypt
from app.models import SensitiveData

PATH = "/candidates/me/selection-registration"


@pytest.fixture
def registration_owner(client, journey_owner):  # noqa: F811 - imported pytest fixture
    headers, job, admin, _ = journey_owner
    application = enroll(client, headers, job)
    application = advance(client, admin, application, job, "SELECTION")
    call(client, "post", "/applications/" + application["id"] + "/approve-screening", admin,
         {"version": application["version"], "reason": "Curriculo conferido para liberar a ficha"})
    issued = call(client, "post", "/applications/" + application["id"] + "/my-process-form", headers, {})
    token = issued["link"].split("#token=")[1]
    call(client, "post", "/public/process-forms/submit", {}, {"token": token, "answers": {"interest": "Interesse nesta oportunidade"}, "consent": True})
    return headers, call(client, "get", "/candidates/me", headers), None


def test_registration_roundtrip_encryption_and_optional_data_preserved(client, db, registration_owner):
    owner, candidate, _ = registration_owner
    initial_profile = call(client, "get", "/candidates/me", owner)
    assert call(client, "get", PATH, owner)["data"] is None
    call(client, "put", "/candidates/me/sensitive", owner, {
        "data": {"pcd": "Informação de teste"}, "consent": True,
        "purpose": "Adaptações da entrevista de teste",
    })
    payload = {
        "desired_position": "Operador de teste",
        "personal": {"name": "Candidato de Teste", "birth_date": "1990-01-02"},
        "documents": {"cpf": "000.000.000-00", "rg": "RG de teste"},
        "bank": {"branch": "TEST", "checking_account": "TEST-123"},
        "dependents": [{"name": "Dependente de Teste", "income_tax_dependent": "Não"}],
        "languages": {"english": "Intermediário"},
        "education": {"extension": "Completo", "extension_course": "Curso de teste"},
        "complementary": {"flexible_weekends": "Não", "weekend_restrictions": "Domingo"},
    }
    saved = call(client, "put", PATH, owner, {"data": payload, "version": 0})
    assert saved["version"] == 1
    assert saved["confirmed_at"] is None
    assert saved == call(client, "get", PATH, owner)
    assert saved["data"]["dependents"][0]["name"] == "Dependente de Teste"
    assert saved["data"]["complementary"]["weekend_restrictions"] == "Domingo"
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate["id"]))
    assert "TEST-123" not in row.encrypted_data
    decrypted = json.loads(decrypt(row.encrypted_data))
    assert decrypted["pcd"] == "Informação de teste"
    call(client, "put", "/candidates/me/sensitive", owner, {
        "data": {"accessibility_needs": "Outra informação de teste"}, "consent": True,
        "purpose": "Adaptações da entrevista de teste",
    })
    assert call(client, "get", PATH, owner) == saved
    assert call(client, "get", "/candidates/me", owner) == initial_profile


def test_registration_is_private_and_rejects_overwrite(client, actors, registration_owner):
    owner, _, notice = registration_owner
    other, _, _ = register_basic_candidate(client)
    saved = call(client, "put", PATH, owner, {"data": {"desired_position": "Teste"}, "version": 0})
    assert call(client, "get", PATH, other)["data"] is None
    assert client.get("/api/v1" + PATH).status_code == 401
    assert client.get("/api/v1" + PATH, headers=actors["manager"]["headers"]).status_code == 403
    assert client.put("/api/v1" + PATH, headers=actors["admin"]["headers"],
                      json={"data": {}, "version": 0}).status_code == 403
    assert client.put("/api/v1" + PATH, headers=owner,
                      json={"data": {}, "version": 0}).status_code == 409
    assert call(client, "get", PATH, owner) == saved
    again = call(client, "put", PATH, owner, {"data": saved["data"], "version": 1})
    assert again["version"] == 2


def test_registration_confirmations_and_limits(client, registration_owner):
    owner, _, _ = registration_owner
    for data in (
        {"declaration": {"accepted": True}},
        {"dependents": [{}] * 7},
        {"employment": {"admission_date": "2024-01-01", "departure_date": "2023-12-31"}},
        {"unexpected_field": "extra"},
    ):
        assert client.put("/api/v1" + PATH, headers=owner,
                          json={"data": data, "version": 0}).status_code == 422
    saved = call(client, "put", PATH, owner, {"data": complete_data(), "version": 0})
    assert saved["confirmed_at"]
    saved["data"]["declaration"]["accepted"] = False
    draft = call(client, "put", PATH, owner, {"data": saved["data"], "version": 1})
    assert draft["confirmed_at"] is None


def test_rh_form_permission_opens_signed_sheet_without_optional_sensitive_data(client, db, actors, registration_owner):
    from sqlalchemy import delete
    from app.models import RolePermission, UserRole
    owner, candidate, _ = registration_owner
    call(client, "put", "/candidates/me/sensitive", owner, {"data": {"pcd": "Informação reservada"}, "consent": True, "purpose": "Adaptações da entrevista"})
    call(client, "put", PATH, owner, {"data": complete_data(), "version": 0})
    roles = select(UserRole.role_id).where(UserRole.user_id == actors["admin"]["id"])
    db.execute(delete(RolePermission).where(RolePermission.role_id.in_(roles), RolePermission.permission == "candidate.sensitive.view"))
    db.flush()
    admin = actors["admin"]["headers"]
    detail = call(client, "get", "/candidates/" + candidate["id"] + "/selection-documents", admin)
    assert detail["registration"]["confirmed_at"]
    assert detail["registration"]["signature_record"]["protocol"]
    assert detail["accessibility"] == {}
    assert call(client, "get", "/candidates/" + candidate["id"] + "/selection-registration-download", admin)["available"]
    assert client.get("/api/v1/candidates/" + candidate["id"] + "/selection-registration.xlsx", headers=admin).status_code == 200
    assert client.get("/api/v1/candidates/" + candidate["id"] + "/selection-documents", headers=actors["outsider"]["headers"]).status_code == 404
