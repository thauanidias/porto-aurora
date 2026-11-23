from sqlalchemy import select
from test_integration import call

from app.models import ConfigRecord, Notification, VacancyRequest


def setup_request_flow(client, actors):
    flow = call(client, "post", "/configuration/workflows", actors["admin"]["headers"], {
        "name": "Pedidos dos gestores", "reason": "Configuração do teste de integração",
        "data": {"target": "REQUEST", "steps": [{"name": "RH", "approver_id": actors["admin"]["id"], "sla_hours": 48}]},
    }, 201)
    payload = {
        "title": "Analista para equipe", "org_unit_id": actors["org"], "quantity": 1,
        "reason": "Nova posição", "request_type": "NEW", "justification": "Necessidade de contratação da equipe",
        "position": "Analista", "cost_center": "TEST", "desired_date": "2026-12-01",
        "request_workflow_id": flow["id"],
    }
    return flow, payload


def test_manager_request_reaches_rh_and_returns_as_linked_vacancy(client, db, actors):
    flow, payload = setup_request_flow(client, actors)
    manager, admin = actors["manager"]["headers"], actors["admin"]["headers"]
    row = call(client, "post", "/vacancy-requests/send", manager, payload, 201)
    assert row["status"] == "PENDING_APPROVAL"
    assert not row["can_decide"]
    call(client, "post", "/vacancy-requests/" + row["id"] + "/approve", manager,
         {"version": row["version"], "decision": "APPROVED", "comment": "Tentativa pelo solicitante"}, 403)
    rh_rows = call(client, "get", "/vacancy-requests", admin)["items"]
    assert next(r for r in rh_rows if r["id"] == row["id"])["can_decide"]
    assert row["id"] not in {r["id"] for r in call(client, "get", "/vacancy-requests", actors["outsider"]["headers"])["items"]}
    call(client, "get", "/vacancy-requests/" + row["id"], actors["outsider"]["headers"], expected=404)
    assert db.scalar(select(Notification.id).where(Notification.user_id == actors["admin"]["id"], Notification.link == "/app/solicitacoes"))
    row = call(client, "post", "/vacancy-requests/" + row["id"] + "/approve", admin,
               {"version": row["version"], "decision": "REJECTED", "comment": "Detalhar o motivo da contratação"})
    feedback = call(client, "get", "/vacancy-requests/" + row["id"], manager)
    assert feedback["last_decision"] == "REJECTED"
    assert feedback["rh_feedback"] == "Detalhar o motivo da contratação"
    row = call(client, "put", "/vacancy-requests/" + row["id"], manager,
               {**payload, "version": row["version"], "justification": "Ampliação da equipe para o novo turno de operação"})
    row = call(client, "post", "/vacancy-requests/" + row["id"] + "/submit", manager,
               {"version": row["version"], "workflow_id": flow["id"], "status": "PENDING_APPROVAL"})
    row = call(client, "post", "/vacancy-requests/" + row["id"] + "/approve", admin,
               {"version": row["version"], "decision": "APPROVED", "comment": "Contratação autorizada"})
    vacancy_payload = {"title": payload["title"], "org_unit_id": actors["org"], "quantity": 1,
                       "manager_id": actors["outsider"]["id"], "recruiter_id": actors["admin"]["id"]}
    call(client, "post", "/vacancy-requests/" + row["id"] + "/vacancy", admin, vacancy_payload, 422)
    vacancy = call(client, "post", "/vacancy-requests/" + row["id"] + "/vacancy", admin,
                   {**vacancy_payload, "manager_id": actors["manager"]["id"]}, 201)
    result = call(client, "get", "/vacancy-requests/" + row["id"], manager)
    assert result["status"] == "CONVERTED"
    assert result["vacancy_id"] == vacancy["id"]
    call(client, "get", "/vacancies/" + vacancy["id"], manager)
    call(client, "get", "/vacancies/" + vacancy["id"], actors["outsider"]["headers"], expected=404)
    assert db.scalar(select(Notification.id).where(Notification.user_id == actors["manager"]["id"], Notification.link == "/gestor/vagas/" + vacancy["id"]))


def test_send_selects_only_request_flow_and_missing_flow_leaves_no_draft(client, db, actors):
    for flow in db.scalars(select(ConfigRecord).where(ConfigRecord.kind == "workflows")):
        flow.active = False
    db.commit()
    _, payload = setup_request_flow(client, actors)
    payload.pop("request_workflow_id")
    row = call(client, "post", "/vacancy-requests/send", actors["manager"]["headers"], payload, 201)
    assert row["status"] == "PENDING_APPROVAL"
    for flow in db.scalars(select(ConfigRecord).where(ConfigRecord.kind == "workflows")):
        flow.active = False
    db.commit()
    payload["title"] = "Pedido sem fluxo não deve ser salvo"
    call(client, "post", "/vacancy-requests/send", actors["manager"]["headers"], payload, 422)
    assert not db.scalar(select(VacancyRequest.id).where(VacancyRequest.title == payload["title"]))
