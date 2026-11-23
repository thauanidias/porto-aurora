from sqlalchemy import select
from test_candidate_journey import register_basic_candidate
from test_integration import call, setup_vacancy
from test_internal_registration import employee

from app.core.db import utcnow
from app.models import Candidate, Document, User, Vacancy


def upload(client, admin, candidate_id, filename="curriculo.pdf"):
    content = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
    result = client.post("/api/v1/documents", headers=admin, data={"type_name": "CURRICULO", "candidate_id": candidate_id},
        files={"file": (filename, content, "application/pdf")})
    assert result.status_code == 201, result.text
    return result.json(), content


def test_external_documents_link_without_merging_accounts_or_transferring_files(client, db, actors):
    target_headers, target = employee(client, db)
    _, source, _ = register_basic_candidate(client)
    admin = actors["admin"]["headers"]
    document, content = upload(client, admin, source["id"])
    path = "/candidates/" + target["id"] + "/external-document-sources"
    body = {"source_candidate_id": source["id"], "identity_confirmed": True, "reason": "Identidade conferida pelo RH no teste"}
    call(client, "post", path, admin, {**body, "identity_confirmed": False}, 422)
    call(client, "post", path, target_headers, body, 403)
    call(client, "post", path, actors["outsider"]["headers"], body, 403)
    link = call(client, "post", path, admin, body, 201)
    assert link["document_count"] == 1
    # Files uploaded later must not silently join the snapshot approved by RH.
    upload(client, admin, source["id"], "novo-curriculo.pdf")
    linked = call(client, "get", path, admin)["items"]
    assert len(linked) == 1 and [doc["id"] for doc in linked[0]["documents"]] == [document["id"]]
    assert "storage_key" not in linked[0]["documents"][0]
    original = db.get(Document, document["id"])
    assert original.candidate_id == source["id"]
    assert not db.scalar(select(Document.id).where(Document.candidate_id == target["id"]))
    assert db.get(User, source["user_id"]).active
    result = client.get("/api/v1/documents/" + document["id"] + "/download", headers=admin)
    assert result.content == content
    call(client, "get", path, target_headers, expected=403)
    call(client, "delete", path + "/" + link["id"], admin)
    assert call(client, "get", path, admin)["items"] == []
    assert db.get(Document, document["id"]).candidate_id == source["id"]


def test_source_identity_must_be_visible_and_target_must_be_internal(client, db, actors):
    _, target = employee(client, db)
    owner, source, _ = register_basic_candidate(client)
    admin = actors["admin"]["headers"]
    upload(client, admin, source["id"])
    vacancy, _, _, _ = setup_vacancy(client, actors)
    call(client, "post", "/applications", owner, {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    db.get(Vacancy, vacancy["id"]).blind = True
    db.commit()
    path = "/candidates/" + target["id"] + "/external-document-sources"
    body = {"source_candidate_id": source["id"], "identity_confirmed": True, "reason": "Conferência de identidade realizada pelo RH"}
    call(client, "post", path, admin, body, 403)
    db.get(Vacancy, vacancy["id"]).blind = False
    db.commit()
    call(client, "post", path, admin, body, 201)
    db.get(Candidate, source["id"]).anonymized_at = utcnow()
    db.commit()
    assert call(client, "get", path, admin)["items"] == []
