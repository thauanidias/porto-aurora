from copy import deepcopy
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Actor
from app.domain.rules import matches
from app.models import (
    Application,
    Approval,
    ConfigRecord,
    Offer,
    Task,
    User,
    Vacancy,
    VacancyAssignment,
    VacancyRequest,
)
from app.repositories.common import required, serialize
from app.services.events import event, notify


def submit(db: Session, actor: Actor, entity, workflow_id: str):
    if entity.status != "DRAFT":
        raise DomainError("Somente rascunhos podem ser enviados.", 409)
    workflow = db.get(ConfigRecord, workflow_id)
    if not workflow or workflow.kind != "workflows" or not workflow.active:
        raise DomainError("Selecione um fluxo de aprovação ativo.")
    target = (
        "OFFER"
        if isinstance(entity, Offer)
        else "REQUEST"
        if isinstance(entity, VacancyRequest)
        else "VACANCY"
    )
    if workflow.data.get("target") != target:
        raise DomainError("O fluxo não corresponde ao tipo de registro.")
    steps = workflow.data.get("steps", [])
    if not steps:
        raise DomainError("O fluxo precisa de aprovadores.")
    facts = serialize(entity) | getattr(entity, "details", {})
    applicable = [deepcopy(step) for step in steps if matches(step.get("conditions", {}), facts)]
    if not applicable:
        raise DomainError("Nenhuma etapa de aprovação se aplica ao registro.")
    for step in applicable:
        user = db.get(User, step.get("approver_id", ""))
        if not user or not user.active or user.kind != "INTERNAL":
            raise DomainError("O fluxo contém aprovador inválido.")
        delegate = db.get(User, step["delegate_id"]) if step.get("delegate_id") else None
        if step.get("delegate_id") and (
            not delegate or not delegate.active or delegate.kind != "INTERNAL"
        ):
            raise DomainError("Substituto inválido.")
        assigned_vacancy = (
            entity.id
            if isinstance(entity, Vacancy)
            else required(db, Application, entity.application_id).vacancy_id
            if isinstance(entity, Offer)
            else None
        )
        if assigned_vacancy and not db.scalar(
            select(VacancyAssignment.id).where(
                VacancyAssignment.vacancy_id == assigned_vacancy,
                VacancyAssignment.user_id == (delegate.id if delegate else user.id),
            )
        ):
            db.add(
                VacancyAssignment(
                    vacancy_id=assigned_vacancy, user_id=delegate.id if delegate else user.id
                )
            )
    entity.workflow_snapshot = applicable
    entity.current_step = 0
    entity.status = "PENDING_APPROVAL"
    activate_step(db, actor, entity)
    event(
        db, actor, "approval.requested", entity, entity.id if isinstance(entity, Vacancy) else None
    )


def activate_step(db, actor, entity):
    step = entity.workflow_snapshot[entity.current_step]
    due = utcnow() + timedelta(hours=int(step.get("sla_hours", 48)))
    db.add(
        Task(
            title="Aprovar " + getattr(entity, "title", "carta oferta"),
            assigned_to=step.get("delegate_id") or step["approver_id"],
            created_by=actor.user.id,
            vacancy_id=entity.id if isinstance(entity, Vacancy) else None,
            due_at=due,
            description="Registro: " + entity.id,
        )
    )
    notify(
        db,
        step.get("delegate_id") or step["approver_id"],
        "Aprovação pendente",
        "Há um registro aguardando sua decisão.",
        "APPROVAL",
        "/app/solicitacoes" if isinstance(entity, VacancyRequest) else "",
    )


def decide(db: Session, actor: Actor, entity, decision: str, comment: str):
    actor.require(
        "offer.approve"
        if isinstance(entity, Offer)
        else "request.approve"
        if isinstance(entity, VacancyRequest)
        else "vacancy.approve"
    )
    if entity.status != "PENDING_APPROVAL":
        raise DomainError("O registro não está aguardando aprovação.", 409)
    step = entity.workflow_snapshot[entity.current_step]
    approver = step.get("delegate_id") or step["approver_id"]
    if approver != actor.user.id:
        raise DomainError("Esta etapa pertence a outro aprovador.", 403)
    if decision == "REJECTED" and len(comment.strip()) < 5:
        raise DomainError("Informe justificativa para reprovar.")
    field = (
        "offer_id"
        if isinstance(entity, Offer)
        else "request_id"
        if isinstance(entity, VacancyRequest)
        else "vacancy_id"
    )
    db.add(
        Approval(
            **{field: entity.id},
            step=entity.current_step,
            approver_id=actor.user.id,
            delegated_from=step["approver_id"] if step.get("delegate_id") else None,
            decision=decision,
            comment=comment,
        )
    )
    for task in db.scalars(
        select(Task).where(
            Task.description == "Registro: " + entity.id,
            Task.assigned_to == actor.user.id,
            Task.status == "OPEN",
        )
    ):
        task.status = "DONE"
    if decision == "REJECTED":
        entity.status = "DRAFT"
    elif entity.current_step + 1 < len(entity.workflow_snapshot):
        entity.current_step += 1
        activate_step(db, actor, entity)
    else:
        entity.status = "APPROVED"
    if isinstance(entity, VacancyRequest):
        message = ("O RH devolveu a solicitação para ajustes." if decision == "REJECTED" else
                   "Sua solicitação foi aprovada." if entity.status == "APPROVED" else
                   "Uma etapa foi aprovada. A solicitação segue em análise.")
        notify(db, entity.requested_by, "Retorno da solicitação: " + entity.title,
               message + (" " + comment if comment else ""), "REQUEST", "/gestor/solicitacoes")
    event(
        db,
        actor,
        "vacancy.approved"
        if isinstance(entity, Vacancy) and entity.status == "APPROVED"
        else "approval.decided",
        entity,
        entity.id if isinstance(entity, Vacancy) else None,
    )
