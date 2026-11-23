import json
import secrets
from datetime import timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import EmailStr, Field, field_validator
from sqlalchemy import select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import (
    Actor,
    Current,
    Db,
    application_access,
    candidate_access,
    vacancy_access,
)
from app.core.security import decrypt, digest, encrypt
from app.models import (
    Application,
    Candidate,
    ConfigRecord,
    Consent,
    Document,
    PipelineStage,
    ProcessForm,
    Role,
    StageReview,
    User,
    UserRole,
    Vacancy,
)
from app.repositories.common import check_version, required, serialize
from app.schemas.auth import StrictModel
from app.schemas.candidates import CandidateInput, professional_facts
from app.services.candidate_journey import application_permissions
from app.services.events import audit, email, event, notify
from app.services.smtp_config import smtp_runtime

router = APIRouter(tags=["Seleção de currículo e ficha por candidatura"])


class RHCandidateInput(CandidateInput):
    email: EmailStr
    phone: str = Field(min_length=10, max_length=30, pattern=r"^[0-9+() .-]+$")
    source: Literal["PORTAL", "WHATSAPP", "INSTAGRAM", "LINKEDIN", "INDICACAO", "OUTRO"] = "OUTRO"


@router.get("/forms/rh-candidate")
def rh_candidate_schema(actor: Current):
    actor.require("candidate.import")
    return RHCandidateInput.model_json_schema()


@router.post("/candidates", status_code=201)
def create_rh_candidate(body: RHCandidateInput, db: Db, actor: Current):
    import re
    actor.require("candidate.import")
    address = str(body.email).lower()
    phone = re.sub(r"[^0-9+]", "", body.phone)
    if len(body.name.strip()) < 3 or not re.fullmatch(r"\+?[0-9]{10,15}", phone):
        raise DomainError("Informe nome completo e telefone válido com DDD.")
    if db.scalar(select(User.id).where(User.email == address)) or db.scalar(select(Candidate.id).where(Candidate.email == address)):
        raise DomainError("Já existe um cadastro com este e-mail. Consulte o perfil existente.", 409)
    if any(certificate.document_id for certificate in body.profile.certifications):
        raise DomainError("Cadastre o perfil antes de vincular certificados.")
    user = User(name=body.name, email=address, kind="CANDIDATO", password_hash=None, email_verified=False)
    db.add(user)
    db.flush()
    role = db.scalar(select(Role).where(Role.name == "CANDIDATO"))
    if role:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    data = body.model_dump(exclude={"version", "email", "profile"})
    data["phone"] = phone
    profile = body.profile.model_dump(mode="json") | {"facts": professional_facts(body.profile)}
    candidate = Candidate(**data, email=address, user_id=user.id, profile=profile)
    db.add(candidate)
    # No consent, verification, password or enrollment is invented on the person's behalf.
    event(db, actor, "candidate.registered_by_rh", candidate)
    return serialize(candidate)


@router.put("/candidates/{candidate_id}/rh-profile")
def edit_rh_candidate(candidate_id: str, body: CandidateInput, db: Db, actor: Current):
    import re

    from app.services.recruitment import candidate_view
    actor.require("candidate.import")
    candidate = candidate_access(db, actor, candidate_id, "candidate.import")
    if candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("A edição de identidade está bloqueada durante o recrutamento cego.", 403)
    if body.version is None:
        raise DomainError("Atualize o perfil antes de salvar.", 409)
    check_version(candidate, body.version)
    phone = re.sub(r"[^0-9+]", "", body.phone)
    if phone and not re.fullmatch(r"\+?[0-9]{10,15}", phone):
        raise DomainError("Informe telefone válido com DDD.")
    for certificate in body.profile.certifications:
        if certificate.document_id:
            document = db.get(Document, str(certificate.document_id))
            if not document or document.candidate_id != candidate.id or document.type_name != "CERTIFICADO":
                raise DomainError("Certificado inválido para este candidato.")
    for key, value in body.model_dump(exclude={"version", "profile"}).items():
        setattr(candidate, key, value)
    candidate.phone = phone
    candidate.profile = body.profile.model_dump(mode="json") | {"facts": professional_facts(body.profile)}
    user = required(db, User, candidate.user_id)
    user.name = body.name
    event(db, actor, "candidate.profile_updated_by_rh", candidate)
    return serialize(candidate)


class ReviewInput(StrictModel):
    version: int = Field(ge=1)
    status: Literal["APPROVED", "REJECTED", "PENDING"]
    reason: str = Field(min_length=5, max_length=4000)


class WorkflowInput(StrictModel):
    version: int = Field(ge=1)


@router.post("/vacancies/{vacancy_id}/structured-workflow")
def enable_workflow(vacancy_id: str, body: WorkflowInput, db: Db, actor: Current):
    from app.services.process_workflow import configure_workflow
    vacancy = vacancy_access(db, actor, vacancy_id, "vacancy.edit")
    db.scalar(select(Vacancy).where(Vacancy.id == vacancy.id).with_for_update())
    check_version(vacancy, body.version)
    if vacancy.details.get("structured_workflow"):
        return serialize(vacancy)
    if vacancy.status in {"CLOSED", "CANCELED", "ARCHIVED"}:
        raise DomainError("Reabra a vaga antes de ativar o fluxo completo.", 409)
    configure_workflow(db, vacancy)
    event(db, actor, "vacancy.structured_workflow_enabled", vacancy, vacancy.id)
    return serialize(vacancy)


class IntakeInput(WorkflowInput):
    source: Literal["PORTAL", "WHATSAPP", "INSTAGRAM", "LINKEDIN", "INDICACAO", "BANCO_TALENTOS", "IMPORTACAO", "OUTRO"]


@router.put("/applications/{application_id}/source")
def application_source(application_id: str, body: IntakeInput, db: Db, actor: Current):
    application = application_access(db, actor, application_id, "candidate.move")
    check_version(application, body.version)
    application.source = body.source
    event(db, actor, "application.source_updated", application, application.vacancy_id)
    return serialize(application)


@router.get("/applications/{application_id}/stage-reviews")
def reviews(application_id: str, db: Db, actor: Current):
    application = application_access(db, actor, application_id, "candidate.view")
    actor.require("candidate.view")
    return {"items": [serialize(row) for row in db.scalars(select(StageReview).where(
        StageReview.application_id == application.id).order_by(StageReview.created_at.desc(), StageReview.id))]}


@router.post("/applications/{application_id}/stage-reviews", status_code=201)
def review(application_id: str, body: ReviewInput, db: Db, actor: Current):
    application = application_access(db, actor, application_id, "candidate.move")
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    check_version(application, body.version)
    if application.status not in {"ACTIVE", "RESERVE"}:
        raise DomainError("A candidatura não está em análise.", 409)
    form_was_available = application_permissions(db, application)["permissions"]["selection_registration"]
    row = StageReview(application_id=application.id, stage_id=application.stage_id,
                      status=body.status, reason=body.reason.strip(), reviewed_by=actor.user.id)
    if len(row.reason) < 5:
        raise DomainError("Registre o parecer e a justificativa da análise.")
    db.add(row)
    db.flush()
    if body.status == "APPROVED" and not form_was_available and application_permissions(db, application)["permissions"]["selection_registration"] and application.recruitment_type != "INTERNAL":
        candidate = db.get(Candidate, application.candidate_id)
        vacancy = db.get(Vacancy, application.vacancy_id)
        if candidate and candidate.user_id:
            notify(db, candidate.user_id, "Triagem aprovada: preencha sua ficha externa",
                   f"Olá, {candidate.name}!\n\nVocê foi aprovado(a) na triagem curricular para a vaga de {vacancy.title}. "
                   "Sua ficha de inscrição para seleção externa já está disponível.\n\n"
                   "Acesse a área do candidato, confira seus dados e preencha as informações solicitadas. "
                   "Você pode salvar um rascunho e continuar depois. Ao terminar, revise, assine e confirme a ficha para dar continuidade ao processo seletivo.\n\n"
                   "O Porto Aurora agradece seu interesse em fazer parte da nossa equipe!",
                   "APPLICATION", "/candidato/perfil#ficha-externa")
    # Review and movement are distinct decisions. A review never advances the person.
    application.updated_at = utcnow()
    event(db, actor, "application.stage_reviewed", row, application.vacancy_id)
    return serialize(row)


class ScreeningApproval(StrictModel):
    version: int = Field(ge=1)
    reason: str = Field(min_length=5, max_length=4000)


@router.post("/applications/{application_id}/approve-screening")
def approve_screening(application_id: str, body: ScreeningApproval, db: Db, actor: Current):
    from app.api.applications import application_view
    from app.services.candidate_journey import stage_phase
    from app.services.recruitment import move

    application_access(db, actor, application_id, "candidate.move")
    application = db.scalar(select(Application).where(Application.id == application_id)
                            .with_for_update().execution_options(populate_existing=True))
    check_version(application, body.version)
    current = required(db, PipelineStage, application.stage_id)
    if stage_phase(db, current) != "SELECTION":
        raise DomainError("Esta candidatura não está na triagem de currículos. Atualize a lista.", 409)
    target = db.scalar(select(PipelineStage).where(PipelineStage.vacancy_id == application.vacancy_id,
                       PipelineStage.position > current.position).order_by(PipelineStage.position).limit(1))
    if not target:
        raise DomainError("Configure a próxima etapa da vaga antes de aprovar a triagem.", 409)
    # The review, advance, history and notifications share one transaction.
    review(application_id, ReviewInput(version=application.version, status="APPROVED", reason=body.reason), db, actor)
    move(db, actor, application, target.id, body.reason)
    db.flush()
    return application_view(db, actor, application)


class ProcessRegistration(StrictModel):
    name: str = Field(min_length=3, max_length=180, title="Nome completo")
    email: EmailStr = Field(title="E-mail de contato")
    phone: str = Field(min_length=10, max_length=30, pattern=r"^[0-9+() .-]+$", title="Telefone com DDD")
    desired_position: str = Field(min_length=2, max_length=180, title="Cargo pretendido")
    education: str = Field(min_length=3, max_length=2000, title="Escolaridade e formação")
    experience: str = Field(min_length=3, max_length=4000, title="Experiência profissional (ou informe primeiro emprego)")
    notes: str = Field(default="", max_length=4000, title="Observações profissionais")

    @field_validator("name", "phone", "desired_position", "education", "experience", "notes", mode="before")
    @classmethod
    def strip_fields(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        import re
        normalized = re.sub(r"[^0-9+]", "", value)
        if not re.fullmatch(r"\+?[0-9]{10,15}", normalized):
            raise ValueError("Informe telefone com DDD.")
        return normalized


class IssueForm(StrictModel):
    version: int = Field(ge=1)
    send_email: bool = False


class TokenInput(StrictModel):
    token: str = Field(min_length=40, max_length=200)


class FormAnswers(TokenInput):
    registration: ProcessRegistration | None = None
    answers: dict = Field(default_factory=dict)
    consent: bool
    submit: bool = True


def form_view(db, application, actor):
    row = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application.id))
    result: dict[str, Any] = {"status": "NOT_SENT", "sent_at": None, "submitted_at": None, "registration": None, "answers": {}}
    if row:
        result |= {key: serialize(row)[key] for key in ("status", "sent_at", "submitted_at", "expires_at", "version")}
        result["questions"] = row.questions
        from app.services.recruitment import candidate_view
        candidate = required(db, Candidate, application.candidate_id)
        if {"candidate.registration.view", "candidate.sensitive.view"} & actor.permissions and not candidate_view(db, actor, candidate, application).get("blind"):
            result |= json.loads(decrypt(row.encrypted_data)) if row.encrypted_data else {}
        else:
            result["restricted"] = True
    return result


@router.get("/applications/{application_id}/process-form")
def get_form(application_id: str, db: Db, actor: Current):
    actor.require("candidate.view")
    application = application_access(db, actor, application_id, "candidate.view")
    audit(db, actor, "application.process_form_accessed", application, vacancy_id=application.vacancy_id)
    return form_view(db, application, actor)


@router.post("/applications/{application_id}/process-form")
def issue_form(application_id: str, body: IssueForm, db: Db, actor: Current):
    application = application_access(db, actor, application_id, "candidate.move")
    vacancy = vacancy_access(db, actor, application.vacancy_id, "candidate.move")
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    check_version(application, body.version)
    if not application_permissions(db, application)["permissions"]["process_form"]:
        raise DomainError("Avance para Perguntas e ficha externa antes de disponibilizar o link.", 409)
    return issue_process_form(db, actor, application, vacancy, body.send_email)


@router.post("/applications/{application_id}/my-process-form")
def open_my_process_form(application_id: str, db: Db, actor: Current):
    application = required(db, Application, application_id)
    candidate = required(db, Candidate, application.candidate_id)
    if candidate.user_id != actor.user.id:
        raise DomainError("Candidatura não encontrada.", 404)
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    if not application_permissions(db, application)["permissions"]["process_form"]:
        raise DomainError("Aguarde a liberação desta atividade pelo RH.", 409)
    vacancy = required(db, Vacancy, application.vacancy_id)
    if vacancy.status not in {"PUBLISHED", "PAUSED"} or candidate.anonymized_at or candidate.merged_into_id:
        raise DomainError("Esta ficha não está disponível.", 409)
    return issue_process_form(db, actor, application, vacancy, False)


def issue_process_form(db, actor, application, vacancy, send_email):
    config = smtp_runtime(db)
    if send_email:
        actor.require("message.send")
        if not config.enabled:
            raise DomainError("Habilite o envio de e-mails ou gere o link para copiar.", 409)
    row = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application.id))
    if row and row.submitted_at:
        raise DomainError("Esta ficha já foi preenchida. Consulte as respostas.", 409)
    raw = secrets.token_urlsafe(48)
    if not row:
        row = ProcessForm(application_id=application.id, created_by=actor.user.id,
            questions=vacancy.details.get("questions", []), encrypted_data="")
        db.add(row)
    row.token_hash = digest(raw)
    row.expires_at = utcnow() + timedelta(days=7)
    row.sent_at = utcnow()
    row.status = "SENT"
    link = config.public_url.rstrip("/") + "/ficha-selecao#token=" + raw
    if send_email:
        candidate = required(db, Candidate, application.candidate_id)
        email(db, candidate.email, "Ficha de seleção Porto Aurora",
              "Preencha a ficha da oportunidade " + vacancy.title + ":\n\n" + link,
              "process-form:" + digest(raw))
    event(db, actor, "application.process_form_issued", row, vacancy.id)
    return form_view(db, application, actor) | {"link": link, "email_queued": send_email}


def public_form(db, token):
    row = db.scalar(select(ProcessForm).where(ProcessForm.token_hash == digest(token)).with_for_update())
    if not row or row.expires_at <= utcnow() or row.submitted_at:
        raise DomainError("Link inválido, expirado ou já utilizado.", 404)
    application = required(db, Application, row.application_id)
    candidate = required(db, Candidate, application.candidate_id)
    vacancy = required(db, Vacancy, application.vacancy_id)
    user = required(db, User, candidate.user_id)
    if (candidate.anonymized_at or candidate.merged_into_id
            or not user.active
            or vacancy.status not in {"PUBLISHED", "PAUSED"}
            or not application_permissions(db, application)["permissions"]["process_form"]):
        raise DomainError("Esta ficha não está disponível para preenchimento.", 409)
    notice = db.get(ConfigRecord, vacancy.details.get("notice_id", ""))
    if not notice or not notice.active or notice.kind != "privacy-notices":
        raise DomainError("Aviso de privacidade indisponível. Contate o RH.", 409)
    return row, application, candidate, vacancy, notice


@router.post("/public/process-forms/lookup")
def lookup_form(body: TokenInput, db: Db):
    row, _, _, vacancy, notice = public_form(db, body.token)
    # The link never discloses the candidate's identity, saved personal data or other applications.
    return {"vacancy_title": vacancy.title, "questions": row.questions,
            "schema": ProcessRegistration.model_json_schema(), "status": row.status,
            "notice": notice.data.get("text", ""), "expires_at": row.expires_at}


@router.post("/public/process-forms/submit")
def submit_form(body: FormAnswers, db: Db, request: Request):
    from app.api.applications import validate_question_answers
    row, application, candidate, vacancy, notice = public_form(db, body.token)
    if not body.consent:
        raise DomainError("Leia e aceite o aviso de privacidade para enviar a ficha.")
    if body.submit:
        validate_question_answers(row.questions, body.answers)
    elif len(json.dumps(body.answers)) > 100000:
        raise DomainError("As respostas excedem o tamanho permitido.")
    stored = json.loads(decrypt(row.encrypted_data)) if row.encrypted_data else {}
    if body.registration is not None:
        stored["registration"] = body.registration.model_dump(mode="json")
    stored["answers"] = body.answers
    row.encrypted_data = encrypt(json.dumps(stored, ensure_ascii=False))
    row.status = "COMPLETED" if body.submit else "PENDING"
    user = required(db, User, candidate.user_id)
    actor = Actor(user, set(), "", request.client.host if request.client else "", request.state.request_id)
    if body.submit:
        row.submitted_at = utcnow()
        application.answers = body.answers
        db.add(Consent(candidate_id=candidate.id, notice_id=notice.id, notice_version=notice.version,
            notice_snapshot=notice.data, purpose="RECRUITMENT", granted=True, ip=actor.ip))
    audit(db, actor, "application.process_form_completed" if body.submit else "application.process_form_saved",
          row, vacancy_id=vacancy.id)
    return {"status": row.status, "submitted_at": row.submitted_at,
            "registration_released": body.submit and application.recruitment_type != "INTERNAL"}
