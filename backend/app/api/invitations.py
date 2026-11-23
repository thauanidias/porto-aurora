import secrets
from datetime import timedelta

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import select

from app.api.public import public_vacancy
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, candidate_access, vacancy_access
from app.core.security import digest
from app.models import AuthToken, ConfigRecord, PipelineStage, Vacancy
from app.schemas.auth import StrictModel
from app.services.events import audit, email
from app.services.smtp_config import smtp_runtime

router = APIRouter(tags=["Convites privados"])


class InvitationInput(StrictModel):
    candidate_id: str
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/vacancies/{vacancy_id}/invite", status_code=201)
def invite(vacancy_id: str, body: InvitationInput, db: Db, actor: Current):
    vacancy = vacancy_access(db, actor, vacancy_id, "message.send")
    candidate = candidate_access(db, actor, body.candidate_id)
    if vacancy.status != "PUBLISHED" or not vacancy.deadline or vacancy.deadline <= utcnow():
        raise DomainError("A vaga precisa estar publicada e dentro do prazo.", 409)
    notice = db.get(ConfigRecord, vacancy.details.get("notice_id", ""))
    if not notice or not notice.active:
        raise DomainError("Aviso de privacidade indisponível.", 409)
    raw = secrets.token_urlsafe(48)
    token = AuthToken(
        user_id=candidate.user_id,
        token_hash=digest(raw),
        purpose="VACANCY_INVITE:" + vacancy.id,
        expires_at=min(vacancy.deadline, utcnow() + timedelta(days=7)),
    )
    db.add(token)
    email(
        db,
        candidate.email,
        "Convite para processo seletivo Porto Aurora",
        "Conheça a oportunidade e manifeste seu interesse: "
        + smtp_runtime(db).public_url.rstrip("/")
        + "/convite#token="
        + raw,
        "invite:" + digest(raw),
    )
    audit(
        db,
        actor,
        "candidate.invited",
        candidate,
        after={"reason": body.reason},
        vacancy_id=vacancy.id,
    )
    return {
        "message": "Convite registrado na fila de comunicação. O envio depende do SMTP habilitado.",
        "delivery_enabled": smtp_runtime(db).enabled,
    }


class InvitationToken(StrictModel):
    token: str = Field(min_length=20, max_length=300)


@router.post("/public/invitations/lookup")
def lookup(body: InvitationToken, db: Db):
    token = db.scalar(select(AuthToken).where(AuthToken.token_hash == digest(body.token)))
    if (
        not token
        or token.used_at
        or token.expires_at <= utcnow()
        or not token.purpose.startswith("VACANCY_INVITE:")
    ):
        raise DomainError("Convite inválido ou expirado.", 404)
    row = db.get(Vacancy, token.purpose.split(":", 1)[1])
    if not row or row.status != "PUBLISHED" or not row.deadline or row.deadline <= utcnow():
        raise DomainError("Oportunidade encerrada.", 404)
    stages = db.scalars(
        select(PipelineStage)
        .where(PipelineStage.vacancy_id == row.id)
        .order_by(PipelineStage.position)
    )
    return public_vacancy(row) | {
        "stages": [{"name": s.name, "position": s.position} for s in stages]
    }
