from uuid import uuid4

from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.models import Outbox, Vacancy


def test_confidential_invitation_requires_the_recipient(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    candidate, profile, _ = register_candidate(client, notice)
    outsider, _, _ = register_candidate(client, notice)
    row = db.get(Vacancy, vacancy["id"])
    row.confidential = True
    db.commit()
    admin = actors["admin"]["headers"]
    call(client, "get", "/public/vacancies/" + vacancy["slug"], {}, expected=404)
    call(
        client,
        "post",
        "/vacancies/" + vacancy["id"] + "/invite",
        admin,
        {"candidate_id": profile["id"], "reason": "Convite para seleção confidencial"},
        201,
    )
    message = db.scalar(
        select(Outbox).where(Outbox.dedup_key.like("invite:%")).order_by(Outbox.created_at.desc())
    )
    token = message.payload["body"].split("#token=", 1)[1]
    assert (
        call(client, "post", "/public/invitations/lookup", {}, {"token": token})["id"]
        == vacancy["id"]
    )
    payload = {
        "vacancy_id": vacancy["id"],
        "notice_id": notice["id"],
        "consent": True,
        "answers": {"interest": "Interesse profissional"},
        "invitation_token": token,
    }
    call(client, "post", "/applications", outsider, payload, expected=409)
    call(client, "post", "/applications", candidate, payload, 201)
    call(client, "post", "/public/invitations/lookup", {}, {"token": token}, expected=404)


def test_vacancy_template_copies_pipeline_and_score_version(client, actors):
    admin = actors["admin"]["headers"]
    template = call(
        client,
        "post",
        "/configuration/vacancy-templates",
        admin,
        {
            "name": "Template " + uuid4().hex[:8],
            "reason": "Padronização de homologação",
            "data": {
                "description": "Descrição da vaga padronizada para validação da cópia de template.",
                "details": {"requirements": "Disponibilidade profissional"},
                "stages": [{"name": "Inscrição", "position": 0, "kind": "SCREENING"}],
                "criteria": [
                    {
                        "key": "available",
                        "name": "Disponibilidade",
                        "field": "availability",
                        "kind": "BOOLEAN",
                        "weight": 100,
                        "expected": True,
                        "justification": "Disponibilidade para a posição",
                    }
                ],
            },
        },
        201,
    )
    vacancy = call(
        client,
        "post",
        "/vacancies",
        admin,
        {
            "title": "Nova vaga de template",
            "vacancy_template_id": template["id"],
            "org_unit_id": actors["org"],
            "recruiter_id": actors["admin"]["id"],
            "manager_id": actors["manager"]["id"],
            "quantity": 1,
        },
        201,
    )
    detail = call(client, "get", "/vacancies/" + vacancy["id"], admin)
    assert detail["description"] == template["data"]["description"]
    assert len(detail["stages"]) == 1 and len(detail["scoring_models"]) == 1
    assert detail["status"] == "DRAFT"
