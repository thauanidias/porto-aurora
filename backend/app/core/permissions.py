from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, utcnow
from app.core.errors import DomainError
from app.core.portals import require_portal
from app.core.security import decode_token
from app.models import (
    Application,
    AuthSession,
    Candidate,
    Evaluation,
    InterviewParticipant,
    PipelineStage,
    RolePermission,
    User,
    UserRole,
    Vacancy,
    VacancyAssignment,
)

PERMISSIONS = {
    "system.manage",
    "user.manage",
    "role.manage",
    "org.manage",
    "config.manage",
    "vacancy.create",
    "vacancy.edit",
    "vacancy.approve",
    "vacancy.publish",
    "vacancy.view",
    "vacancy.all",
    "request.create",
    "request.approve",
    "candidate.view",
    "candidate.all",
    "candidate.sensitive.view",
    "candidate.registration.view",
    "candidate.evaluate",
    "candidate.move",
    "candidate.select",
    "candidate.merge",
    "candidate.import",
    "candidate.export",
    "score.manage",
    "test.manage",
    "interview.manage",
    "offer.create",
    "offer.approve",
    "report.view",
    "report.export",
    "audit.view",
    "privacy.manage",
    "talent.manage",
    "message.send",
    "task.manage",
    "document.review",
    "internal.view",
    "referral.create",
    "webhook.manage",
}
ROLES = {
    "SUPER_ADMIN": PERMISSIONS,
    "RH_ADMIN": PERMISSIONS - {"system.manage", "role.manage"},
    "RECRUTADOR": {
        "candidate.registration.view",
        "vacancy.create",
        "vacancy.edit",
        "vacancy.view",
        "candidate.view",
        "candidate.evaluate",
        "candidate.move",
        "candidate.select",
        "test.manage",
        "interview.manage",
        "offer.create",
        "report.view",
        "talent.manage",
        "message.send",
        "task.manage",
        "document.review",
    },
    "ANALISTA_RH": {
        "candidate.registration.view",
        "vacancy.view",
        "candidate.view",
        "candidate.evaluate",
        "candidate.move",
        "interview.manage",
        "message.send",
        "task.manage",
        "document.review",
    },
    "SOLICITANTE": {"request.create", "vacancy.view"},
    "GESTOR": {
        "request.create",
        "vacancy.view",
        "candidate.view",
        "candidate.evaluate",
        "interview.manage",
        "report.view",
    },
    "APROVADOR": {"vacancy.view", "request.approve", "vacancy.approve", "offer.approve"},
    "ENTREVISTADOR": {"candidate.view", "candidate.evaluate"},
    "AUDITOR": {"vacancy.view", "candidate.view", "report.view", "audit.view"},
    "COLABORADOR": {"internal.view", "referral.create"},
    "CANDIDATO": set(),
}


@dataclass
class Actor:
    user: User
    permissions: set[str]
    session_id: str
    ip: str
    request_id: str

    def require(self, permission: str) -> None:
        if permission not in self.permissions:
            raise DomainError("Você não tem permissão para esta ação.", 403, "FORBIDDEN")


bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db, scope="function")]


def get_actor(
    request: Request,
    db: Db,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Actor:
    if credentials is None:
        raise DomainError("Entre para continuar.", 401, "UNAUTHENTICATED")
    payload = decode_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    session = db.get(AuthSession, payload["sid"])
    if (
        not user
        or not user.active
        or not session
        or session.user_id != user.id
        or session.revoked_at
        or session.expires_at <= utcnow()
    ):
        raise DomainError("Sessão encerrada. Entre novamente.", 401, "UNAUTHENTICATED")
    if (
        settings().email_verification_required
        and user.kind == "CANDIDATO"
        and not user.email_verified
    ):
        raise DomainError("Confirme seu e-mail antes de entrar.", 403, "EMAIL_NOT_VERIFIED")
    permissions = set(
        db.scalars(
            select(RolePermission.permission)
            .join(UserRole, RolePermission.role_id == UserRole.role_id)
            .where(UserRole.user_id == user.id)
        )
    )
    require_portal(request, db, user)
    from app.services.directory_access import require_directory_session
    require_directory_session(db, user, session)
    if user.kind == "CANDIDATO" and request.method not in {"GET", "HEAD", "OPTIONS"} and not request.url.path.startswith((
        "/api/v1/auth/", "/api/v1/privacy/", "/api/v1/public/consent-receipts")):
        from app.services.electronic_acceptance import has_registration_acceptance
        if not has_registration_acceptance(db, user):
            raise DomainError("Leia e aceite o termo de consentimento antes de continuar na área do candidato.", 403, "CONSENT_REQUIRED")
    return Actor(
        user,
        permissions,
        session.id,
        request.client.host if request.client else "",
        request.state.request_id,
    )


Current = Annotated[Actor, Depends(get_actor)]


def is_manager(actor: Actor) -> bool:
    return "request.create" in actor.permissions and not (
        {"vacancy.create", "request.approve"} & actor.permissions
    )


def sector_finalist_ids(actor: Actor):
    assigned = select(VacancyAssignment.vacancy_id).where(VacancyAssignment.user_id == actor.user.id)
    return select(Application.id).join(Vacancy, Application.vacancy_id == Vacancy.id).join(
        PipelineStage, Application.stage_id == PipelineStage.id,
    ).where(
        Vacancy.org_unit_id == actor.user.org_unit_id,
        Vacancy.org_unit_id.is_not(None),
        or_(Vacancy.confidential.is_(False), Vacancy.manager_id == actor.user.id, Vacancy.id.in_(assigned)),
        Application.status.in_(["ACTIVE", "SELECTED", "PRE_ADMISSION", "HIRED"]),
        or_(PipelineStage.kind == "FINALIST", Application.status.in_(["SELECTED", "PRE_ADMISSION", "HIRED"])),
    )


def vacancy_scope(actor: Actor):
    if "vacancy.all" in actor.permissions:
        return Vacancy.id.is_not(None)
    assigned = select(VacancyAssignment.vacancy_id).where(
        VacancyAssignment.user_id == actor.user.id
    )
    conditions = [
        Vacancy.recruiter_id == actor.user.id,
        Vacancy.manager_id == actor.user.id,
        Vacancy.id.in_(assigned),
    ]
    manager_only = "request.create" in actor.permissions and not ({"vacancy.create", "request.approve"} & actor.permissions)
    if actor.user.org_unit_id and not manager_only:
        conditions.append(
            (Vacancy.org_unit_id == actor.user.org_unit_id) & Vacancy.confidential.is_(False)
        )
    return or_(*conditions)


def vacancy_access(
    db: Session, actor: Actor, vacancy_id: str, permission: str = "vacancy.view"
) -> Vacancy:
    actor.require(permission)
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id, vacancy_scope(actor)))
    if not vacancy and permission == "vacancy.view" and is_manager(actor):
        eligible = db.scalar(select(Application.id).where(
            Application.vacancy_id == vacancy_id, Application.id.in_(sector_finalist_ids(actor)),
        ).limit(1))
        if eligible:
            vacancy = db.get(Vacancy, vacancy_id)
    if not vacancy:
        raise DomainError("Vaga não encontrada ou acesso não autorizado.", 404, "NOT_FOUND")
    return vacancy


def application_access(
    db: Session, actor: Actor, application_id: str, permission: str = "candidate.view"
) -> Application:
    application = db.get(Application, application_id)
    if not application:
        raise DomainError("Candidatura não encontrada.", 404)
    candidate = db.get(Candidate, application.candidate_id)
    if candidate and candidate.user_id == actor.user.id and permission == "candidate.view":
        return application
    actor.require(permission)
    if permission == "candidate.view" and is_manager(actor) and db.scalar(
        select(Application.id).where(Application.id == application.id, Application.id.in_(sector_finalist_ids(actor)))
    ):
        return application
    assigned = db.scalar(
        select(Evaluation.id).where(
            Evaluation.application_id == application.id, Evaluation.evaluator_id == actor.user.id
        )
    )
    interview = db.scalar(
        select(InterviewParticipant.id).where(
            InterviewParticipant.application_id == application.id,
            InterviewParticipant.user_id == actor.user.id,
        )
    )
    if not assigned and not interview:
        vacancy_access(db, actor, application.vacancy_id, permission)
    return application


def candidate_access(
    db: Session, actor: Actor, candidate_id: str, permission: str = "candidate.view"
) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if not candidate:
        raise DomainError("Candidato não encontrado.", 404)
    if candidate.user_id == actor.user.id and permission == "candidate.view":
        return candidate
    actor.require(permission)
    if "candidate.all" not in actor.permissions:
        ids = db.scalars(
            select(Application.id).where(Application.candidate_id == candidate.id)
        ).all()
        for item in ids:
            try:
                application_access(db, actor, item, permission)
                return candidate
            except DomainError:
                continue
        raise DomainError("Candidato não encontrado.", 404)
    return candidate
