from sqlalchemy import select
from test_candidate_journey import register_basic_candidate
from test_integration import call

from app.models import AuditLog, Notification


def test_document_review_notifies_only_owner_and_records_audit(client, actors, db):
    owner, candidate, _ = register_basic_candidate(client)
    _, other, _ = register_basic_candidate(client)
    rh = actors["admin"]["headers"]
    response = client.post(
        "/api/v1/documents", headers=rh,
        data={"type_name": "ADM_RG", "candidate_id": candidate["id"]},
        files={"file": ("rg.pdf", b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n", "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    path = "/documents/" + document["id"] + "/review"
    body = {"version": document["version"], "status": "REJECTED", "comment": "Envie uma cópia legível."}
    assert client.put("/api/v1" + path, headers=owner, json=body).status_code == 403
    assert client.put("/api/v1" + path, headers=rh, json={**body, "comment": ""}).status_code == 422
    reviewed = call(client, "put", path, rh, body)
    notifications = db.scalars(select(Notification).where(
        Notification.user_id == candidate["user_id"], Notification.category == "DOCUMENT",
    )).all()
    assert len(notifications) == 1
    assert notifications[0].link == "/candidato/documentos"
    assert "correção" in notifications[0].title.lower()
    assert "cópia legível" not in notifications[0].body
    assert not db.scalar(select(Notification.id).where(Notification.user_id == other["user_id"]))
    assert db.scalar(select(AuditLog.id).where(
        AuditLog.entity_id == document["id"], AuditLog.action == "document.reviewed",
    ))
    assert client.put("/api/v1" + path, headers=rh, json=body).status_code == 409
    call(client, "put", path, rh, {"version": reviewed["version"], "status": "APPROVED"})
    assert len(db.scalars(select(Notification).where(
        Notification.user_id == candidate["user_id"], Notification.category == "DOCUMENT",
    )).all()) == 2


def test_rejected_admission_document_can_be_corrected_with_history(client, actors, db):
    owner, candidate, _ = register_basic_candidate(client)
    rh = actors["admin"]["headers"]
    from test_integration import setup_vacancy
    from readiness_helpers import ready_candidate
    from app.models import Application
    job, _, _, _ = setup_vacancy(client, actors)
    ready_candidate(client, owner)
    application = call(client, "post", "/applications", owner, {"vacancy_id": job["id"], "enrollment": True}, 201)
    # This document-correction scenario starts after the selection has completed.
    db.get(Application, application["id"]).status = "SELECTED"
    db.commit()
    call(client, "post", "/candidates/" + candidate["id"] + "/approve-document-uploads", rh)
    payload = {"type_name": "ADM_RG", "candidate_id": candidate["id"]}
    files = {"file": ("rg.pdf", b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n", "application/pdf")}
    first = client.post("/api/v1/documents", headers=rh, data=payload, files=files).json()
    assert client.post("/api/v1/documents", headers=rh, data=payload, files=files).status_code == 409
    call(client, "put", "/documents/" + first["id"] + "/review", rh, {
        "version": first["version"], "status": "REJECTED", "comment": "Envie todas as páginas.",
    })
    corrected = client.post("/api/v1/documents", headers=owner, data={"type_name": "ADM_RG"}, files=files)
    assert corrected.status_code == 201, corrected.text
    second = corrected.json()
    assert second["revision"] == 2 and second["status"] == "PENDING"
    checklist = call(client, "get", "/documents/admission-checklist?candidate_id=" + candidate["id"], rh)
    assert next(item for item in checklist["items"] if item["type_name"] == "ADM_RG")["document"]["id"] == second["id"]
    assert client.get("/api/v1/documents/" + first["id"] + "/download", headers=owner).status_code == 200
    assert client.post("/api/v1/documents", headers=rh, data=payload, files=files).status_code == 409
