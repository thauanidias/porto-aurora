import test_candidate_journey
from consent_helpers import consent_signature
from test_candidate_journey import advance, enroll
from test_integration import call

journey_owner = test_candidate_journey.journey_owner


def test_rh_sees_phase_and_selection_documents_with_scoped_permissions(client, actors, journey_owner):
    owner, job, admin, _ = journey_owner
    app = enroll(client, owner, job)
    details = call(client, "get", "/applications/" + app["id"], admin)
    assert details["candidate_access"]["phase"] == "RECRUITMENT"
    app = advance(client, admin, app, job, "SELECTION")
    details = call(client, "get", "/applications/" + app["id"], admin)
    assert details["candidate_access"]["permissions"]["selection_registration"] is False
    app = call(client, "post", "/applications/" + app["id"] + "/approve-screening", admin,
               {"version": app["version"], "reason": "Curriculo conferido e aprovado pelo RH"})
    details = call(client, "get", "/applications/" + app["id"], admin)
    assert details["candidate_access"]["permissions"]["selection_registration"] is True
    assert details["candidate_access"]["permissions"]["questions"] is False
    profile = call(client, "get", "/candidates/me", owner)
    call(client, "put", "/candidates/me/selection-registration", owner,
         {"data": {"desired_position": "Operador"}, "version": 0})
    call(client, "put", "/candidates/me/sensitive", owner,
         {"data": {"accessibility_needs": "Local acessível"}, "purpose": "Adaptar a entrevista do candidato", "consent": True})
    receipt = call(client, "post", "/public/consent-receipts", owner,
         {"name": profile["name"], "email": profile["email"], "context": "CADASTRO", "accepted": True, "signature_image": consent_signature()}, 201)
    path = "/candidates/" + profile["id"] + "/selection-documents"
    result = call(client, "get", path, admin)
    assert result["registration"]["data"]["desired_position"] == "Operador"
    assert result["accessibility"]["accessibility_needs"] == "Local acessível"
    assert result["receipts"][0]["id"] == receipt["id"]
    consent_download = call(client, "get", f"/candidates/{profile['id']}/consent-download", admin)
    assert consent_download == {"available": True, "receipt_id": receipt["id"], "protocol": receipt["protocol"]}
    assert call(client, "get", f"/candidates/{profile['id']}/selection-registration-download", admin)["available"] is False
    assert client.get(f"/api/v1/candidates/{profile['id']}/consent-download", headers=owner).status_code == 403
    manager = actors["manager"]["headers"]
    limited = call(client, "get", path, manager)
    assert limited["registration"] == {"restricted": True}
    assert limited["accessibility"] == {}
    assert client.get("/api/v1" + path, headers=owner).status_code == 403
    assert client.get("/api/v1" + path, headers=actors["outsider"]["headers"]).status_code in {403, 404}
    receipt_path = "/api/v1/privacy/consent-receipts/" + receipt["id"] + "/document"
    assert client.get(receipt_path, headers=manager).status_code == 200
    assert client.get(receipt_path, headers=actors["outsider"]["headers"]).status_code in {403, 404}
