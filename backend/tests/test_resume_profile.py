import io
import zipfile
from unittest.mock import Mock
from uuid import uuid4

from reportlab.pdfgen import canvas
from test_candidate_journey import enroll, register_basic_candidate
from test_integration import call, setup_vacancy

from app.core.config import settings
from app.services.resume_profile import profile_suggestions, resume_text


def resume_pdf():
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(40, 800, "Nome: Pessoa de Teste")
    pdf.drawString(40, 780, "Telefone: (91) 99999-1234")
    pdf.drawString(40, 760, "Habilidades: Excel; Python")
    pdf.drawString(40, 740, "https://example.com/portfolio")
    pdf.save()
    return output.getvalue()


def test_pdf_and_docx_reading_preserves_reference_text():
    text = resume_text(resume_pdf(), "application/pdf")
    assert profile_suggestions(text) == {
        "name": "Pessoa de Teste", "phone": "(91) 99999-1234",
        "profile": {"links": ["https://example.com/portfolio"], "skills": ["Excel", "Python"]},
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Formação profissional</w:t></w:r></w:p></w:body></w:document>')
    assert resume_text(out.getvalue(), "docx") == "Formação profissional"
    assert profile_suggestions("Texto sem dados reconhecíveis") == {}


def test_uploaded_resume_is_listed_and_suggestions_are_private(client, actors, monkeypatch):
    monkeypatch.setattr(settings(), "resume_ai_enabled", False)
    vacancy, _, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_basic_candidate(client)
    other, _, _ = register_basic_candidate(client)
    enroll(client, owner, vacancy)
    enroll(client, other, vacancy)
    original = call(client, "get", "/candidates/me", owner)
    response = client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
                           files={"file": ("curriculo.pdf", resume_pdf(), "application/pdf")})
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["id"] in {row["id"] for row in call(client, "get", "/documents", owner)["items"]}
    path = "/documents/" + document["id"] + "/profile-suggestions"
    assert call(client, "get", path, owner)["suggestions"]["profile"]["skills"] == ["Excel", "Python"]
    assert client.get("/api/v1" + path, headers=other).status_code == 404
    assert call(client, "get", "/candidates/me", owner)["profile"] == original["profile"]
    cached_results = {}
    analyzer = Mock(return_value={"suggestions": {"profile": {"skills": ["Excel"]}}, "missing": [], "uncertain": []})
    monkeypatch.setattr(settings(), "resume_ai_enabled", True)
    monkeypatch.setattr("app.services.resume_ai.extract_local", analyzer)
    monkeypatch.setattr("app.services.resume_cache.read_result", lambda user, sha: cached_results.get((user, sha)))
    monkeypatch.setattr("app.services.resume_cache.store_result", lambda user, sha, result: cached_results.__setitem__((user, sha), result))
    assert call(client, "get", path, owner)["cached"] is False
    assert call(client, "get", path, owner)["cached"] is True
    analyzer.assert_called_once()
    assert client.get("/api/v1" + path, headers=other).status_code == 404
    assert call(client, "get", "/candidates/me", owner)["profile"] == original["profile"]
    # A broken PDF is retained as a document even when extraction is unavailable.
    response = client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
                           files={"file": ("sem-texto.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")})
    assert response.status_code == 201
    assert client.get("/api/v1/documents/" + response.json()["id"] + "/profile-suggestions", headers=owner).status_code == 422
    assert call(client, "get", "/documents", owner)["total"] == 3


def test_new_candidate_uploads_resume_before_enrollment_and_must_complete_profile(client, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    registration = call(client, "post", "/auth/register", {}, {
        "name": "Pessoa recém cadastrada", "email": uuid4().hex + "@example.com",
        "notice_id": notice["id"], "consent": True,
    }, 201)
    token = registration["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    login = call(client, "post", "/auth/consume-link", {}, {
        "token": token, "password": "Ct42!?",
    })
    owner = {"Authorization": "Bearer " + login["access_token"]}
    call(client, "post", "/public/consent-receipts", owner, {"name": "Pessoa recém cadastrada",
        "email": login["user"]["email"], "context": "CADASTRO", "accepted": True, "read_to_end": True}, 201)
    assert client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
                       files={"file": ("primeiro.pdf", resume_pdf(), "application/pdf")}).status_code == 201
    enroll(client, owner, vacancy)
    response = client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
                           files={"file": ("primeiro.pdf", resume_pdf(), "application/pdf")})
    assert response.status_code == 201, response.text
    assert call(client, "get", "/documents", owner)["total"] == 2
    assert call(client, "get", "/candidates/me", owner)["name"] == "Pessoa recém cadastrada"
