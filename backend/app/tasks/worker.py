import logging
from datetime import timedelta
from pathlib import Path

from celery import Celery
from sqlalchemy import case, select

from app.core.config import settings
from app.core.db import SessionLocal, utcnow
from app.core.errors import DomainError
from app.core.permissions import Actor
from app.core.security import decrypt
from app.domain.rules import matches
from app.integrations.delivery import graph_event, send_email, send_webhook
from app.models import (
    Application,
    AutomationExecution,
    Candidate,
    CandidateLabel,
    ConfigRecord,
    Interview,
    InterviewParticipant,
    Offer,
    Outbox,
    RolePermission,
    Task,
    TestAssignment,
    TestAttempt,
    User,
    UserRole,
    Vacancy,
    VacancyAssignment,
    Webhook,
)
from app.services.events import notify

celery = Celery("tgpm-talentos", broker=settings().redis_url)
celery.conf.update(
    timezone="UTC",
    task_serializer="json",
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "deliver-outbox": {"task": "tgpm.drain", "schedule": 1.0},
        "retention-review": {"task": "tgpm.retention", "schedule": 86400.0},
        "expire-records": {"task": "tgpm.expire", "schedule": 30.0},
    },
)
logger = logging.getLogger("tgpm.jobs")


@celery.task(name="tgpm.resume_import", bind=True, soft_time_limit=3600, time_limit=3660, max_retries=60)
def resume_import(self, owner, document_id):
    from app.services.resume_jobs import run_import, write_job
    try:
        run_import(owner, document_id)
    except DomainError as exc:
        if exc.status == 429 and self.request.retries < self.max_retries:
            raise self.retry(countdown=15) from exc
        write_job(owner, document_id, {"status": "FAILED", "message": exc.message})
    except Exception:
        # Never log document contents or personal fields from the extraction.
        write_job(owner, document_id, {"status": "FAILED", "message": "Não foi possível concluir a leitura. O currículo continua anexado. Tente novamente ou preencha manualmente."})


def process_event(db, entry):
    payload = entry.payload
    for webhook in (
        []
        if payload.get("_application_only")
        else db.scalars(select(Webhook).where(Webhook.enabled.is_(True)))
    ):
        if payload["event"] in webhook.events:
            db.add(
                Outbox(
                    kind="WEBHOOK",
                    dedup_key="hook:" + webhook.id + ":" + payload["event_id"],
                    payload={"webhook_id": webhook.id, "event": payload},
                )
            )
    multi_entity = payload["entity"] in {"interviews", "vacancies"}
    parent = (
        db.get(Interview if payload["entity"] == "interviews" else Vacancy, payload["id"])
        if multi_entity
        else None
    )
    for rule in db.scalars(
        select(ConfigRecord).where(
            ConfigRecord.kind == "automations", ConfigRecord.active.is_(True)
        )
    ):
        data = rule.data
        candidate_action = data["action"] in {"TAG", "EMAIL", "MOVE"}
        if (payload.get("_application_only") and not candidate_action) or (
            multi_entity and candidate_action
        ):
            continue
        if not data.get("approved") or data["event"] != payload["event"]:
            continue
        if db.scalar(
            select(AutomationExecution.id).where(
                AutomationExecution.rule_id == rule.id,
                AutomationExecution.event_id == payload["event_id"],
            )
        ):
            continue
        application = (
            db.get(Application, payload["id"]) if payload["entity"] == "applications" else None
        )
        related = None
        if payload["entity"] == "test_attempts":
            attempt = db.get(TestAttempt, payload["id"])
            related = db.get(TestAssignment, attempt.assignment_id) if attempt else None
        elif payload["entity"] == "offers":
            related = db.get(Offer, payload["id"])
        if related:
            application = db.get(Application, related.application_id)
        facts = (
            (
                application.profile_snapshot.get("facts", {})
                | {"status": application.status, "stage_id": application.stage_id}
            )
            if application
            else {}
        )
        if payload["entity"] == "test_attempts" and attempt:
            facts |= {
                "test_score": float(attempt.score) if attempt.score is not None else None,
                "event_status": attempt.status,
            }
        if parent:
            facts |= {"status": parent.status, "event_status": parent.status}
        if payload.get("_event_status"):
            facts["event_status"] = payload["_event_status"]
        if not matches(data.get("conditions", {}), facts):
            continue
        user = db.get(User, rule.created_by)
        if not user or not user.active:
            continue
        permissions = set(
            db.scalars(
                select(RolePermission.permission)
                .join(UserRole, RolePermission.role_id == UserRole.role_id)
                .where(UserRole.user_id == user.id)
            )
        )
        actor = Actor(user, permissions, "", "", payload["event_id"])
        action = data["action"]
        if payload.get("vacancy_id"):
            from app.core.permissions import vacancy_access

            try:
                vacancy_access(
                    db,
                    actor,
                    payload["vacancy_id"],
                    {
                        "TAG": "talent.manage",
                        "EMAIL": "message.send",
                        "MOVE": "candidate.move",
                        "TASK": "task.manage",
                        "ASSIGN": "vacancy.edit",
                    }.get(action, "vacancy.view"),
                )
            except DomainError as exc:
                if exc.status == 403:
                    continue
                raise
        if action == "NOTIFY":
            target = db.get(User, data["target_id"])
            if not target:
                raise DomainError("Destinatário da automação inválido")
            notify(db, target.id, "Atualização do processo", data["text"], "SYSTEM")
        elif action == "TASK":
            actor.require("task.manage")
            db.add(
                Task(
                    title=data["text"][:180],
                    assigned_to=data["target_id"],
                    created_by=user.id,
                    vacancy_id=payload.get("vacancy_id"),
                    due_at=utcnow() + timedelta(hours=48),
                )
            )
        elif action == "TAG" and application:
            actor.require("talent.manage")
            if not db.scalar(
                select(CandidateLabel.id).where(
                    CandidateLabel.candidate_id == application.candidate_id,
                    CandidateLabel.user_id == user.id,
                    CandidateLabel.kind == "TAG",
                    CandidateLabel.label == data["text"],
                )
            ):
                db.add(
                    CandidateLabel(
                        candidate_id=application.candidate_id,
                        user_id=user.id,
                        label=data["text"],
                        kind="TAG",
                    )
                )
        elif action == "ASSIGN" and payload.get("vacancy_id"):
            actor.require("vacancy.edit")
            if not db.scalar(
                select(VacancyAssignment.id).where(
                    VacancyAssignment.vacancy_id == payload["vacancy_id"],
                    VacancyAssignment.user_id == data["target_id"],
                )
            ):
                db.add(
                    VacancyAssignment(vacancy_id=payload["vacancy_id"], user_id=data["target_id"])
                )
        elif action == "EMAIL" and application:
            actor.require("message.send")
            candidate = db.get(Candidate, application.candidate_id)
            db.add(
                Outbox(
                    kind="EMAIL",
                    dedup_key="auto:" + rule.id + ":" + payload["event_id"],
                    payload={
                        "recipient": candidate.email,
                        "subject": "Porto Aurora Talentos",
                        "body": data["text"],
                    },
                )
            )
        elif action == "MOVE" and application:
            if payload.get("automation_depth", 0) >= 3:
                raise DomainError("Limite de encadeamento de automações atingido")
            from app.services.events import event_depth
            from app.services.recruitment import move

            token = event_depth.set(payload.get("automation_depth", 0) + 1)
            try:
                move(db, actor, application, data["target_id"], "Automação aprovada: " + rule.name)
            finally:
                event_depth.reset(token)
        else:
            raise DomainError("A ação configurada não se aplica ao evento")
        db.add(
            AutomationExecution(
                rule_id=rule.id, event_id=payload["event_id"], status="COMPLETED", detail=action
            )
        )

    if multi_entity and parent:
        from types import SimpleNamespace

        if payload["entity"] == "interviews":
            ids = db.scalars(
                select(InterviewParticipant.application_id).where(
                    InterviewParticipant.interview_id == parent.id,
                    InterviewParticipant.application_id.is_not(None),
                )
            ).all()
        else:
            ids = db.scalars(
                select(Application.id).where(Application.vacancy_id == parent.id)
            ).all()
        for application_id in set(ids):
            process_event(
                db,
                SimpleNamespace(
                    payload=payload
                    | {
                        "entity": "applications",
                        "id": application_id,
                        "event_id": payload["event_id"] + ":" + application_id,
                        "_application_only": True,
                        "_event_status": parent.status,
                    }
                ),
            )


@celery.task(name="tgpm.drain")
def drain():
    processed = 0
    for _ in range(50):
        with SessionLocal.begin() as db:
            entry = db.scalar(
                select(Outbox)
                .where(Outbox.status.in_(["PENDING", "RETRY"]), Outbox.available_at <= utcnow())
                .order_by(case((Outbox.kind == "EMAIL", 0), else_=1), Outbox.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if not entry:
                break
            entry.attempts += 1
            try:
                with db.begin_nested():
                    if entry.kind == "EMAIL":
                        send_email(entry.payload, entry.dedup_key, db=db)
                    elif entry.kind == "EVENT":
                        process_event(db, entry)
                    elif entry.kind == "WEBHOOK":
                        webhook = db.get(Webhook, entry.payload["webhook_id"])
                        if not webhook or not webhook.enabled:
                            raise DomainError("WEBHOOK_DISABLED", 503)
                        send_webhook(
                            webhook.url,
                            decrypt(webhook.encrypted_secret),
                            entry.payload["event"],
                            entry.dedup_key,
                        )
                    elif entry.kind == "GRAPH":
                        graph_event(entry.payload)
                    elif entry.kind == "DELETE_FILE":
                        key = entry.payload["storage_key"]
                        if Path(key).name != key:
                            raise DomainError("Chave de arquivo inválida")
                        (Path(settings().upload_dir) / key).unlink(missing_ok=True)
                    else:
                        raise DomainError("Tipo de tarefa inválido")
                entry.status = "SENT"
                entry.error = ""
            except Exception as exc:
                disabled = isinstance(exc, DomainError) and exc.message.endswith("_DISABLED")
                entry.status = (
                    "DISABLED" if disabled else "DEAD" if entry.attempts >= 6 else "RETRY"
                )
                entry.available_at = utcnow() + timedelta(seconds=min(3600, 30 * 2**entry.attempts))
                entry.error = exc.message if isinstance(exc, DomainError) else type(exc).__name__
                logger.warning(
                    "delivery_failed",
                    extra={"job_id": entry.id, "attempts": entry.attempts, "kind": entry.kind},
                )
            processed += 1
    return processed


@celery.task(name="tgpm.retention")
def retention():
    from app.services.maintenance import apply_retention

    with SessionLocal.begin() as db:
        return apply_retention(db)


@celery.task(name="tgpm.expire")
def expire():
    from app.services.maintenance import emit_sla_events, expire_records

    with SessionLocal.begin() as db:
        return {"expired": expire_records(db), "sla_events": emit_sla_events(db)}
