from datetime import timedelta

from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.core.db import utcnow
from app.models import (
    Application,
    Assessment,
    AuthSession,
    Candidate,
    PipelineStage,
    StageHistory,
    User,
    Vacancy,
)
from app.models import (
    TestAssignment as Assignment,
)
from app.models import TestAttempt as Attempt


def registered_application(client, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    headers, profile, _ = register_candidate(client, notice)
    application = call(
        client,
        "post",
        "/applications",
        headers,
        {
            "vacancy_id": vacancy["id"],
            "notice_id": notice["id"],
            "consent": True,
            "answers": {"interest": "Interesse profissional"},
        },
        201,
    )
    return vacancy, notice, headers, profile, application


def test_required_test_minimum_blocks_progression(client, db, actors):
    vacancy, _, _, _, app = registered_application(client, actors)
    stages = list(
        db.scalars(
            select(PipelineStage)
            .where(PipelineStage.vacancy_id == vacancy["id"])
            .order_by(PipelineStage.position)
        )
    )
    admin = actors["admin"]["headers"]
    app = call(
        client,
        "post",
        "/applications/" + app["id"] + "/move",
        admin,
        {"stage_id": stages[1].id, "version": app["version"]},
    )
    stages[1].required = True
    assessment = Assessment(name="Teste mínimo", created_by=actors["admin"]["id"], questions=[])
    db.add(assessment)
    db.flush()
    assignment = Assignment(
        application_id=app["id"],
        assessment_id=assessment.id,
        snapshot={"pass_score": 60},
        opens_at=utcnow(),
        due_at=utcnow() + timedelta(days=1),
        created_by=actors["admin"]["id"],
    )
    db.add(assignment)
    db.flush()
    attempt = Attempt(
        assignment_id=assignment.id, number=1, started_at=utcnow(), status="GRADED", score=40
    )
    db.add(attempt)
    db.commit()
    call(
        client,
        "post",
        "/applications/" + app["id"] + "/move",
        admin,
        {"stage_id": stages[2].id, "version": app["version"]},
        409,
    )
    attempt.score = 80
    db.commit()
    call(
        client,
        "post",
        "/applications/" + app["id"] + "/move",
        admin,
        {"stage_id": stages[2].id, "version": app["version"]},
    )


def test_return_requires_policy_consent_and_preserves_history(client, db, actors):
    vacancy, notice, headers, _, app = registered_application(client, actors)
    original_history = set(db.scalars(select(StageHistory.id).where(StageHistory.application_id == app["id"])))
    app = call(
        client,
        "post",
        "/applications/" + app["id"] + "/decision",
        headers,
        {"version": app["version"], "decision": "WITHDRAWN"},
    )
    body = {"version": app["version"], "notice_id": notice["id"], "consent": True}
    call(client, "post", "/applications/" + app["id"] + "/return", headers, body, 409)
    vacancy_row = db.get(Vacancy, vacancy["id"])
    vacancy_row.details = vacancy_row.details | {"allow_withdrawal_return": True}
    db.commit()
    call(
        client,
        "post",
        "/applications/" + app["id"] + "/return",
        headers,
        body | {"consent": False},
        422,
    )
    returned = call(client, "post", "/applications/" + app["id"] + "/return", headers, body)
    assert returned["id"] == app["id"] and returned["status"] == "ACTIVE"
    histories = list(
        db.scalars(select(StageHistory).where(StageHistory.application_id == app["id"]))
    )
    assert len(histories) == len(original_history) + 1 and sum(h.left_at is None for h in histories) == 1
    assert original_history.issubset({history.id for history in histories})


def test_reviewed_merge_revokes_source_login_and_retains_audit_link(client, db, actors):
    _, notice, _, target, _ = registered_application(client, actors)
    headers, source, _ = register_candidate(client, notice)
    source_row = db.get(Candidate, source["id"])
    source_user = db.get(User, source_row.user_id)
    admin = actors["admin"]["headers"]
    call(
        client,
        "post",
        "/candidates/" + target["id"] + "/merge",
        admin,
        {"source_id": source["id"], "reason": "Identidade conferida na revisão manual"},
    )
    db.refresh(source_user)
    assert source_user.active is False
    assert db.get(Candidate, source["id"]).merged_into_id == target["id"]
    assert not list(
        db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == source_user.id, AuthSession.revoked_at.is_(None)
            )
        )
    )
    call(client, "get", "/auth/me", headers, expected=401)


def test_bulk_move_rejects_invalid_payload_and_rolls_back_conflict(client, db, actors):
    vacancy, _, _, _, app = registered_application(client, actors)
    stages = list(
        db.scalars(
            select(PipelineStage)
            .where(PipelineStage.vacancy_id == vacancy["id"])
            .order_by(PipelineStage.position)
        )
    )
    admin = actors["admin"]["headers"]
    call(
        client,
        "post",
        "/applications/bulk/move",
        admin,
        {"moves": [{"stage_id": stages[1].id, "version": app["version"]}]},
        422,
    )
    item = {"id": app["id"], "stage_id": stages[1].id, "version": app["version"]}
    call(
        client,
        "post",
        "/applications/bulk/move",
        admin,
        {"moves": [item, item | {"version": 999}]},
        409,
    )
    db.expire_all()
    assert db.get(Application, app["id"]).stage_id == stages[0].id


def test_score_uses_latest_attempt_and_automation_resolves_test_candidate(client, db, actors):
    from uuid import uuid4

    from app.models import AutomationExecution, CandidateLabel, Outbox
    from app.tasks.worker import process_event

    vacancy, _, _, profile, app = registered_application(client, actors)
    admin = actors["admin"]["headers"]
    assessment = Assessment(
        name="Teste para aderência", created_by=actors["admin"]["id"], questions=[]
    )
    db.add(assessment)
    db.flush()
    assignment = Assignment(
        application_id=app["id"],
        assessment_id=assessment.id,
        snapshot={"pass_score": 60},
        opens_at=utcnow(),
        due_at=utcnow() + timedelta(days=1),
        created_by=actors["admin"]["id"],
    )
    db.add(assignment)
    db.flush()
    for number, score in [(1, 40), (2, 80)]:
        attempt = Attempt(
            assignment_id=assignment.id,
            number=number,
            started_at=utcnow(),
            status="GRADED",
            score=score,
        )
        db.add(attempt)
        db.flush()
    model = call(
        client,
        "post",
        "/vacancies/" + vacancy["id"] + "/scoring-models",
        admin,
        {
            "criteria": [
                {
                    "key": "test",
                    "name": "Teste técnico",
                    "field": "test_score",
                    "kind": "NUMBER_MIN",
                    "weight": 100,
                    "expected": 100,
                    "justification": "Conhecimento exigido pela função",
                }
            ],
            "reason": "Critério baseado na prova real",
        },
        201,
    )
    result = call(
        client,
        "post",
        "/applications/" + app["id"] + "/recalculate",
        admin,
        {"model_id": model["id"], "reason": "Nova versão baseada na prova real"},
    )
    assert result["total"] == 80 and result["breakdown"]["items"][0]["value"] == 80
    rule = call(
        client,
        "post",
        "/configuration/automations",
        admin,
        {
            "name": "Teste " + uuid4().hex,
            "reason": "Automação aprovada pelo responsável",
            "data": {
                "event": "test.completed",
                "conditions": {"field": "test_score", "op": "gte", "value": 60},
                "action": "TAG",
                "text": "Prova concluída",
                "approved": True,
            },
        },
        201,
    )
    entry = Outbox(
        kind="EVENT",
        dedup_key=uuid4().hex,
        payload={
            "event": "test.completed",
            "entity": "test_attempts",
            "id": attempt.id,
            "vacancy_id": vacancy["id"],
            "event_id": uuid4().hex,
        },
    )
    db.add(entry)
    db.flush()
    process_event(db, entry)
    db.flush()
    process_event(db, entry)
    assert (
        len(
            list(
                db.scalars(
                    select(CandidateLabel).where(
                        CandidateLabel.candidate_id == profile["id"],
                        CandidateLabel.label == "Prova concluída",
                    )
                )
            )
        )
        == 1
    )
    assert (
        len(
            list(
                db.scalars(
                    select(AutomationExecution).where(AutomationExecution.rule_id == rule["id"])
                )
            )
        )
        == 1
    )


def test_sla_event_is_unique_and_applies_rule_to_related_candidates(client, db, actors):
    from uuid import uuid4

    from app.models import CandidateLabel, Outbox
    from app.services.maintenance import emit_sla_events
    from app.tasks.worker import process_event

    vacancy, _, _, profile, _ = registered_application(client, actors)
    row = db.get(Vacancy, vacancy["id"])
    row.published_at = utcnow() - timedelta(hours=600)
    db.commit()
    call(
        client,
        "post",
        "/configuration/automations",
        actors["admin"]["headers"],
        {
            "name": "SLA " + uuid4().hex,
            "reason": "Acompanhamento aprovado do prazo",
            "data": {
                "event": "vacancy.sla_near",
                "action": "TAG",
                "text": "Revisar prazo do processo",
                "approved": True,
            },
        },
        201,
    )
    assert emit_sla_events(db) == 1
    db.flush()
    assert emit_sla_events(db) == 0
    entry = db.scalar(select(Outbox).where(Outbox.dedup_key.like("sla:" + vacancy["id"] + ":%")))
    process_event(db, entry)
    db.flush()
    process_event(db, entry)
    assert (
        len(
            list(
                db.scalars(
                    select(CandidateLabel).where(
                        CandidateLabel.candidate_id == profile["id"],
                        CandidateLabel.label == "Revisar prazo do processo",
                    )
                )
            )
        )
        == 1
    )


def test_database_commit_finishes_before_http_success_is_sent(client):
    from fastapi.testclient import TestClient

    from app.core.db import get_db
    from app.main import app

    original = app.dependency_overrides[get_db]
    completed = False

    def guarded():
        nonlocal completed
        yield from original()
        completed = True

    app.dependency_overrides[get_db] = guarded

    async def observed(scope, receive, send):
        async def check(message):
            if message["type"] == "http.response.start":
                assert completed, "Success response preceded the transaction commit"
            await send(message)

        await app(scope, receive, check)

    try:
        with TestClient(observed) as request:
            assert request.get("/api/v1/public/privacy").status_code == 200
    finally:
        app.dependency_overrides[get_db] = original
