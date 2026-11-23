from sqlalchemy import select
from test_candidate_journey import advance, enroll, journey_owner  # noqa: F401
from test_integration import call

from app.models import Application, Document, PipelineStage, Vacancy


def test_document_profiles_appear_after_tests_and_download_all_uploaded_types(client, db, actors, journey_owner):  # noqa: F811
    owner, job, admin, _ = journey_owner
    application = enroll(client, owner, job)
    candidate = call(client, "get", "/candidates/me", owner)
    assert call(client, "get", "/document-candidates", admin)["items"] == []
    pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
    baseline = call(client, "get", "/documents?include_photo=true&candidate_id=" + candidate["id"], admin)["items"]
    documents = []
    for kind, name in [("CURRICULO", "curriculo.pdf"), ("ADM_RG", "rg.pdf")]:
        response = client.post("/api/v1/documents", headers=admin, data={"type_name": kind, "candidate_id": candidate["id"]}, files={"file": (name, pdf, "application/pdf")})
        assert response.status_code == 201, response.text
        documents.append(response.json())
    advance(client, admin, application, job, "TEST")
    result = call(client, "get", "/document-candidates", admin)
    assert result["total"] == 1
    assert result["items"][0]["id"] == candidate["id"]
    assert result["items"][0]["document_count"] == 3
    assert result["items"][0]["processes"][0]["stage_name"]
    files = call(client, "get", "/documents?include_photo=true&candidate_id=" + candidate["id"], admin)
    assert {row["id"] for row in files["items"]} == {row["id"] for row in documents + baseline}
    for document in documents:
        response = client.get("/api/v1/documents/" + document["id"] + "/download", headers=admin)
        assert response.status_code == 200 and response.content == pdf
        assert "storage_key" not in next(row for row in files["items"] if row["id"] == document["id"])
    assert call(client, "get", "/document-candidates", actors["outsider"]["headers"])["total"] == 0
    call(client, "get", "/document-candidates", owner, expected=403)
    call(client, "get", "/document-candidates", {}, expected=401)
    call(client, "get", "/documents/" + documents[0]["id"] + "/download", actors["outsider"]["headers"], expected=404)
    file = db.get(Document, documents[0]["id"])
    file.scan_status = "PENDING"
    db.commit()
    call(client, "get", "/documents/" + file.id + "/download", admin, expected=409)
    # A candidate who previously reached tests keeps the document profile.
    db.get(Application, application["id"]).stage_id = job["stages"][0]["id"]
    db.commit()
    assert call(client, "get", "/document-candidates", admin)["total"] == 1
    db.get(Vacancy, job["id"]).blind = True
    for stage in db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == job["id"])):
        stage.reveal_identity = False
    db.commit()
    hidden = call(client, "get", "/document-candidates", admin)["items"][0]
    assert hidden["blind"] and hidden["name"].startswith("Candidato #") and hidden["document_count"] == 0
    assert call(client, "get", "/document-candidates?q=Pessoa", admin)["items"] == []
