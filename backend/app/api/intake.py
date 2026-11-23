import csv
import hashlib
import io
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, File, Request, Response, UploadFile
from pydantic import EmailStr, Field, ValidationError
from sqlalchemy import select

from app.api.auth import session_response
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Actor, Current, Db
from app.core.security import digest
from app.models import Application, Candidate, ConfigRecord, Referral, User, Vacancy
from app.models.intake import ImportBatch, QuickApplication
from app.repositories.common import page, serialize
from app.schemas.auth import StrictModel
from app.schemas.recruitment import ApplicationInput
from app.services.events import audit, email
from app.services.recruitment import apply
from app.services.smtp_config import smtp_runtime

router = APIRouter(tags=["Captação, indicações e importação"])


class QuickInput(StrictModel):
    vacancy_id: str
    notice_id: str
    consent: bool
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    phone: str = Field(default="", max_length=30)
    answers: dict = Field(default_factory=dict)


@router.post("/public/quick-apply")
def quick_apply(body: QuickInput, db: Db):
    if body.answers:
        raise DomainError("As perguntas serão respondidas quando o RH liberar a seleção.", 403, "STAGE_LOCKED")
    smtp = smtp_runtime(db)
    if not smtp.enabled:
        raise DomainError(
            "A candidatura por link está indisponível. Utilize o cadastro com senha.",
            503,
            "EMAIL_DISABLED",
        )
    vacancy = db.get(Vacancy, body.vacancy_id)
    notice = db.get(ConfigRecord, body.notice_id)
    if (
        not vacancy
        or vacancy.confidential
        or vacancy.audience == "INTERNAL"
        or vacancy.status != "PUBLISHED"
        or not vacancy.deadline
        or vacancy.deadline <= utcnow()
    ):
        raise DomainError("Vaga indisponível.", 409)
    if (
        not body.consent
        or not notice
        or not notice.active
        or vacancy.details.get("notice_id") != notice.id
    ):
        raise DomainError("Aceite o aviso de privacidade da vaga.")
    normalized_email = str(body.email).lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user and (not user.active or user.kind != "CANDIDATO"):
        return {
            "message": "Confira seu e-mail para confirmar o interesse e acompanhar a candidatura."
        }
    raw = secrets.token_urlsafe(48)
    row = QuickApplication(
        vacancy_id=vacancy.id,
        notice_id=notice.id,
        name=body.name,
        email=normalized_email,
        phone=body.phone,
        answers=body.answers,
        token_hash=digest(raw),
        expires_at=utcnow() + timedelta(minutes=30),
    )
    db.add(row)
    email(
        db,
        normalized_email,
        "Confirme sua candidatura no Porto Aurora",
        "Confirme seu interesse em até 30 minutos: "
        + smtp.public_url.rstrip("/")
        + "/confirmar#quick="
        + raw,
        "quick:" + digest(raw),
    )
    return {"message": "Confira seu e-mail para confirmar o interesse e acompanhar a candidatura."}


class QuickConfirm(StrictModel):
    token: str = Field(min_length=20, max_length=300)


@router.post("/auth/consume-quick")
def confirm_quick(body: QuickConfirm, db: Db, request: Request, response: Response):
    row = db.scalar(
        select(QuickApplication)
        .where(QuickApplication.token_hash == digest(body.token))
        .with_for_update()
    )
    if not row or row.confirmed_at or row.expires_at <= utcnow():
        raise DomainError("Link inválido ou expirado.", 400)
    user = db.scalar(select(User).where(User.email == row.email))
    if user and (not user.active or user.kind != "CANDIDATO"):
        raise DomainError("Link inválido ou expirado.", 400)
    if not user:
        user = User(email=row.email, name=row.name, kind="CANDIDATO", email_verified=True)
        db.add(user)
        db.flush()
        db.add(Candidate(user_id=user.id, name=row.name, email=row.email, phone=row.phone))
        db.flush()
    user.email_verified = True
    actor = Actor(
        user, set(), "", request.client.host if request.client else "", request.state.request_id
    )
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == user.id))
    if not candidate:
        raise DomainError("Perfil não encontrado.", 409)
    existing = db.scalar(
        select(Application).where(
            Application.vacancy_id == row.vacancy_id, Application.candidate_id == candidate.id
        )
    )
    if not existing:
        apply(
            db,
            actor,
            ApplicationInput(
                vacancy_id=row.vacancy_id,
                notice_id=row.notice_id,
                answers={},
                enrollment=True,
                consent=False,
            ),
        )
    row.confirmed_at = utcnow()
    result = session_response(db, user, request, response)
    return result


class ReferralInput(StrictModel):
    vacancy_id: str
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    comment: str = Field(default="", max_length=3000)


@router.get("/referrals")
def referrals(db: Db, actor: Current):
    actor.require("referral.create")
    return page(
        db,
        select(Referral)
        .where(Referral.referred_by == actor.user.id)
        .order_by(Referral.created_at.desc()),
        1,
        100,
    )


@router.post("/referrals", status_code=201)
def refer(body: ReferralInput, db: Db, actor: Current):
    actor.require("referral.create")
    vacancy = db.get(Vacancy, body.vacancy_id)
    if not vacancy or vacancy.status != "PUBLISHED" or vacancy.confidential:
        raise DomainError("Vaga indisponível para indicação.")
    row = Referral(**body.model_dump(mode="json"), referred_by=actor.user.id)
    row.email = str(body.email).lower()
    db.add(row)
    audit(db, actor, "referral.created", row, vacancy_id=vacancy.id)
    if smtp_runtime(db).enabled:
        email(
            db,
            row.email,
            "Uma oportunidade no Porto Aurora",
            "Você recebeu uma indicação. Conheça a vaga e confirme seu interesse: "
            + smtp_runtime(db).public_url.rstrip("/")
            + "/carreiras/vagas/"
            + vacancy.slug,
            "referral:" + row.id,
        )
    return serialize(row)


@router.post("/referrals/{referral_id}/confirm")
def confirm_referral(referral_id: str, body: ApplicationInput, db: Db, actor: Current):
    row = db.scalar(select(Referral).where(Referral.id == referral_id).with_for_update())
    if not row or row.email != actor.user.email or row.vacancy_id != body.vacancy_id:
        raise DomainError("Indicação não encontrada.", 404)
    application = apply(db, actor, body)
    application.source = "INDICACAO"
    row.candidate_id = application.candidate_id
    row.status = "CONFIRMED"
    audit(db, actor, "referral.confirmed", row, vacancy_id=row.vacancy_id)
    return serialize(application)


class ImportRow(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    phone: str = Field(default="", max_length=30)
    city: str = Field(default="", max_length=120)
    state: str = Field(default="", max_length=2)


@router.post("/imports/candidates/preview", status_code=201)
async def preview_import(db: Db, actor: Current, file: Annotated[UploadFile, File()]):
    actor.require("candidate.import")
    raw = await file.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024 or not (file.filename or "").lower().endswith(".csv"):
        raise DomainError("Envie um CSV de até 2 MB.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError("Salve o CSV em UTF-8.") from exc
    if not decoded.strip():
        raise DomainError("O arquivo está vazio.")
    reader = csv.DictReader(
        io.StringIO(decoded), delimiter=";" if ";" in decoded.splitlines()[0] else ","
    )
    if (
        not reader.fieldnames
        or not {"name", "email"} <= set(reader.fieldnames)
        or set(reader.fieldnames) - set(ImportRow.model_fields)
    ):
        raise DomainError("Use as colunas name, email e, opcionalmente, phone, city, state.")
    valid = []
    errors = []
    seen = set()
    for index, item in enumerate(reader, 2):
        if index > 1001:
            raise DomainError("Cada importação aceita até 1.000 candidatos.")
        try:
            parsed = ImportRow.model_validate(item).model_dump(mode="json")
            parsed["email"] = parsed["email"].lower()
            if parsed["email"] in seen or db.scalar(
                select(User.id).where(User.email == parsed["email"])
            ):
                errors.append({"line": index, "message": "E-mail duplicado ou já cadastrado."})
            else:
                valid.append(parsed)
                seen.add(parsed["email"])
        except ValidationError:
            errors.append(
                {
                    "line": index,
                    "message": "Campos inválidos. Revise nome, e-mail e limites de tamanho.",
                }
            )
    if not valid and not errors:
        raise DomainError("O arquivo não contém registros.")
    row = ImportBatch(
        created_by=actor.user.id,
        sha256=hashlib.sha256(raw).hexdigest(),
        rows={"valid": valid, "errors": errors},
    )
    db.add(row)
    db.flush()
    audit(db, actor, "import.previewed", row, after={"count": len(valid), "errors": len(errors)})
    return {
        "id": row.id,
        "version": row.version,
        "items": valid,
        "errors": errors,
        "count": len(valid),
        "can_confirm": not errors,
    }


@router.post("/imports/candidates/{batch_id}/confirm")
def confirm_import(batch_id: str, db: Db, actor: Current):
    actor.require("candidate.import")
    row = db.scalar(select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update())
    if not row or row.created_by != actor.user.id:
        raise DomainError("Importação não encontrada.", 404)
    if row.status == "IMPORTED":
        return {"count": len(row.rows["valid"]), "message": "Importação já concluída."}
    if row.rows["errors"]:
        raise DomainError("Corrija os erros no arquivo antes de importar.", 409)
    for item in row.rows["valid"]:
        if db.scalar(select(User.id).where(User.email == item["email"])):
            raise DomainError(
                "Um e-mail foi cadastrado após a prévia. Reenvie o arquivo; nenhum registro foi importado.",
                409,
            )
        user = User(email=item["email"], name=item["name"], kind="CANDIDATO")
        db.add(user)
        db.flush()
        db.add(Candidate(user_id=user.id, source="IMPORTACAO", **item))
    row.status = "IMPORTED"
    row.confirmed_at = utcnow()
    audit(db, actor, "import.confirmed", row, after={"count": len(row.rows["valid"])})
    return {
        "count": len(row.rows["valid"]),
        "message": "Todos os registros foram importados. Consentimento permanece pendente.",
    }


@router.get("/referral-vacancies")
def referral_vacancies(db: Db, actor: Current):
    actor.require("referral.create")
    from app.api.public import public_vacancy

    return page(
        db,
        select(Vacancy)
        .where(
            Vacancy.status == "PUBLISHED",
            Vacancy.confidential.is_(False),
            Vacancy.deadline > utcnow(),
        )
        .order_by(Vacancy.title),
        1,
        100,
        public_vacancy,
    )
