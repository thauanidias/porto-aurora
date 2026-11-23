from sqlalchemy import select
from test_candidate_journey import register_basic_candidate
from test_integration import call, setup_vacancy

from app.models import Application, Notification
from app.services.admission_documents import ADMISSION_CATALOG


def test_checklist_is_visible_without_candidate_profile(client, actors):
    result = call(client, "get", "/documents/admission-checklist", actors["admin"]["headers"])
    assert len(result["items"]) == 24
    assert result["can_upload"] is False
    assert result["internal_account"] is True
    assert all(item["document"] is None for item in result["items"])


def test_rh_uploads_before_release_without_unlocking_candidate(client, actors):
    owner, candidate, _ = register_basic_candidate(client)
    other, _, _ = register_basic_candidate(client)
    rh = actors["admin"]["headers"]
    payload = {"type_name": "ADM_RG", "candidate_id": candidate["id"]}
    pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
    files = {"file": ("rg-rh.pdf", pdf, "application/pdf")}
    assert client.post("/api/v1/documents", headers=other, data=payload, files=files).status_code == 403
    assert client.post("/api/v1/documents", headers=actors["manager"]["headers"], data=payload, files=files).status_code == 403
    result = client.post("/api/v1/documents", headers=rh, data=payload, files=files)
    assert result.status_code == 201, result.text
    document = result.json()
    assert document["candidate_id"] == candidate["id"]
    assert document["uploaded_by"] == actors["admin"]["id"]
    checklist = call(client, "get", "/documents/admission-checklist?candidate_id=" + candidate["id"], rh)
    assert checklist["can_upload"] is True and checklist["approved"] is False
    assert call(client, "get", "/documents/admission-checklist", owner)["can_upload"] is False
    assert client.post("/api/v1/documents", headers=owner, data={"type_name": "ADM_CPF"}, files=files).status_code == 403
    assert client.get("/api/v1/documents/" + document["id"] + "/download", headers=rh).content == pdf
    assert client.get("/api/v1/documents/" + document["id"] + "/download", headers=other).status_code == 403


def test_admission_checklist_upload_is_immutable_and_private(client, actors, db):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_basic_candidate(client)
    other, _, _ = register_basic_candidate(client)
    pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
    initial = call(client, "get", "/documents/admission-checklist", owner)
    assert len(initial["items"]) == 24
    assert initial["can_upload"] is False
    assert initial["internal_account"] is False
    assert client.post("/api/v1/documents", headers=owner, data={"type_name": "ADM_RG"}, files={"file": ("rg.pdf", pdf, "application/pdf")}).status_code == 403
    assert client.post("/api/v1/candidates/" + candidate["id"] + "/approve-document-uploads", headers=owner).status_code == 403
    application = call(client, "post", "/applications", owner, {
        "vacancy_id": vacancy["id"], "enrollment": True,
    }, 201)
    assert call(client, "get", "/documents/admission-checklist", owner)["eligible"] is False
    assert call(client, "get", "/documents/admission-checklist?candidate_id=" + candidate["id"], actors["admin"]["headers"])["can_approve"] is False
    call(client, "post", "/candidates/" + candidate["id"] + "/approve-document-uploads", actors["admin"]["headers"], {}, 409)
    # Set up the post-test stage; movement and automatic release are tested in process_workflow.
    from app.models import PipelineStage
    stages = db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy["id"])).all()
    final = next(stage for stage in stages if stage.kind in {"FINALIST", "OFFER", "HIRED"})
    db.get(Application, application["id"]).stage_id = final.id
    db.commit()
    call(client, "post", "/candidates/" + candidate["id"] + "/approve-document-uploads", actors["admin"]["headers"])
    notifications = db.scalars(select(Notification).where(Notification.user_id == candidate["user_id"], Notification.category == "DOCUMENT")).all()
    assert len(notifications) == 1
    assert notifications[0].link == "/candidato/documentos"
    call(client, "post", "/candidates/" + candidate["id"] + "/approve-document-uploads", actors["admin"]["headers"])
    assert len(db.scalars(select(Notification).where(Notification.user_id == candidate["user_id"], Notification.category == "DOCUMENT")).all()) == 1
    assert call(client, "get", "/documents/admission-checklist", owner)["can_upload"] is True
    assert call(client, "get", "/candidates/me/journey", owner)["sections"]["admission"]["enabled"] is True
    assert db.get(Application, application["id"]).status == "ACTIVE"
    assert sum(item["group"] == "Dependentes" for item in initial["items"]) == 7
    assert all(item["document"] is None for item in initial["items"])
    for item in ADMISSION_CATALOG:
        response = client.post("/api/v1/documents", headers=owner,
            data={"type_name": item["type_name"]},
            files={"file": ("documento.pdf", pdf, "application/pdf")})
        assert response.status_code == 201, response.text
        document = response.json()
        duplicate = client.post("/api/v1/documents", headers=owner,
            data={"type_name": item["type_name"]},
            files={"file": ("substituto.pdf", pdf, "application/pdf")})
        assert duplicate.status_code == 409
        path = "/api/v1/documents/" + document["id"] + "/download"
        assert client.get(path, headers=owner).content == pdf
        assert client.get(path, headers=other).status_code == 403
    after = call(client, "get", "/documents/admission-checklist", owner)
    rh = call(client, "get", "/documents/admission-checklist?candidate_id=" + candidate["id"], actors["admin"]["headers"])
    assert rh["can_upload"] is True
    assert [item["document"]["id"] for item in rh["items"]] == [item["document"]["id"] for item in after["items"]]
    assert client.get("/api/v1/documents/admission-checklist?candidate_id=" + candidate["id"], headers=other).status_code == 403
    assert all(item["document"]["revision"] == 1 for item in after["items"])
    assert all(item["document"] is None for item in call(client, "get", "/documents/admission-checklist", other)["items"])
    assert client.get("/api/v1/documents/admission-checklist").status_code == 401
    assert client.post("/api/v1/documents", headers=owner,
        data={"type_name": "ADM_INVALID"}, files={"file": ("documento.pdf", pdf, "application/pdf")}).status_code == 422
    db.get(Application, application["id"]).status = "REJECTED"
    db.commit()
    blocked = call(client, "get", "/documents/admission-checklist", owner)
    assert blocked["approved"] is False and blocked["can_upload"] is False
    assert client.post("/api/v1/documents", headers=owner,
        data={"type_name": "ADM_RG"}, files={"file": ("rg.pdf", pdf, "application/pdf")}).status_code == 403
