from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from test_integration import call

from app.core.db import utcnow
from app.models import Approval, Vacancy


def test_rh_can_publish_when_saving_without_separate_approval(client, db, actors):
    admin = actors["admin"]["headers"]
    call(
        client,
        "post",
        "/configuration/privacy-notices",
        admin,
        {
            "name": "Aviso publicação direta " + uuid4().hex[:8],
            "reason": "Termo ativo para publicação da vaga de teste",
            "data": {
                "text": "Aviso de privacidade para o processo seletivo e tratamento dos dados da candidatura.",
                "purpose": "Recrutamento e seleção",
                "contact": "rh@example.com",
                "talent_months": 12,
            },
        },
        201,
    )
    payload = {
        "title": "Vaga publicada ao salvar " + uuid4().hex[:6],
        "org_unit_id": actors["org"],
        "recruiter_id": actors["admin"]["id"],
        "manager_id": actors["manager"]["id"],
        "quantity": 1,
        "description": "Atendimento aos usuários e acompanhamento dos chamados internos da equipe.",
        "city": "Barcarena",
        "state": "PA",
        "deadline": (utcnow() + timedelta(days=30)).isoformat(),
        "details": {"requirements": "Conhecimentos básicos de atendimento e suporte técnico."},
        "publish_on_save": True,
    }
    created = call(client, "post", "/vacancies", admin, payload, 201)
    assert created["status"] == "PUBLISHED"
    assert call(client, "get", "/public/vacancies/" + created["slug"], {})["title"] == payload["title"]
    detail = call(client, "get", "/vacancies/" + created["id"], admin)
    assert detail["stages"] and detail["scoring_models"]
    assert all(item["ok"] for item in detail["checklist"])
    assert detail["scoring_models"][0]["criteria"][0]["not_applicable"] is True
    assert not db.scalar(select(Approval.id).where(Approval.vacancy_id == created["id"]))

    cloned = call(client, "post", "/vacancies/" + created["id"] + "/clone", admin, {}, 201)
    assert cloned["id"] != created["id"]
    assert cloned["status"] == "DRAFT"
    assert cloned["title"] == created["title"] + " (cópia)"
    cloned_detail = call(client, "get", "/vacancies/" + cloned["id"], admin)
    assert len(cloned_detail["stages"]) == len(detail["stages"])
    assert cloned_detail["scoring_models"][0]["criteria"] == detail["scoring_models"][0]["criteria"]

    draft = call(client, "post", "/vacancies", admin, payload | {
        "title": "Rascunho para publicação direta " + uuid4().hex[:6],
        "publish_on_save": False,
    }, 201)
    assert draft["status"] == "DRAFT"
    published = call(
        client,
        "post",
        "/vacancies/" + draft["id"] + "/status",
        admin,
        {"version": draft["version"], "status": "PUBLISHED"},
    )
    assert published["status"] == "PUBLISHED"


def test_incomplete_vacancy_is_not_published(client, db, actors):
    admin = actors["admin"]["headers"]
    title = "Vaga incompleta " + uuid4().hex[:8]
    response = client.post(
        "/api/v1/vacancies",
        headers=admin,
        json={
            "title": title,
            "org_unit_id": actors["org"],
            "recruiter_id": actors["admin"]["id"],
            "manager_id": actors["manager"]["id"],
            "quantity": 1,
            "publish_on_save": True,
        },
    )
    assert response.status_code == 422
    assert "Pendências para publicar" in response.text
    assert not db.scalar(select(Vacancy.id).where(Vacancy.title == title))
