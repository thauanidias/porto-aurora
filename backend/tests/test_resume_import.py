import io
import json
from contextlib import contextmanager
from unittest.mock import Mock

import pytest
from reportlab.pdfgen import canvas
from sqlalchemy import select
from test_candidate_journey import register_basic_candidate
from test_integration import call

from app.core.config import settings
from app.core.errors import DomainError
from app.core.security import decrypt
from app.models import Candidate, SensitiveData
from app.schemas.candidates import Education, Experience, Language, Profile, professional_facts
from app.services.resume_ai import (
    Extraction,
    Fact,
    extract_local,
    fast_labeled_suggestions,
    labeled_professional,
    validated_suggestions,
)
from app.services.resume_jobs import run_import
from app.services.resume_profile import read_resume


def test_fast_reading_requires_all_content_to_be_understood_and_preserves_partial_dates():
    text = """Nome: Pessoa Ficticia
Telefone: (91) 98888-7766
Cidade: Barcarena - PA
Endereço: Rua Ficticia, 123
Bairro: Centro
FORMAÇÃO ACADÊMICA
Escolaridade: Técnico concluído
Curso: Logística
Instituição: Escola Ficticia
Período: 2018 - 2022
EXPERIÊNCIA PROFISSIONAL
Empresa: Empresa Ficticia
Cargo: Assistente
Período: 03/2021 a 10/2023
Atividades: Conferência de cargas
Habilidades: Excel; Organização
Idiomas: Inglês intermediário"""
    result = fast_labeled_suggestions(text)
    assert result is not None
    data = result["suggestions"]
    assert data["profile"]["experiences"][0]["period_text"] == "03/2021 a 10/2023"
    assert "start" not in data["profile"]["experiences"][0]
    assert data["personal"]["address"]["street"] == "Rua Ficticia"
    assert data["personal"]["address"]["number"] == "123"
    assert fast_labeled_suggestions(text + "\nOutra empresa de 2010 a 2015: vendas e atendimento") is None
    assert fast_labeled_suggestions(text.replace("Habilidades:", "Certificado adicional de piloto\nHabilidades:")) is None


def test_fast_reading_does_not_skip_unrecognized_continuations_in_experience():
    text = """FORMAÇÃO ACADÊMICA
Escolaridade: Técnico concluído
Curso: Logística
Instituição: Escola Ficticia
EXPERIÊNCIA PROFISSIONAL
Empresa: Empresa Ficticia
Cargo: Assistente
Período: 2021 - 2023
Atividades: Conferência de cargas
Outro empregador em 2018: auxiliar de vendas"""
    assert fast_labeled_suggestions(text) is None


def curriculum_pdf():
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(40, 800, "Nome: Pessoa Ficticia de Importacao")
    pdf.drawString(40, 770, "CPF: 529.982.247-25")
    pdf.drawString(40, 740, "Nascimento: 31/12/1990")
    pdf.showPage()
    pdf.drawString(40, 800, "Habilidades: Excel; Logistica; Organizacao")
    pdf.drawString(40, 770, "Formacao: Ensino medio concluido")
    pdf.save()
    return output.getvalue()


def test_partial_periods_and_language_levels_do_not_invent_dates_or_ratings():
    text = "Empresa Alfa\nAnalista\n2021 - 2023\nIngles intermediario"
    facts = [Fact(path=path, value=value, evidence=evidence) for path, value, evidence in [
        ("profile.experiences.0.company", "Empresa Alfa", "Empresa Alfa"),
        ("profile.experiences.0.position", "Analista", "Analista"),
        ("profile.experiences.0.period_text", "2021 - 2023", "2021 - 2023"),
        ("profile.experiences.0.start", "2021-01-01", "2021 - 2023"),
        ("profile.languages.0.language", "Ingles", "Ingles intermediario"),
        ("profile.languages.0.level_text", "intermediario", "Ingles intermediario"),
    ]]
    result = validated_suggestions(Extraction(facts=facts), text)["suggestions"]["profile"]
    assert "start" not in result["experiences"][0]
    profile = Profile(experiences=[Experience(**result["experiences"][0])], languages=[Language(**result["languages"][0])])
    assert profile.experiences[0].period_text == "2021 - 2023"
    assert profile.languages[0].reading is None
    assert professional_facts(profile)["experience_years"] is None
    assert professional_facts(profile)["languages"] is None
    assert professional_facts(Profile(education=[Education(course="Administração")]))["education_level"] is None


def test_personal_data_require_literal_valid_evidence():
    text = "CPF: 529.982.247-25\nNascimento: 31/12/1990\nE-mail: teste@example.com"
    result = validated_suggestions(Extraction(facts=[]), text)["suggestions"]
    assert result["personal"]["cpf"] == "52998224725"
    assert result["personal"]["birth_date"] == "1990-12-31"
    assert result["personal"]["email"] == "teste@example.com"
    invalid = validated_suggestions(Extraction(facts=[]), "CPF: 111.111.111-11\nNascimento: 99/99/9999")
    assert not invalid["suggestions"].get("personal")
    assert invalid["uncertain"]


def test_table_rows_courses_certifications_and_language_labels_are_mapped():
    text = "EXPERIÊNCIA PROFISSIONAL\nEmpresa              Empresa Fictícia de Importação\nCargo                Assistente de Logística\nPeríodo              03/2021 a 10/2023\nAtividades           Conferência de cargas.\nCURSOS COMPLEMENTARES\nCurso: Segurança\nInstituição: Escola\nCarga horária: 40 horas\nConclusão: 2023\nIdiomas: Inglês intermediário\nCERTIFICAÇÕES\nNome: Operação Segura\nEmissor: Instituto Fictício\nEmissão: 2024"
    data = validated_suggestions(Extraction(facts=labeled_professional(text)), text)["suggestions"]["profile"]
    assert data["experiences"][0]["company"] == "Empresa Fictícia de Importação"
    assert data["experiences"][0]["period_text"] == "03/2021 a 10/2023"
    assert "start" not in data["experiences"][0]
    assert data["courses"][0]["hours"] == 40
    assert data["languages"][0]["level_text"] == "intermediário"
    assert data["certifications"][0]["issued_text"] == "2024"


def test_every_scanned_page_is_read_including_pages_after_five(monkeypatch):
    page = Mock()
    page.get_contents.return_value = None
    page.extract_text.return_value = ""
    reader = Mock(is_encrypted=False, pages=[page] * 8)
    monkeypatch.setattr("app.services.resume_profile.PdfReader", lambda *args: reader)
    ocr = Mock(side_effect=lambda content, number: f"Texto reconhecido da pagina numero {number}")
    monkeypatch.setattr("app.services.resume_profile.ocr_page", ocr)
    result = read_resume(b"pdf", "application/pdf")
    assert result["pages"] == 8
    assert result["ocr_pages"] == list(range(1, 9))
    assert "numero 8" in result["text"]
    assert ocr.call_count == 8


def test_long_documents_are_interpreted_in_chunks_without_ignoring_tail(monkeypatch):
    seen = []
    def extract(text):
        seen.append(text)
        return {"suggestions": {"profile": {"skills": ["Excel"]}}, "uncertain": [], "missing": []}
    monkeypatch.setattr("app.services.resume_ai._extract_chunk", extract)
    text = ("Linha profissional de exemplo.\n" * 1400) + "ULTIMA PAGINA"
    result = extract_local(text)
    assert len(seen) > 1 and "ULTIMA PAGINA" in seen[-1]
    assert "".join(seen) == text
    assert result["suggestions"]["profile"]["skills"] == ["Excel"]


def test_conflicting_personal_information_across_pages_is_flagged_not_guessed(monkeypatch):
    results = iter([{"suggestions": {"personal": {"birth_date": "1990-01-01"}}, "uncertain": []},
                    {"suggestions": {"personal": {"birth_date": "1991-01-01"}}, "uncertain": []}])
    monkeypatch.setattr("app.services.resume_ai._extract_chunk", lambda text: next(results))
    result = extract_local("x" * 12001)
    assert "birth_date" not in result["suggestions"].get("personal", {})
    assert any("informações diferentes" in message for message in result["uncertain"])


def test_async_upload_extraction_review_and_atomic_confirmation(client, db, monkeypatch):
    owner, person, email = register_basic_candidate(client)
    other, _, _ = register_basic_candidate(client)
    queued = Mock()
    monkeypatch.setattr("app.tasks.worker.resume_import.delay", queued)
    upload = client.post("/api/v1/documents", headers=owner, data={"type_name": "CURRICULO"},
                         files={"file": ("curriculo.pdf", curriculum_pdf(), "application/pdf")})
    assert upload.status_code == 201
    document = upload.json()
    path = "/documents/" + document["id"] + "/profile-import"
    assert call(client, "post", path, owner, expected=202)["status"] == "QUEUED"
    call(client, "post", path, owner, expected=202)
    queued.assert_called_once_with(person["user_id"], document["id"])
    call(client, "get", path, other, expected=404)
    call(client, "get", path, {}, expected=401)
    monkeypatch.setattr(settings(), "resume_ai_enabled", False)
    # Keep job identity stable for this rules-mode integration test.
    monkeypatch.setattr("app.services.resume_jobs.key", lambda user, doc: "test-resume-import:" + user + ":" + doc)
    @contextmanager
    def session():
        yield db
    monkeypatch.setattr("app.services.resume_jobs.SessionLocal", session)
    run_import(person["user_id"], document["id"])
    result = call(client, "get", path, owner)
    assert result["status"] == "COMPLETED"
    assert result["result"]["pages"] == 2
    assert result["result"]["suggestions"]["personal"]["cpf"] == "52998224725"
    assert db.get(Candidate, person["id"]).profile == {}
    body = {"candidate": {"name": person["name"], "phone": "91999999999", "city": "Belem", "state": "PA",
                           "profile": {"skills": ["Excel", "Logistica"]}, "version": person["version"]},
            "personal": {"cpf": "52998224725", "birth_date": "1990-12-31"}, "personal_version": 0, "confirmed": False}
    call(client, "post", "/candidates/me/confirm-resume-import", owner, body, expected=422)
    assert db.get(Candidate, person["id"]).profile == {}
    body["confirmed"] = True
    saved = call(client, "post", "/candidates/me/confirm-resume-import", owner, body)
    assert saved["candidate"]["profile"]["skills"] == ["Excel", "Logistica"]
    assert saved["candidate"]["email"] == email
    stored = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == person["id"]))
    assert "52998224725" not in stored.encrypted_data
    assert json.loads(decrypt(stored.encrypted_data))["resume_personal"]["data"]["cpf"] == "52998224725"
    body["candidate"].update(version=saved["candidate"]["version"], name="Nome que deve ser revertido")
    call(client, "post", "/candidates/me/confirm-resume-import", owner, body, expected=409)
    assert call(client, "get", "/candidates/me", owner)["name"] == person["name"]


def test_protected_or_excessive_pdf_returns_actionable_error(monkeypatch):
    monkeypatch.setattr("app.services.resume_profile.PdfReader", lambda *args: Mock(is_encrypted=True))
    with pytest.raises(DomainError, match="protegido"):
        read_resume(b"pdf", "application/pdf")
