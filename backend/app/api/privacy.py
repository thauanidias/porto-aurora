import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import EmailStr, Field, field_validator, model_validator
from sqlalchemy import select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, bearer, get_actor
from app.core.security import decrypt, encrypt
from app.models import (
    Application,
    AuditLog,
    Candidate,
    CandidateFeedback,
    ConfigRecord,
    Consent,
    ConsentReceipt,
    DataSubjectRequest,
    SurveyResponse,
)
from app.repositories.common import check_version, page, serialize
from app.schemas.auth import StrictModel
from app.schemas.internal_registration import InternalDeclaration
from app.services.events import audit
from app.services.privacy import anonymize
from app.services.receipt_document import receipt_docx

router = APIRouter(tags=["Privacidade"])


class ReceiptInput(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    context: Literal["CADASTRO", "CANDIDATURA"]
    accepted: Literal[True]
    signature_image: str = Field(default="", max_length=250000)
    read_to_end: bool = False

    @field_validator('signature_image')
    @classmethod
    def valid_signature(cls, value):
        return InternalDeclaration.valid_signature(value) if value else ""

    @model_validator(mode="after")
    def confirm_acceptance(self):
        if not self.signature_image and not self.read_to_end:
            raise ValueError("Confirme a leitura integral e o aceite do termo.")
        return self


@router.post("/public/consent-receipts", status_code=201)
def accept_document(
    body: ReceiptInput,
    db: Db,
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    actor = get_actor(request, db, credentials) if credentials else None
    if actor:
        from app.services.candidate_journey import require_candidate_section
        require_candidate_section(db, actor, "consent")
    paragraphs = json.loads(
        (Path(__file__).parents[1] / "consent-term.json").read_text(encoding="utf-8-sig")
    )
    now = utcnow()
    row = ConsentReceipt(
        protocol="Porto Aurora-ACEITE-" + now.strftime("%Y%m%d") + "-" + uuid4().hex.upper(),
        name=actor.user.name if actor else body.name.strip(),
        email=actor.user.email if actor else str(body.email).lower(),
        user_id=actor.user.id if actor else None,
        ip=request.client.host if request.client else "",
        context=body.context,
        document_code="FORM-PPO-RH-002.09",
        document_sha256=hashlib.sha256("\n".join(paragraphs).encode()).hexdigest(),
        document_snapshot={
            "text_revision": "2026-10-29",
            "paragraphs": paragraphs,
            "identity": "AUTHENTICATED" if actor else "DECLARED",
            "signature_image": body.signature_image,
            "signature_sha256": hashlib.sha256(body.signature_image.encode()).hexdigest(),
        },
        created_at=now,
    )
    if not body.signature_image:
        from app.services.electronic_acceptance import acceptance_signature
        record = {"method": "CLICK_ACCEPTANCE", "protocol": row.protocol, "name": row.name, "email": row.email,
                  "user_id": row.user_id, "accepted_at": now.isoformat(), "ip": row.ip,
                  "document_code": row.document_code, "document_sha256": row.document_sha256,
                  "read_to_end": body.read_to_end, "accepted": True,
                  "user_agent": request.headers.get("user-agent", "")[:512]}
        row.document_snapshot = {**row.document_snapshot, "signature_method": "CLICK_ACCEPTANCE",
                                 "acceptance_record": record, "electronic_signature_sha256": acceptance_signature(record)}
    db.add(row)
    db.flush()
    if actor and actor.user.kind == "CANDIDATO" and body.context == "CADASTRO":
        candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
        if candidate:
            db.add(Consent(
                candidate_id=candidate.id,
                notice_id=None,
                notice_version=9,
                notice_snapshot={
                    "text": "\n".join(paragraphs),
                    "document_code": row.document_code,
                    "receipt_protocol": row.protocol,
                    "receipt_id": row.id,
                },
                purpose="RECRUITMENT",
                granted=True,
                ip=row.ip,
            ))
    db.add(
        AuditLog(
            user_id=row.user_id,
            action="document.accepted",
            entity="consent_receipts",
            entity_id=row.id,
            before={},
            after={"protocol": row.protocol},
            ip=row.ip,
            request_id=request.state.request_id,
        )
    )
    result = serialize(row, {"document_snapshot"})
    if row.document_snapshot.get("electronic_signature_sha256"):
        result["signature_method"] = "CLICK_ACCEPTANCE"
        result["electronic_signature_sha256"] = row.document_snapshot["electronic_signature_sha256"]
    token = encrypt(json.dumps({"receipt_id": row.id, "expires": (now + timedelta(hours=1)).timestamp()}))
    result["download_url"] = f"/api/v1/public/consent-receipts/{row.id}/document?token={token}"
    return result


@router.get("/public/consent-receipts/{receipt_id}/document")
def download_just_signed_document(receipt_id: str, token: str, db: Db):
    try:
        proof = json.loads(decrypt(token))
        if proof["receipt_id"] != receipt_id or proof["expires"] <= utcnow().timestamp():
            raise ValueError()
    except Exception as exc:
        raise DomainError("Link de download inválido ou expirado.", 403) from exc
    row = db.get(ConsentReceipt, receipt_id)
    if not row:
        raise DomainError("Comprovante não encontrado.", 404)
    return Response(receipt_docx(row), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": 'attachment; filename="termo-assinado-e-comprovante.docx"', "Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer"})


@router.get("/privacy/consent-receipts")
def receipts(db: Db, actor: Current, page_number: int = 1):
    actor.require("privacy.manage")
    return page(
        db,
        select(ConsentReceipt).order_by(ConsentReceipt.created_at.desc()),
        max(1, page_number),
        25,
        serializer=lambda row: serialize(row, {"document_snapshot"}),
    )


@router.get("/privacy/consent-receipts/{receipt_id}")
def receipt_document(receipt_id: str, db: Db, actor: Current):
    row = accessible_receipt(receipt_id, db, actor)
    audit(db, actor, "consent_receipt.viewed", row)
    return serialize(row)


@router.get("/privacy/consent-receipts/{receipt_id}/document")
def download_receipt_document(receipt_id: str, db: Db, actor: Current):
    row = accessible_receipt(receipt_id, db, actor)
    try:
        content = receipt_docx(row)
    except ValueError as exc:
        raise DomainError(str(exc), 409) from exc
    audit(db, actor, "consent_receipt.downloaded", row)
    filename = f"{row.document_code}-{row.protocol}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


def accessible_receipt(receipt_id: str, db: Db, actor: Current):
    query = select(ConsentReceipt).where(ConsentReceipt.id == receipt_id)
    if "privacy.manage" not in actor.permissions:
        if actor.user.kind != "CANDIDATO":
            actor.require("candidate.view")
            receipt = db.scalar(query)
            candidate = db.scalar(select(Candidate).where(Candidate.user_id == receipt.user_id)) if receipt else None
            if receipt and candidate is None:
                candidate = db.scalar(select(Candidate).join(Consent, Consent.candidate_id == Candidate.id).where(
                    Consent.notice_snapshot["receipt_id"].astext == receipt.id))
            if not candidate:
                raise DomainError("Você não tem acesso a este comprovante.", 403)
            from app.core.permissions import candidate_access
            candidate_access(db, actor, candidate.id)
            from app.services.recruitment import candidate_view
            if candidate_view(db, actor, candidate).get("blind"):
                raise DomainError("Comprovante indisponível durante a seleção sem identidade.", 403)
        else:
            query = query.where(own_receipts(actor))
    row = db.scalar(query)
    if not row:
        raise DomainError("Comprovante não encontrado.", 404)
    return row


def own_receipts(actor):
    linked = (
        select(Consent.notice_snapshot["receipt_id"].astext)
        .join(Candidate, Candidate.id == Consent.candidate_id)
        .where(Candidate.user_id == actor.user.id)
    )
    return (ConsentReceipt.user_id == actor.user.id) | ConsentReceipt.id.in_(linked)


@router.get("/privacy/my-consent-receipts")
def my_receipts(db: Db, actor: Current, page_number: int = 1):
    return page(
        db,
        select(ConsentReceipt)
        .where(own_receipts(actor))
        .order_by(ConsentReceipt.created_at.desc()),
        max(1, page_number),
        25,
        serializer=lambda row: serialize(row, {"document_snapshot"}),
    )


def own_candidate(db, actor):
    row = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    if not row:
        raise DomainError("Perfil não encontrado.", 404)
    return row


@router.get("/privacy/consents")
def consents(db: Db, actor: Current, page_number: int = 1):
    candidate = own_candidate(db, actor)
    return page(
        db,
        select(Consent)
        .where(Consent.candidate_id == candidate.id)
        .order_by(Consent.created_at.desc()),
        max(1, page_number),
        25,
    )


class ConsentInput(StrictModel):
    notice_id: str
    purpose: Literal["TALENT", "RECRUITMENT"]
    granted: bool


@router.post("/privacy/consents", status_code=201)
def consent(body: ConsentInput, db: Db, actor: Current):
    candidate = own_candidate(db, actor)
    notice = db.get(ConfigRecord, body.notice_id)
    if not notice or notice.kind != "privacy-notices" or not notice.active:
        raise DomainError("Aviso inválido.")
    row = Consent(
        candidate_id=candidate.id,
        notice_id=notice.id,
        notice_version=notice.version,
        notice_snapshot=notice.data,
        purpose=body.purpose,
        granted=body.granted,
        ip=actor.ip,
    )
    db.add(row)
    if body.purpose == "TALENT":
        candidate.talent_consent_until = (
            utcnow() + timedelta(days=round(notice.data["talent_months"] * 365.2425 / 12))
            if body.granted
            else None
        )
    audit(
        db, actor, "consent.changed", row, after={"purpose": body.purpose, "granted": body.granted}
    )
    return serialize(row)


class PrivacyRequest(StrictModel):
    kind: Literal["COPY", "CORRECTION", "DELETION", "CLOSE_ACCOUNT"]
    detail: str = Field(min_length=5, max_length=3000)


@router.get("/privacy/requests")
def requests(db: Db, actor: Current):
    query = select(DataSubjectRequest)
    if "privacy.manage" not in actor.permissions:
        query = query.where(DataSubjectRequest.candidate_id == own_candidate(db, actor).id)
    return page(db, query.order_by(DataSubjectRequest.created_at.desc()), 1, 100)


@router.post("/privacy/requests", status_code=201)
def request(body: PrivacyRequest, db: Db, actor: Current):
    candidate = own_candidate(db, actor)
    row = DataSubjectRequest(candidate_id=candidate.id, **body.model_dump())
    db.add(row)
    audit(db, actor, "privacy.requested", row)
    return serialize(row)


class Handle(StrictModel):
    version: int
    status: Literal["IN_REVIEW", "FULFILLED", "DENIED"]
    response: str = Field(min_length=10)
    anonymize_data: bool = False


@router.put("/privacy/requests/{request_id}")
def handle(request_id: str, body: Handle, db: Db, actor: Current):
    actor.require("privacy.manage")
    row = db.get(DataSubjectRequest, request_id)
    if not row:
        raise DomainError("Solicitação não encontrada.", 404)
    check_version(row, body.version)
    if row.status in {"FULFILLED", "DENIED"}:
        raise DomainError("Solicitação já concluída.", 409)
    if body.anonymize_data:
        if row.kind not in {"DELETION", "CLOSE_ACCOUNT"} or body.status != "FULFILLED":
            raise DomainError("A anonimização exige solicitação de exclusão concluída.")
        candidate = db.get(Candidate, row.candidate_id)
        anonymize(db, actor, candidate, body.response)
    row.status, row.response, row.handled_by = body.status, body.response, actor.user.id
    audit(db, actor, "privacy.handled", row, after={"status": row.status, "response": row.response})
    return serialize(row)


@router.get("/privacy/export")
def export_data(db: Db, actor: Current):
    from app.core.security import decrypt
    from app.models import ProcessForm
    candidate = own_candidate(db, actor)
    applications = [
        serialize(row, {"profile_snapshot", "closure_reason"})
        for row in db.scalars(select(Application).where(Application.candidate_id == candidate.id))
    ]
    result = {
        "profile": serialize(candidate),
        "applications": applications,
        "process_forms": [{"application_id": form.application_id, "submitted_at": form.submitted_at,
            "data": json.loads(decrypt(form.encrypted_data)) if form.encrypted_data else {}}
            for form in db.scalars(select(ProcessForm).where(ProcessForm.application_id.in_(
                select(Application.id).where(Application.candidate_id == candidate.id))))],
        "feedback": [serialize(row) for row in db.scalars(select(CandidateFeedback).where(CandidateFeedback.candidate_id == candidate.id))],
        "consents": [
            serialize(row)
            for row in db.scalars(select(Consent).where(Consent.candidate_id == candidate.id))
        ],
    }
    audit(db, actor, "privacy.exported", candidate, after={"count": len(applications)})
    return result


@router.get("/privacy/surveys")
def surveys(db: Db, actor: Current):
    return page(
        db,
        select(ConfigRecord)
        .where(ConfigRecord.kind == "surveys", ConfigRecord.active.is_(True))
        .order_by(ConfigRecord.created_at.desc()),
        1,
        100,
    )


class SurveyInput(StrictModel):
    answers: dict


@router.post("/privacy/surveys/{survey_id}/respond")
def survey_response(survey_id: str, body: SurveyInput, db: Db, actor: Current):
    candidate = own_candidate(db, actor)
    survey = db.get(ConfigRecord, survey_id)
    if not survey or survey.kind != "surveys" or not survey.active:
        raise DomainError("Pesquisa inválida.")
    if survey.data["nps"] and (
        not isinstance(body.answers.get("nps"), int) or not 0 <= body.answers["nps"] <= 10
    ):
        raise DomainError("Informe nota entre 0 e 10.")
    row = SurveyResponse(candidate_id=candidate.id, survey_id=survey.id, answers=body.answers)
    db.add(row)
    audit(db, actor, "survey.responded", row)
    return serialize(row)


class CandidateFeedbackInput(StrictModel):
    application_id: str = Field(min_length=1, max_length=36)
    message: str = Field(min_length=5, max_length=5000)
    rating: int | None = Field(default=None, ge=1, le=5)

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.post("/candidate-feedback", status_code=201)
def send_candidate_feedback(body: CandidateFeedbackInput, db: Db, actor: Current):
    from app.models import CandidateFeedback
    candidate = own_candidate(db, actor)
    application = db.get(Application, body.application_id)
    if not application or application.candidate_id != candidate.id:
        raise DomainError("Candidatura não encontrada.", 404)
    row = CandidateFeedback(candidate_id=candidate.id, application_id=application.id,
                            message=body.message, rating=body.rating)
    db.add(row)
    db.flush()
    audit(db, actor, "candidate.feedback_submitted", row, vacancy_id=application.vacancy_id)
    return {"id": row.id, "created_at": row.created_at, "message": "Feedback enviado ao RH."}


@router.get("/candidate-feedback")
def list_candidate_feedback(db: Db, actor: Current, page_number: int = 1):
    from app.models import CandidateFeedback, Vacancy
    from app.core.permissions import vacancy_scope
    from app.services.recruitment import candidate_view
    actor.require("candidate.evaluate")
    if page_number < 1:
        raise DomainError("Página inválida.")
    query = select(CandidateFeedback).join(Application, Application.id == CandidateFeedback.application_id).where(
        Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))))
    def feedback_view(row):
        application = db.get(Application, row.application_id)
        candidate = db.get(Candidate, row.candidate_id)
        vacancy = db.get(Vacancy, application.vacancy_id)
        identity = candidate_view(db, actor, candidate, application)
        return {"id": row.id, "application_id": application.id, "candidate_name": identity["name"],
                "vacancy_title": vacancy.title, "message": row.message if not identity.get("blind") else None,
                "rating": row.rating, "created_at": row.created_at, "restricted": bool(identity.get("blind"))}
    return page(db, query.order_by(CandidateFeedback.created_at.desc(), CandidateFeedback.id), page_number, 25, serializer=feedback_view)
