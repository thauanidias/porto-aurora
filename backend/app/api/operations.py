import csv
import secrets
from datetime import date, datetime, time, timedelta
from io import BytesIO, StringIO
from statistics import mean, median
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Response
from pydantic import Field
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, vacancy_access, vacancy_scope
from app.core.security import encrypt
from app.domain.rules import health
from app.integrations.delivery import validate_webhook_url
from app.models import (
    Application,
    AuditLog,
    Interview,
    Notification,
    Offer,
    Outbox,
    StageHistory,
    Task,
    TestAssignment,
    TestAttempt,
    User,
    Vacancy,
    Webhook,
)
from app.repositories.common import check_version, page, serialize
from app.schemas.auth import StrictModel
from app.services.events import audit, notify

router = APIRouter(tags=["Trabalho, indicadores e integrações"])


@router.get("/dashboard")
def dashboard(db: Db, actor: Current):
    actor.require("report.view")
    vacancies = list(db.scalars(select(Vacancy).where(vacancy_scope(actor))))
    ids = [v.id for v in vacancies]
    applications = list(db.scalars(select(Application).where(Application.vacancy_id.in_(ids))))
    offers = list(
        db.scalars(select(Offer).join(Application).where(Application.vacancy_id.in_(ids)))
    )
    now = utcnow()
    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for application in applications:
        by_status[application.status] = by_status.get(application.status, 0) + 1
        by_source[application.source] = by_source.get(application.source, 0) + 1
    durations = [
        (v.closed_at - (v.published_at or v.created_at)).total_seconds() / 86400
        for v in vacancies
        if v.closed_at
    ]
    hired = [
        (
            o.responded_at - next(a for a in applications if a.id == o.application_id).created_at
        ).total_seconds()
        / 86400
        for o in offers
        if o.status == "ACCEPTED" and o.responded_at
    ]
    stage_times: dict[str, list[float]] = {}
    for item in db.scalars(
        select(StageHistory).join(Application).where(Application.vacancy_id.in_(ids))
    ):
        stage_times.setdefault(item.stage_id, []).append(
            ((item.left_at or now) - item.entered_at).total_seconds() / 3600
        )
    from app.models import PipelineStage

    stages = {
        s.id: s.name
        for s in db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id.in_(ids)))
    }

    def statistics(values):
        ordered = sorted(values)

        def percentile(p):
            if not ordered:
                return None
            index = (len(ordered) - 1) * p
            low = int(index)
            high = min(low + 1, len(ordered) - 1)
            return round(ordered[low] + (ordered[high] - ordered[low]) * (index - low), 2)

        return {
            "mean": round(mean(values), 2) if values else None,
            "median": round(median(values), 2) if values else None,
            "p75": percentile(0.75),
            "p90": percentile(0.9),
        }

    health_rows = []
    for vacancy in vacancies:
        if vacancy.status in {"PUBLISHED", "PAUSED"}:
            count = sum(a.vacancy_id == vacancy.id for a in applications)
            result = health(
                (now - (vacancy.published_at or vacancy.created_at)).total_seconds() / 3600,
                vacancy.details.get("sla_hours", 720),
                count,
            )
            health_rows.append(
                {"id": vacancy.id, "title": vacancy.title, "candidate_count": count, **result}
            )
    return {
        "open_vacancies": sum(v.status == "PUBLISHED" for v in vacancies),
        "scheduled_interviews": db.scalar(select(func.count()).select_from(Interview).where(
            Interview.vacancy_id.in_(ids), Interview.status == "SCHEDULED", Interview.starts_at >= now)) or 0,
        "pending_tests": db.scalar(select(func.count()).select_from(TestAssignment).join(Application).where(
            Application.vacancy_id.in_(ids), Application.status.in_(["ACTIVE", "RESERVE"]),
            TestAssignment.id.not_in(select(TestAttempt.assignment_id).where(TestAttempt.status == "GRADED")))) or 0,
        "approved_candidates": sum(by_status.get(status, 0) for status in ("SELECTED", "PRE_ADMISSION", "HIRED")),
        "rejected_candidates": by_status.get("REJECTED", 0),
        "stage_counts": [{"id": stage_id, "name": name,
            "count": sum(a.stage_id == stage_id and a.status in {"ACTIVE", "RESERVE"} for a in applications)}
            for stage_id, name in stages.items()],
        "recent_activity": [{"id": entry.id, "action": entry.action, "created_at": entry.created_at}
            for entry in db.scalars(select(AuditLog).where(AuditLog.vacancy_id.in_(ids),
                AuditLog.action.not_in(["candidate.accessed", "application.process_form_accessed"]))
                .order_by(AuditLog.created_at.desc()).limit(12))],
        "pending_approval": sum(v.status == "PENDING_APPROVAL" for v in vacancies),
        "active_candidates": sum(
            a.status in {"ACTIVE", "SELECTED", "PRE_ADMISSION"} for a in applications
        ),
        "hired": by_status.get("HIRED", 0),
        "withdrawn": by_status.get("WITHDRAWN", 0),
        "offer_acceptance": round(
            sum(o.status == "ACCEPTED" for o in offers) / len(offers) * 100, 2
        )
        if offers
        else None,
        "funnel": [{"name": key, "value": value} for key, value in by_status.items()],
        "sources": [{"name": key, "value": value} for key, value in by_source.items()],
        "time_to_fill": statistics(durations),
        "time_to_hire": statistics(hired),
        "stage_duration": [
            {"name": stages.get(key, key), **statistics(values)}
            for key, values in stage_times.items()
        ],
        "vacancy_health": health_rows,
        "overdue_tasks": db.scalar(
            select(func.count())
            .select_from(Task)
            .where(Task.assigned_to == actor.user.id, Task.status == "OPEN", Task.due_at < now)
        )
        or 0,
        "formulas": {
            "time_to_fill": "Encerramento menos publicação (dias)",
            "time_to_hire": "Aceite menos candidatura (dias)",
            "stage_duration": "Saída (ou agora) menos entrada (horas)",
        },
    }


class TaskInput(StrictModel):
    title: str = Field(min_length=3, max_length=180)
    assigned_to: str
    due_at: datetime
    priority: Literal["LOW", "NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
    description: str = ""
    vacancy_id: str | None = None


@router.get("/tasks")
def tasks(
    db: Db,
    actor: Current,
    status: str = "",
    q: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    query = select(Task).where(Task.assigned_to == actor.user.id, Task.title.ilike("%" + q + "%"))
    if status:
        query = query.where(Task.status == status)
    return page(db, query.order_by(Task.due_at), page_number, 25)


@router.post("/tasks", status_code=201)
def create_task(body: TaskInput, db: Db, actor: Current):
    actor.require("task.manage")
    if body.vacancy_id:
        vacancy_access(db, actor, body.vacancy_id, "task.manage")
    if not body.due_at.tzinfo:
        raise DomainError("Informe prazo com fuso horário.")
    assigned = db.get(User, body.assigned_to)
    if not assigned or not assigned.active or assigned.kind != "INTERNAL":
        raise DomainError("Responsável inválido.")
    row = Task(**body.model_dump(), created_by=actor.user.id)
    db.add(row)
    audit(db, actor, "task.created", row, vacancy_id=body.vacancy_id)
    notify(db, body.assigned_to, "Nova tarefa", body.title, "TASK")
    return serialize(row)


class TaskStatus(StrictModel):
    version: int
    status: Literal["OPEN", "DONE", "CANCELED"]


@router.put("/tasks/{task_id}")
def task_status(task_id: str, body: TaskStatus, db: Db, actor: Current):
    row = db.get(Task, task_id)
    if not row or row.assigned_to != actor.user.id:
        raise DomainError("Tarefa não encontrada.", 404)
    check_version(row, body.version)
    row.status = body.status
    audit(db, actor, "task.updated", row, vacancy_id=row.vacancy_id)
    return serialize(row)


@router.get("/notifications")
def notifications(db: Db, actor: Current):
    result = page(
        db,
        select(Notification)
        .where(Notification.user_id == actor.user.id, Notification.status != "ARCHIVED")
        .order_by(Notification.created_at.desc()),
        1,
        100,
    )
    result["unread"] = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == actor.user.id, Notification.status == "UNREAD")
    )
    return result


class NotificationStatus(StrictModel):
    status: Literal["READ", "ARCHIVED"]


@router.put("/notifications/{notification_id}")
def notification_status(notification_id: str, body: NotificationStatus, db: Db, actor: Current):
    row = db.get(Notification, notification_id)
    if not row or row.user_id != actor.user.id:
        raise DomainError("Notificação não encontrada.", 404)
    row.status = body.status
    return serialize(row)


@router.get("/audit")
def logs(
    db: Db,
    actor: Current,
    action: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
    q: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
):
    actor.require("audit.view")
    if date_from and date_to and date_from > date_to:
        raise DomainError("A data inicial deve ser anterior ou igual à data final.")
    query = select(AuditLog).outerjoin(User, User.id == AuditLog.user_id).outerjoin(
        Vacancy, Vacancy.id == AuditLog.vacancy_id)
    if "system.manage" not in actor.permissions:
        query = query.where(AuditLog.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))))
    if action:
        query = query.where(AuditLog.action.ilike("%" + action + "%"))
    if q.strip():
        term = "%" + q.strip() + "%"
        query = query.where(or_(AuditLog.action.ilike(term), User.name.ilike(term),
                                Vacancy.title.ilike(term), AuditLog.entity_id.ilike(term)))
    local = ZoneInfo("America/Fortaleza")
    if date_from:
        query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min, local))
    if date_to:
        query = query.where(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min, local))
    names, titles = {}, {}

    def prepare(records):
        names.update(db.execute(select(User.id, User.name).where(User.id.in_([r.user_id for r in records]))).all())
        titles.update(db.execute(select(Vacancy.id, Vacancy.title).where(Vacancy.id.in_([r.vacancy_id for r in records]))).all())

    return page(db, query.order_by(AuditLog.created_at.desc(), AuditLog.id), page_number, 50,
                lambda row: serialize(row) | {"user_name": names.get(row.user_id),
                    "vacancy_title": titles.get(row.vacancy_id)}, prepare=prepare)


REPORTS: dict[str, tuple[Any, set[str]]] = {
    "vacancies": (
        Vacancy,
        {
            "code",
            "title",
            "status",
            "city",
            "state",
            "quantity",
            "created_at",
            "published_at",
            "closed_at",
        },
    ),
    "applications": (
        Application,
        {
            "id",
            "vacancy_id",
            "status",
            "source",
            "created_at",
            "stage_entered_at",
            "selected_at",
            "closed_at",
        },
    ),
    "interviews": (Interview, {"id", "title", "kind", "starts_at", "ends_at", "status"}),
    "offers": (
        Offer,
        {"id", "application_id", "number", "status", "created_at", "responded_at", "expires_at"},
    ),
    "tasks": (Task, {"id", "title", "priority", "status", "due_at"}),
    "audit": (AuditLog, {"id", "created_at", "action", "entity", "entity_id", "user_id"}),
}


def report_query(entity, actor):
    if entity not in REPORTS:
        raise DomainError("Relatório não encontrado.", 404)
    model, columns = REPORTS[entity]
    query = select(model)
    ids = select(Vacancy.id).where(vacancy_scope(actor))
    if model is Vacancy:
        query = query.where(vacancy_scope(actor))
    elif model is Offer:
        query = query.where(
            Offer.application_id.in_(select(Application.id).where(Application.vacancy_id.in_(ids)))
        )
    elif model is Task:
        query = query.where(Task.assigned_to == actor.user.id)
    elif model is AuditLog:
        actor.require("audit.view")
        query = query.where(AuditLog.vacancy_id.in_(ids))
    else:
        query = query.where(model.vacancy_id.in_(ids))
    return query, columns


@router.get("/reports")
def report_options(actor: Current):
    actor.require("report.view")
    return {
        name: sorted(columns)
        for name, (_, columns) in REPORTS.items()
        if name != "audit" or "audit.view" in actor.permissions
    }


@router.get("/reports/{entity}")
def report(
    entity: str,
    db: Db,
    actor: Current,
    columns: str = "",
    status: str = "",
    output: Literal["json", "csv", "xlsx"] = "json",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    actor.require("report.view")
    query, allowed = report_query(entity, actor)
    selected = set(columns.split(",")) if columns else allowed
    if not selected <= allowed:
        raise DomainError("Colunas não autorizadas.", 403)
    model = REPORTS[entity][0]
    if status and hasattr(model, "status"):
        query = query.where(model.status == status)
    query = query.order_by(model.created_at.desc())
    if output == "json":
        return page(
            db,
            query,
            page_number,
            50,
            lambda row: {key: value for key, value in serialize(row).items() if key in selected},
        )
    actor.require("report.export")
    rows = db.scalars(query.limit(10001)).all()
    if len(rows) > 10000:
        raise DomainError("Refine os filtros para exportar até 10.000 registros.")
    keys = sorted(selected)

    def safe(value):
        if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
            return "'" + value
        return value

    data = [[safe(serialize(row).get(key)) for key in keys] for row in rows]
    audit_row = AuditLog(
        user_id=actor.user.id,
        action="report.exported",
        entity=entity,
        entity_id=actor.user.id,
        before={},
        after={"filters": {"status": status}, "columns": keys, "count": len(data)},
        ip=actor.ip,
        request_id=actor.request_id,
    )
    db.add(audit_row)
    if output == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(keys)
        writer.writerows(data)
        content = ("\ufeff" + buffer.getvalue()).encode()
        mime = "text/csv; charset=utf-8"
    else:
        from openpyxl import Workbook

        book = Workbook(write_only=True)
        sheet = book.create_sheet("Relatório")
        sheet.append(keys)
        for row in data:
            sheet.append(row)
        buffer_binary = BytesIO()
        book.save(buffer_binary)
        content = buffer_binary.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(
        content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="relatorio.{output}"'},
    )


class WebhookInput(StrictModel):
    name: str = Field(min_length=3)
    url: str
    events: list[str] = Field(min_length=1, max_length=20)
    enabled: bool = False


@router.get("/webhooks")
def webhooks(db: Db, actor: Current):
    actor.require("webhook.manage")
    return page(db, select(Webhook).order_by(Webhook.created_at.desc()), 1, 100)


@router.post("/webhooks", status_code=201)
def create_webhook(body: WebhookInput, db: Db, actor: Current):
    actor.require("webhook.manage")
    validate_webhook_url(body.url)
    secret = secrets.token_urlsafe(48)
    row = Webhook(**body.model_dump(), encrypted_secret=encrypt(secret), created_by=actor.user.id)
    db.add(row)
    audit(db, actor, "webhook.created", row)
    return serialize(row) | {"secret_once": secret}


@router.get("/deliveries")
def deliveries(db: Db, actor: Current):
    actor.require("config.manage")
    return page(
        db,
        select(Outbox)
        .where(Outbox.kind.in_(["EMAIL", "WEBHOOK", "GRAPH"]))
        .order_by(Outbox.created_at.desc()),
        1,
        100,
        lambda row: serialize(row, {"payload"}),
    )


@router.post("/deliveries/{delivery_id}/replay")
def replay(delivery_id: str, db: Db, actor: Current):
    actor.require("webhook.manage")
    row = db.get(Outbox, delivery_id)
    if not row or row.status not in {"DEAD", "DISABLED"}:
        raise DomainError("Entrega não está disponível para reprocessamento.", 409)
    row.status, row.available_at, row.attempts = "PENDING", utcnow(), 0
    audit(db, actor, "delivery.replayed", row)
    return serialize(row, {"payload"})
