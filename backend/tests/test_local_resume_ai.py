import io
import json
from unittest.mock import Mock

import httpx
import pytest
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.core.errors import DomainError
from app.services.resume_ai import (
    Extraction,
    extract_local,
    labeled_education,
    validated_suggestions,
)
from app.services.resume_profile import resume_text


def extracted(*facts):
    return Extraction.model_validate({"facts": [dict(zip(("path", "value", "evidence"), fact, strict=True)) for fact in facts]})


def test_local_facts_require_evidence_and_leave_partial_dates_empty():
    text = "Maria Silva\nCidade: Barcarena\nUF: PA\nEmpresa TGPM\nCargo Analista\n2022 - atual\nSuperior cursando: Administração\nInglês básico"
    result = validated_suggestions(extracted(
        ("name", "Maria Silva", "Maria Silva"),
        ("city", "Barcarena", "Cidade: Barcarena"),
        ("state", "PA", "UF: PA"),
        ("profile.experiences.0.company", "TGPM", "Empresa TGPM"),
        ("profile.experiences.0.position", "Analista", "Cargo Analista"),
        ("profile.experiences.0.start", "2022-01-01", "2022 - atual"),
        ("profile.experiences.0.current", "true", "2022 - atual"),
        ("profile.education.0.degree", "SUPERIOR", "Superior cursando: Administração"),
        ("profile.education.0.status", "CURSANDO", "Superior cursando: Administração"),
        ("profile.languages.0.reading", "2", "Inglês básico"),
        ("phone", "91999999999", "Telefone não presente"),
        ("profile.facts.score", "100", "Maria Silva"),
    ), text)
    assert result["suggestions"]["name"] == "Maria Silva"
    experience = result["suggestions"]["profile"]["experiences"][0]
    assert experience == {"company": "TGPM", "position": "Analista", "current": True}
    assert "phone" not in result["suggestions"]
    assert "languages" not in result["suggestions"]["profile"]
    assert result["uncertain"]


def test_local_request_has_no_tools_and_never_changes_a_profile(monkeypatch):
    monkeypatch.setattr(settings(), "resume_ai_enabled", True)
    captured = {}
    redis = Mock()
    redis.lock.return_value.acquire.return_value = True
    monkeypatch.setattr("app.services.resume_ai.Redis.from_url", lambda *args: redis)

    def post(self, url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "message": {"content": json.dumps({"facts": [{"path": "name", "value": "Maria Silva", "evidence": "Maria Silva"}]})},
        })

    monkeypatch.setattr(httpx.Client, "post", post)
    assert extract_local("Maria Silva")["suggestions"] == {"name": "Maria Silva"}
    assert "tools" not in captured
    assert captured["stream"] is False
    assert captured["format"]["additionalProperties"] is False


def test_cloud_address_and_model_failure_do_not_fabricate_data(monkeypatch):
    monkeypatch.setattr(settings(), "resume_ai_enabled", True)
    monkeypatch.setattr(settings(), "resume_ai_url", "https://external.example")
    with pytest.raises(DomainError):
        extract_local("Nome: Pessoa Teste")


def test_conflicting_facts_are_not_applied():
    result = validated_suggestions(extracted(("city", "Belém", "Belém"), ("city", "Barcarena", "Barcarena")), "Belém / Barcarena")
    assert "city" not in result["suggestions"]


def test_full_brazilian_dates_are_normalized_without_inventing_days():
    result = validated_suggestions(extracted(("profile.education.0.start", "10/02/2016", "10/02/2016")), "Início: 10/02/2016")
    assert result["suggestions"]["profile"]["education"][0]["start"] == "2016-02-10"


def test_explicit_academic_labels_use_existing_fields():
    text = "Formação: Ensino superior concluído\nCurso: Administração\nInstituição: Faculdade Exemplo\nInício: 10/02/2016\nConclusão: 15/12/2019"
    result = validated_suggestions(Extraction(facts=labeled_education(text)), text)
    assert result["suggestions"]["profile"]["education"] == [{
        "institution": "Faculdade Exemplo", "course": "Administração", "degree": "SUPERIOR",
        "status": "CONCLUIDO", "start": "2016-02-10", "end": "2019-12-15",
    }]


def test_scanned_resume_uses_local_ocr():
    image = Image.new("RGB", (1400, 400), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSans.ttf", 48)
    draw.text((40, 50), "Nome: Maria Silva", font=font, fill="black")
    draw.text((40, 140), "Telefone: (91) 99999-1234", font=font, fill="black")
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawImage(ImageReader(image), 30, 540, width=530, height=150)
    pdf.save()
    text = resume_text(output.getvalue(), "application/pdf")
    assert "Maria Silva" in text
    assert "99999" in text


def test_plain_header_location_and_bullet_sections_are_extracted_without_inventing_employment():
    text = "Franciel Ferreira Rodrigues\nTelefone: (91) 99999-1234\nCidade: Barcarena - PA\n\nFormação Acadêmica\n\x7f Ensino Médio Completo\n\x7f Cursando Engenharia da Computação\n\nExperiência\nÁrea de Computação: conhecimentos em informática e suporte básico.\n\nHabilidades\n\x7f Computação e Informática\n\x7f Pacote Microsoft Office (Word, Excel e PowerPoint)\n\x7f Trabalho em equipe"
    result = validated_suggestions(Extraction(facts=labeled_education(text)), text)
    data = result["suggestions"]
    assert data["name"] == "Franciel Ferreira Rodrigues"
    assert data["city"] == "Barcarena" and data["state"] == "PA"
    assert len(data["profile"]["skills"]) == 3
    education = data["profile"]["education"]
    assert len(education) == 2
    assert education[0]["degree"] == "MEDIO" and education[0]["status"] == "CONCLUIDO"
    assert education[1]["status"] == "CURSANDO"
    assert "Engenharia da Computação" in education[1]["course"]
    assert all("start" not in item and "institution" not in item for item in education)
    assert "experiences" not in data["profile"]
    assert "Área de Computação" in data["profile"]["notes"]
