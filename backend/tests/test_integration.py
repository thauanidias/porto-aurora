import io
import zipfile
from datetime import timedelta
from uuid import uuid4

from consent_helpers import consent_signature
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import utcnow
from app.models import (
    AuditLog,
)


def call(client, method, path, headers, data=None, expected=200):
    legacy = getattr(client, "legacy_candidates", {}).get(headers.get("Authorization"))
    if method == "post" and path == "/applications" and expected == 201 and legacy and not data.get("enrollment"):
        return staged_application(client, headers, data)
    if method == "post" and expected == 200 and legacy and path.startswith("/test-assignments/") and path.endswith("/start"):
        from app.models import TestAssignment
        assignment = client.test_db.get(TestAssignment, path.split("/")[2])
        if assignment:
            release_test_stage(client, assignment.application_id)
    if method == "post" and path == "/applications" and expected == 201:
        readiness = client.get("/api/v1/candidates/me/application-readiness", headers=headers)
        if readiness.status_code == 200 and not readiness.json()["ready"]:
            from readiness_helpers import ready_candidate
            ready_candidate(client, headers)
    response = getattr(client, method)(
        "/api/v1" + path, headers=headers, **({"json": data} if data is not None else {})
    )
    assert response.status_code == expected, (
        f"{method} {path}: {response.status_code}: {response.text}"
    )
    result = response.json()
    if method == "post" and path == "/applications" and expected == 201 and legacy:
        prepare_professional_profile(client, headers, legacy)
        result = call(client, "get", "/applications/" + result["id"], headers)
    return result


def prepare_professional_profile(client, headers, legacy):
    if legacy["prepared"]:
        return
    current = call(client, "get", "/candidates/me", headers)
    saved = call(client, "put", "/candidates/me", headers, {**legacy["data"], "version": current["version"]})
    legacy["profile"].clear()
    legacy["profile"].update(saved)
    legacy["prepared"] = True


def release_test_stage(client, application_id):
    admin = client.legacy_admin_headers
    application = call(client, "get", "/applications/" + application_id, admin)
    vacancy = call(client, "get", "/vacancies/" + application["vacancy_id"], admin)
    stage = next(stage for stage in vacancy["stages"] if stage["kind"] == "TEST")
    if application["stage_id"] != stage["id"]:
        application = call(client, "post", "/applications/" + application_id + "/move", admin,
            {"stage_id": stage["id"], "version": application["version"], "reason": "Liberação explícita pelo RH no teste"})
    return application


def staged_application(client, headers, data):
    # Older feature tests now prepare their fixtures through the real RH stage APIs.
    from readiness_helpers import ready_candidate
    prepare_professional_profile(client, headers, client.legacy_candidates[headers["Authorization"]])
    ready_candidate(client, headers)
    application = call(client, "post", "/applications", headers,
        {"vacancy_id": data["vacancy_id"], "enrollment": True,
         **({"invitation_token": data["invitation_token"]} if data.get("invitation_token") else {})}, 201)
    initial_stage = application["stage_id"]
    application = release_test_stage(client, application["id"])
    identity = call(client, "get", "/auth/me", headers)["user"]
    call(client, "post", "/public/consent-receipts", headers,
        {"name": identity["name"], "email": identity["email"], "context": "CANDIDATURA", "accepted": True, "signature_image": consent_signature()}, 201)
    application = call(client, "put", "/applications/" + application["id"] + "/selection", headers,
        {"version": application["version"], "consent": True, "answers": data.get("answers", {})})
    application = call(client, "post", "/applications/" + application["id"] + "/move", client.legacy_admin_headers,
        {"version": application["version"], "stage_id": initial_stage, "reason": "Preparação do cenário inicial do teste"})
    return application


def setup_vacancy(client, actors):
    admin = actors["admin"]["headers"]
    client.legacy_admin_headers = admin
    notice = call(
        client,
        "post",
        "/configuration/privacy-notices",
        admin,
        {
            "name": "Aviso " + uuid4().hex[:6],
            "reason": "Configuração de teste",
            "data": {
                "text": "Tratamento dos dados exclusivamente para o processo seletivo deste teste.",
                "purpose": "Recrutamento",
                "contact": "privacy@example.com",
                "talent_months": 12,
            },
        },
        201,
    )
    workflow = call(
        client,
        "post",
        "/configuration/workflows",
        admin,
        {
            "name": "Fluxo " + uuid4().hex[:6],
            "reason": "Configuração de teste",
            "data": {
                "target": "REQUEST",
                "steps": [
                    {"name": "Aprovação RH", "approver_id": actors["admin"]["id"], "sla_hours": 24}
                ],
            },
        },
        201,
    )
    request = call(
        client,
        "post",
        "/vacancy-requests",
        actors["manager"]["headers"],
        {
            "title": "Analista de teste",
            "org_unit_id": actors["org"],
            "quantity": 1,
            "reason": "Nova posição",
            "request_type": "NEW",
            "justification": "Necessidade operacional para o teste",
            "position": "Analista",
            "cost_center": "TEST",
            "desired_date": "2026-12-01",
        },
        201,
    )
    request = call(
        client,
        "post",
        "/vacancy-requests/" + request["id"] + "/submit",
        actors["manager"]["headers"],
        {
            "version": request["version"],
            "status": "PENDING_APPROVAL",
            "workflow_id": workflow["id"],
        },
    )
    request = call(
        client,
        "post",
        "/vacancy-requests/" + request["id"] + "/approve",
        admin,
        {"version": request["version"], "decision": "APPROVED"},
    )
    vacancy = call(
        client,
        "post",
        "/vacancy-requests/" + request["id"] + "/vacancy",
        admin,
        {
            "title": "Analista de teste",
            "org_unit_id": actors["org"],
            "recruiter_id": actors["admin"]["id"],
            "manager_id": actors["manager"]["id"],
            "quantity": 1,
            "description": "Descrição funcional da oportunidade para validar o processo seletivo completo.",
            "city": "Belém",
            "state": "PA",
            "deadline": (utcnow() + timedelta(days=30)).isoformat(),
            "details": {
                "requirements": "Experiência profissional",
                "notice_id": notice["id"],
                "questions": [
                    {
                        "key": "interest",
                        "label": "Por que deseja participar?",
                        "kind": "TEXT",
                        "required": True,
                    }
                ],
            },
        },
        201,
    )
    call(
        client,
        "put",
        "/vacancies/" + vacancy["id"] + "/pipeline",
        admin,
        {
            "version": vacancy["version"],
            "stages": [
                {"name": "Inscritos", "position": 0, "kind": "SCREENING"},
                {"name": "Teste", "position": 1, "kind": "TEST"},
                {"name": "Entrevista", "position": 2, "kind": "INTERVIEW", "reveal_identity": True},
                {"name": "Finalistas", "position": 3, "kind": "FINALIST", "reveal_identity": True},
            ],
        },
    )
    model = call(
        client,
        "post",
        "/vacancies/" + vacancy["id"] + "/scoring-models",
        admin,
        {
            "criteria": [
                {
                    "key": "experience",
                    "name": "Experiência",
                    "field": "experience_years",
                    "kind": "NUMBER_MIN",
                    "weight": 100,
                    "expected": 4,
                    "justification": "Experiência relevante para a função",
                }
            ],
            "reason": "Modelo inicial aprovado",
        },
        201,
    )
    vacancy = call(client, "get", "/vacancies/" + vacancy["id"], admin)
    vacancy = call(
        client,
        "post",
        "/vacancies/" + vacancy["id"] + "/status",
        admin,
        {"version": vacancy["version"], "status": "PUBLISHED"},
    )
    return vacancy, notice, workflow, model


def register_candidate(client, notice):
    email = "candidate-" + uuid4().hex[:10] + "@example.com"
    receipt = client.post("/api/v1/public/consent-receipts", json={
        "name": "Pessoa Candidata de Teste", "email": email, "context": "CADASTRO", "accepted": True, "read_to_end": True,
    })
    assert receipt.status_code == 201, receipt.text
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Pessoa Candidata de Teste",
            "email": email,
            "notice_id": notice["id"],
            "receipt_id": receipt.json()["id"],
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    response = client.post(
        "/api/v1/auth/consume-link",
        json={"token": token, "password": "Ct42!?"},
    )
    assert response.status_code == 200, response.text
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    profile_data = {
        "name": "Pessoa Candidata de Teste", "city": "Belém", "state": "PA", "phone": "+5591999999999",
        "profile": {"experiences": [{"company": "Empresa de teste", "position": "Analista",
            "start": "2020-01-01", "end": "2022-01-01", "current": False}]},
    }
    profile = call(
        client,
        "put",
        "/candidates/me",
        headers,
        {
            "name": "Pessoa Candidata de Teste",
            "city": "Belém",
            "state": "PA",
            "phone": "+5591999999999",
            "profile": {},
        },
    )
    if not hasattr(client, "legacy_candidates"):
        client.legacy_candidates = {}
    client.legacy_candidates[headers["Authorization"]] = {"data": profile_data, "profile": profile, "prepared": False}
    return headers, profile, email


def test_certification_pdf_is_linked_to_its_owner(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    headers, profile, _ = register_candidate(client, notice)
    other_headers, other_profile, _ = register_candidate(client, notice)
    for owner in [headers, other_headers]:
        call(client, "post", "/applications", owner, {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    pdf = b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n"
    response = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"type_name": "CERTIFICADO"},
        files={"file": ("certificado.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["mime"] == "application/pdf"
    certification = {
        "name": "Certificação de teste",
        "issuer": "Instituição de teste",
        "issued": "2025-01-01",
        "document_id": document["id"],
    }
    payload = {
        "name": profile["name"],
        "version": profile["version"],
        "profile": {"certifications": [certification]},
    }
    saved = call(client, "put", "/candidates/me", headers, payload)
    assert saved["profile"]["certifications"][0]["document_id"] == document["id"]
    downloaded = client.get(f"/api/v1/documents/{document['id']}/download", headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.content == pdf
    payload["name"] = other_profile["name"]
    payload["version"] = other_profile["version"]
    denied = client.put("/api/v1/candidates/me", headers=other_headers, json=payload)
    assert denied.status_code == 422
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    docx = client.post(
        "/api/v1/documents",
        headers=headers,
        data={"type_name": "CERTIFICADO"},
        files={
            "file": (
                "certificado.docx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert docx.status_code == 422

    email = "new-candidate-" + uuid4().hex[:10] + "@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Pessoa Nova de Teste",
            "email": email,
            "notice_id": notice["id"],
            "consent": True,
        },
    )
    assert registered.status_code == 201, registered.text
    token = registered.json()["test_setup_url"].split("#token=", 1)[1].split("&", 1)[0]
    registered = client.post(
        "/api/v1/auth/consume-link",
        json={"token": token, "password": "Ct42!?"},
    )
    assert registered.status_code == 200
    new_headers = {"Authorization": "Bearer " + registered.json()["access_token"]}
    assert call(client, "get", "/candidates/me", new_headers)["profile"] == {}
    call(client, "post", "/applications", new_headers, {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    first_upload = client.post(
        "/api/v1/documents",
        headers=new_headers,
        data={"type_name": "CERTIFICADO"},
        files={"file": ("primeiro-certificado.pdf", pdf, "application/pdf")},
    )
    assert first_upload.status_code == 201, first_upload.text
    assert call(client, "get", "/candidates/me", new_headers)["email"] == email
    first_profile = call(
        client,
        "put",
        "/candidates/me",
        new_headers,
        {
            "name": "Pessoa Nova de Teste",
            "profile": {
                "certifications": [{**certification, "document_id": first_upload.json()["id"]}]
            },
        },
    )
    assert first_profile["profile"]["certifications"][0]["document_id"] == first_upload.json()["id"]


def test_complete_recruitment_flow(client, db, actors):
    admin = actors["admin"]["headers"]
    vacancy, notice, workflow, model = setup_vacancy(client, actors)
    public = client.get("/api/v1/public/vacancies/" + vacancy["slug"])
    assert public.status_code == 200
    assert "salary" not in public.json()["details"]
    candidate, profile, email = register_candidate(client, notice)
    application = call(
        client,
        "post",
        "/applications",
        candidate,
        {
            "vacancy_id": vacancy["id"],
            "notice_id": notice["id"],
            "consent": True,
            "answers": {"interest": "Atuar na área de tecnologia"},
        },
        201,
    )
    call(
        client,
        "post",
        "/applications",
        candidate,
        {
            "vacancy_id": vacancy["id"],
            "notice_id": notice["id"],
            "consent": True,
            "answers": {"interest": "Outra tentativa"},
        },
        409,
    )
    detail = call(client, "get", "/applications/" + application["id"], admin)
    assert detail["scores"][0]["total"] == 50
    assert detail["scores"][0]["breakdown"]["items"][0]["contribution"] == 50
    assert "scores" not in call(client, "get", "/applications/" + application["id"], candidate)
    stages = call(client, "get", "/vacancies/" + vacancy["id"], admin)["stages"]
    call(
        client,
        "post",
        "/applications/" + application["id"] + "/move",
        admin,
        {"version": application["version"], "stage_id": stages[1]["id"]},
    )
    assert (
        call(client, "get", "/applications/" + application["id"], admin)["stage_id"]
        == stages[1]["id"]
    )
    call(
        client,
        "post",
        "/applications/" + application["id"] + "/move",
        admin,
        {"version": application["version"], "stage_id": stages[2]["id"]},
        409,
    )
    test = call(
        client,
        "post",
        "/tests",
        admin,
        {
            "name": "Conhecimento objetivo",
            "duration_minutes": 30,
            "questions": [
                {"key": "q1", "text": "Quanto é dois mais dois?", "kind": "NUMBER", "correct": 4}
            ],
        },
        201,
    )
    assignment = call(
        client,
        "post",
        "/tests/" + test["id"] + "/assign",
        admin,
        {
            "application_id": application["id"],
            "opens_at": (utcnow() - timedelta(minutes=1)).isoformat(),
            "due_at": (utcnow() + timedelta(days=1)).isoformat(),
        },
        201,
    )
    attempt = call(client, "post", "/test-assignments/" + assignment["id"] + "/start", candidate)
    assert "correct" not in attempt["questions"][0]
    graded = call(
        client,
        "post",
        "/test-attempts/" + attempt["id"] + "/submit",
        candidate,
        {"version": attempt["version"], "answers": {"q1": 4}},
    )
    assert graded["score"] == 100
    card = call(
        client,
        "post",
        "/configuration/scorecards",
        admin,
        {
            "name": "Ficha técnica",
            "reason": "Ficha objetiva de teste",
            "data": {
                "category": "TECHNICAL",
                "independent": True,
                "criteria": [
                    {
                        "key": "technical",
                        "name": "Conhecimento técnico",
                        "min_value": 1,
                        "max_value": 5,
                        "weight": 100,
                        "extreme_comment": True,
                    }
                ],
            },
        },
        201,
    )
    evaluation = call(
        client,
        "post",
        "/evaluations",
        admin,
        {
            "application_id": application["id"],
            "evaluator_id": actors["interviewer"]["id"],
            "scorecard_id": card["id"],
        },
        201,
    )
    submitted = call(
        client,
        "post",
        "/evaluations/" + evaluation["id"] + "/submit",
        actors["interviewer"]["headers"],
        {
            "version": evaluation["version"],
            "answers": {"technical": {"value": 5, "comment": "Demonstra domínio técnico adequado"}},
            "recommendation": "ADVANCE",
        },
    )
    assert submitted["score"] == 100
    interview = call(
        client,
        "post",
        "/interviews",
        admin,
        {
            "vacancy_id": vacancy["id"],
            "title": "Entrevista técnica",
            "kind": "TECHNICAL",
            "starts_at": (utcnow() + timedelta(days=2)).isoformat(),
            "ends_at": (utcnow() + timedelta(days=2, hours=1)).isoformat(),
            "location": "Sala RH",
            "interviewers": [actors["interviewer"]["id"]],
            "application_ids": [application["id"]],
        },
        201,
    )
    ics = client.get("/api/v1/interviews/" + interview["id"] + "/calendar.ics", headers=candidate)
    assert ics.status_code == 200 and "BEGIN:VEVENT" in ics.text
    detail = call(client, "get", "/applications/" + application["id"], admin)
    call(
        client,
        "post",
        "/applications/" + application["id"] + "/decision",
        admin,
        {
            "version": detail["version"],
            "decision": "SELECTED",
            "reason": "Evidências do processo concluídas",
        },
    )
    offer = call(
        client,
        "post",
        "/offers",
        admin,
        {
            "application_id": application["id"],
            "expires_at": (utcnow() + timedelta(days=5)).isoformat(),
            "terms": {
                "position": "Analista",
                "salary": 5000,
                "benefits": "Benefícios conforme política interna",
                "workload": "40 horas semanais",
                "establishment": "Unidade de teste",
                "expected_start": "2026-12-01",
                "conditions": "Condições estabelecidas para teste",
            },
        },
        201,
    )
    workflow = call(
        client,
        "post",
        "/configuration/workflows",
        admin,
        {
            "name": "Oferta " + uuid4().hex[:6],
            "reason": "Fluxo de oferta de teste",
            "data": {
                "target": "OFFER",
                "steps": [{"name": "Aprovação", "approver_id": actors["admin"]["id"]}],
            },
        },
        201,
    )
    offer = call(
        client,
        "post",
        "/offers/" + offer["id"] + "/submit",
        admin,
        {"version": offer["version"], "status": "PENDING_APPROVAL", "workflow_id": workflow["id"]},
    )
    offer = call(
        client,
        "post",
        "/offers/" + offer["id"] + "/approve",
        admin,
        {"version": offer["version"], "decision": "APPROVED"},
    )
    offer = call(client, "post", "/offers/" + offer["id"] + "/send", admin)
    pdf = client.get("/api/v1/offers/" + offer["id"] + "/pdf", headers=candidate)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    accepted = call(
        client,
        "post",
        "/offers/" + offer["id"] + "/respond",
        candidate,
        {"version": offer["version"], "decision": "ACCEPTED"},
    )
    assert accepted["status"] == "ACCEPTED"
    assert (
        call(client, "get", "/applications/" + application["id"], admin)["status"]
        == "PRE_ADMISSION"
    )
    assert call(client, "get", "/notifications", candidate)["total"] > 0
    request = call(
        client,
        "post",
        "/privacy/requests",
        candidate,
        {"kind": "COPY", "detail": "Solicito cópia dos meus dados pessoais"},
        201,
    )
    call(
        client,
        "put",
        "/privacy/requests/" + request["id"],
        admin,
        {
            "version": request["version"],
            "status": "FULFILLED",
            "response": "Os dados foram disponibilizados pela exportação da área de privacidade.",
        },
    )
    exported = call(client, "get", "/privacy/export", candidate)
    assert exported["profile"]["email"] == email
    assert db.scalar(select(func_count(AuditLog))) > 0


def func_count(model):
    from sqlalchemy import func

    return func.count(model.id)


def test_rbac_and_independent_evaluation(client, db, actors):
    admin = actors["admin"]["headers"]
    vacancy, notice, workflow, model = setup_vacancy(client, actors)
    candidate, profile, _ = register_candidate(client, notice)
    application = call(
        client,
        "post",
        "/applications",
        candidate,
        {
            "vacancy_id": vacancy["id"],
            "notice_id": notice["id"],
            "consent": True,
            "answers": {"interest": "Interesse profissional"},
        },
        201,
    )
    call(
        client,
        "get",
        "/applications/" + application["id"],
        actors["outsider"]["headers"],
        expected=404,
    )
    call(
        client,
        "get",
        "/applications/" + application["id"],
        actors["interviewer"]["headers"],
        expected=404,
    )
    call(client, "get", "/candidates/" + profile["id"], actors["outsider"]["headers"], expected=404)
    call(
        client,
        "get",
        "/candidates/" + profile["id"] + "/sensitive",
        actors["manager"]["headers"],
        expected=403,
    )
    call(
        client,
        "post",
        "/vacancies",
        actors["auditor"]["headers"],
        {
            "title": "Tentativa",
            "org_unit_id": actors["org"],
            "recruiter_id": actors["admin"]["id"],
            "manager_id": actors["manager"]["id"],
            "quantity": 1,
        },
        403,
    )
    another, other_profile, _ = register_candidate(client, notice)
    call(client, "get", "/applications/" + application["id"], another, expected=403)
    call(
        client,
        "post",
        "/applications/" + application["id"] + "/decision",
        candidate,
        {
            "version": application["version"],
            "decision": "SELECTED",
            "reason": "Evidências do processo concluídas",
        },
        403,
    )
    notice_record = call(
        client,
        "post",
        "/configuration/scorecards",
        admin,
        {
            "name": "Ficha independente",
            "reason": "Teste de confidencialidade",
            "data": {
                "category": "RH",
                "independent": True,
                "criteria": [
                    {
                        "key": "skill",
                        "name": "Competência",
                        "min_value": 1,
                        "max_value": 5,
                        "weight": 1,
                        "extreme_comment": False,
                    }
                ],
            },
        },
        201,
    )
    first = call(
        client,
        "post",
        "/evaluations",
        admin,
        {
            "application_id": application["id"],
            "evaluator_id": actors["interviewer"]["id"],
            "scorecard_id": notice_record["id"],
        },
        201,
    )
    second = call(
        client,
        "post",
        "/evaluations",
        admin,
        {
            "application_id": application["id"],
            "evaluator_id": actors["manager"]["id"],
            "scorecard_id": notice_record["id"],
        },
        201,
    )
    call(
        client,
        "post",
        "/evaluations/" + first["id"] + "/submit",
        actors["interviewer"]["headers"],
        {
            "version": first["version"],
            "answers": {"skill": {"value": 4, "comment": ""}},
            "recommendation": "ADVANCE",
        },
    )
    view = call(
        client,
        "get",
        "/evaluations?application_id=" + application["id"],
        actors["manager"]["headers"],
    )
    first_view = next(row for row in view["items"] if row["id"] == first["id"])
    assert (
        first_view["sealed"] is True and "score" not in first_view and "answers" not in first_view
    )
    call(
        client,
        "post",
        "/evaluations/" + second["id"] + "/submit",
        actors["manager"]["headers"],
        {
            "version": second["version"],
            "answers": {"skill": {"value": 3, "comment": ""}},
            "recommendation": "RESERVE",
        },
    )
    consensus = call(client, "get", "/applications/" + application["id"] + "/consensus", admin)
    assert consensus["sealed"] is False and consensus["mean"] == 62.5


def test_refresh_rotation_and_revocation(client, actors):
    from conftest import TEST_PASSWORD

    login = client.post(
        "/api/v1/auth/login", json={"email": actors["admin"]["email"], "password": TEST_PASSWORD}
    )
    assert login.status_code == 200
    old_cookie = client.cookies.get("tgpm_refresh")
    first = client.post("/api/v1/auth/refresh")
    assert first.status_code == 200
    new_cookie = client.cookies.get("tgpm_refresh")
    assert old_cookie != new_cookie
    client.cookies.clear()
    client.cookies.set("tgpm_refresh", old_cookie, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401
    headers = {"Authorization": "Bearer " + first.json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_audit_is_immutable(client, db, actors):
    import pytest

    row = db.scalar(select(AuditLog).limit(1))
    assert row
    with pytest.raises(DBAPIError), db.begin_nested():
        db.execute(text("UPDATE audit_logs SET action='tampered' WHERE id=:id"), {"id": row.id})
