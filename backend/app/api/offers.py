from datetime import datetime
from html import escape
from io import BytesIO
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import Field
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import func, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, vacancy_access, vacancy_scope
from app.models import Application, Candidate, ChecklistItem, ConfigRecord, Offer, Vacancy
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.schemas.recruitment import ApprovalInput, StatusInput
from app.services.events import audit, event, notify
from app.services.workflow import decide, submit

router = APIRouter(tags=["Ofertas e pré-admissão"])


class OfferTerms(StrictModel):
    position: str = Field(min_length=2, title="Cargo")
    salary: float = Field(gt=0, le=1000000, allow_inf_nan=False, title="Salário")
    benefits: str = Field(min_length=2, title="Benefícios")
    workload: str = Field(min_length=2, title="Jornada")
    establishment: str = Field(min_length=2, title="Estabelecimento")
    expected_start: str = Field(min_length=8, title="Previsão de início")
    conditions: str = Field(min_length=5, title="Condições")
    checklist_id: str | None = None


class OfferInput(StrictModel):
    application_id: str
    terms: OfferTerms
    expires_at: datetime


@router.get("/offers")
def offers(db: Db, actor: Current):
    query = select(Offer).join(Application, Offer.application_id == Application.id)
    if actor.user.kind == "CANDIDATO" or not {"offer.create", "offer.approve"} & actor.permissions:
        query = query.join(Candidate, Application.candidate_id == Candidate.id).where(
            Candidate.user_id == actor.user.id,
            Offer.status.in_(["SENT", "ACCEPTED", "DECLINED", "EXPIRED"]),
        )
    else:
        actor.require(
            "offer.create" if "offer.approve" not in actor.permissions else "offer.approve"
        )
        query = query.where(
            Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
        )
    return page(db, query.order_by(Offer.created_at.desc()), 1, 100)


@router.post("/offers", status_code=201)
def create_offer(body: OfferInput, db: Db, actor: Current):
    actor.require("offer.create")
    application = application_access(db, actor, body.application_id, "offer.create")
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    if application.status != "SELECTED":
        raise DomainError("Selecione o candidato antes de gerar oferta.", 409)
    if not body.expires_at.tzinfo or body.expires_at <= utcnow():
        raise DomainError("Informe validade futura com fuso horário.")
    live = db.scalar(
        select(Offer.id).where(
            Offer.application_id == application.id,
            Offer.status.in_(["PENDING_APPROVAL", "APPROVED", "SENT", "ACCEPTED"]),
        )
    )
    if live:
        raise DomainError("Já existe uma oferta ativa. Cancele-a antes de criar nova versão.", 409)
    number = (
        db.scalar(select(func.max(Offer.number)).where(Offer.application_id == application.id)) or 0
    ) + 1
    row = Offer(
        application_id=application.id,
        number=number,
        terms=body.terms.model_dump(),
        expires_at=body.expires_at,
        created_by=actor.user.id,
    )
    db.add(row)
    event(db, actor, "offer.created", row, application.vacancy_id)
    return serialize(row)


def offer_access(db, actor, offer_id):
    row = db.get(Offer, offer_id)
    if not row:
        raise DomainError("Oferta não encontrada.", 404)
    application = required(db, Application, row.application_id)
    own = required(db, Candidate, application.candidate_id).user_id == actor.user.id
    if not own:
        vacancy_access(
            db,
            actor,
            application.vacancy_id,
            "offer.approve" if "offer.approve" in actor.permissions else "offer.create",
        )
    if own and row.status not in {"SENT", "ACCEPTED", "DECLINED", "EXPIRED"}:
        raise DomainError("Oferta não encontrada.", 404)
    return row, application, own


@router.post("/offers/{offer_id}/submit")
def submit_offer(offer_id: str, body: StatusInput, db: Db, actor: Current):
    row, application, _ = offer_access(db, actor, offer_id)
    actor.require("offer.create")
    check_version(row, body.version)
    submit(db, actor, row, body.workflow_id or "")
    return serialize(row)


@router.post("/offers/{offer_id}/approve")
def approve_offer(offer_id: str, body: ApprovalInput, db: Db, actor: Current):
    row, application, _ = offer_access(db, actor, offer_id)
    check_version(row, body.version)
    decide(db, actor, row, body.decision, body.comment)
    return serialize(row)


@router.post("/offers/{offer_id}/send")
def send_offer(offer_id: str, db: Db, actor: Current):
    row, application, _ = offer_access(db, actor, offer_id)
    actor.require("offer.create")
    if row.status != "APPROVED" or row.expires_at <= utcnow():
        raise DomainError("A oferta precisa estar aprovada e dentro da validade.", 409)
    row.status = "SENT"
    event(db, actor, "offer.sent", row, application.vacancy_id)
    notify(
        db,
        required(db, Candidate, application.candidate_id).user_id,
        "Sua carta oferta está disponível",
        "Acesse a área de ofertas para conhecer as condições.",
        "OFFER",
        "/candidato/ofertas",
    )
    return serialize(row)


class OfferResponse(StrictModel):
    version: int
    decision: Literal["ACCEPTED", "DECLINED"]
    reason: str = ""


@router.post("/offers/{offer_id}/respond")
def respond(offer_id: str, body: OfferResponse, db: Db, actor: Current):
    db.scalar(select(Offer).where(Offer.id == offer_id).with_for_update())
    row, application, own = offer_access(db, actor, offer_id)
    if not own:
        raise DomainError("Somente o candidato pode responder à oferta.", 403)
    from app.core.config import settings

    if settings().environment == "production" and not actor.user.email_verified:
        raise DomainError("Confirme seu e-mail antes de responder à oferta.", 409)
    if row.status == body.decision:
        return serialize(row)
    check_version(row, body.version)
    if row.status != "SENT" or row.expires_at <= utcnow():
        raise DomainError("A oferta não está disponível para resposta.", 409)
    row.status = body.decision
    row.responded_at = utcnow()
    row.response_ip = actor.ip
    row.response_reason = body.reason
    if row.status == "ACCEPTED":
        application.status = "PRE_ADMISSION"
        checklist = (
            db.get(ConfigRecord, row.terms.get("checklist_id"))
            if row.terms.get("checklist_id")
            else None
        )
        if checklist and checklist.kind == "checklists":
            for title in checklist.data["items"]:
                db.add(ChecklistItem(application_id=application.id, title=title))
    event(
        db,
        actor,
        "offer.accepted" if row.status == "ACCEPTED" else "offer.declined",
        row,
        application.vacancy_id,
    )
    return serialize(row)


@router.get("/offers/{offer_id}/pdf")
def pdf(offer_id: str, db: Db, actor: Current):
    row, application, _ = offer_access(db, actor, offer_id)
    candidate = required(db, Candidate, application.candidate_id)
    vacancy = required(db, Vacancy, application.vacancy_id)
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=(21 * cm, 29.7 * cm),
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#b51f32")
    styles["BodyText"].leading = 16
    story = [
        Paragraph("Porto Aurora Talentos", styles["Title"]),
        Paragraph("Carta oferta", styles["Heading1"]),
        Paragraph("Destinatário: " + escape(candidate.name), styles["BodyText"]),
        Paragraph("Vaga: " + escape(vacancy.title) + " · " + vacancy.code, styles["BodyText"]),
        Spacer(1, 0.6 * cm),
    ]
    labels = {
        "position": "Cargo",
        "salary": "Remuneração mensal (BRL)",
        "benefits": "Benefícios",
        "workload": "Jornada",
        "establishment": "Estabelecimento",
        "expected_start": "Previsão de início",
        "conditions": "Condições",
    }
    for key, label in labels.items():
        value = (
            f"R$ {row.terms[key]:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if key == "salary"
            else str(row.terms.get(key, ""))
        )
        story.extend(
            [
                Paragraph(label, styles["Heading3"]),
                Paragraph(escape(value).replace("\n", "<br/>"), styles["BodyText"]),
            ]
        )
    story.extend(
        [
            Spacer(1, 0.7 * cm),
            Paragraph(
                f"Versão {row.number} · Validade: {row.expires_at.strftime('%d/%m/%Y %H:%M')} UTC",
                styles["BodyText"],
            ),
            Paragraph(
                "O aceite na plataforma registra a manifestação do candidato. Este registro não equivale a assinatura digital certificada.",
                styles["BodyText"],
            ),
        ]
    )
    document.build(story)
    audit(db, actor, "offer.downloaded", row, vacancy_id=application.vacancy_id)
    return Response(
        output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="carta-oferta.pdf"'},
    )


@router.get("/applications/{application_id}/checklist")
def checklist(application_id: str, db: Db, actor: Current):
    application_access(db, actor, application_id)
    return page(
        db,
        select(ChecklistItem)
        .where(ChecklistItem.application_id == application_id)
        .order_by(ChecklistItem.created_at),
        1,
        100,
    )


class ChecklistReview(StrictModel):
    version: int
    status: Literal["APPROVED", "REJECTED", "PENDING"]
    comment: str = ""


@router.put("/checklist/{item_id}")
def review_checklist(item_id: str, body: ChecklistReview, db: Db, actor: Current):
    actor.require("document.review")
    row = db.get(ChecklistItem, item_id)
    if not row:
        raise DomainError("Item não encontrado.", 404)
    application = application_access(db, actor, row.application_id, "document.review")
    check_version(row, body.version)
    if body.status == "REJECTED" and len(body.comment.strip()) < 5:
        raise DomainError("Rejeição exige comentário.")
    row.status, row.comment, row.reviewed_by = body.status, body.comment, actor.user.id
    event(db, actor, "checklist.reviewed", row, application.vacancy_id)
    return serialize(row)


class CancelOffer(StrictModel):
    version: int
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/offers/{offer_id}/cancel")
def cancel_offer(offer_id: str, body: CancelOffer, db: Db, actor: Current):
    row, application, own = offer_access(db, actor, offer_id)
    actor.require("offer.create")
    check_version(row, body.version)
    if row.status in {"ACCEPTED", "DECLINED", "EXPIRED", "CANCELED"}:
        raise DomainError("Esta oferta não pode ser cancelada.", 409)
    row.status = "CANCELED"
    audit(
        db,
        actor,
        "offer.canceled",
        row,
        after={"reason": body.reason},
        vacancy_id=application.vacancy_id,
    )
    notify(
        db,
        required(db, Candidate, application.candidate_id).user_id,
        "Oferta cancelada",
        "O RH registrou uma atualização na oferta.",
        "OFFER",
    )
    return serialize(row)
