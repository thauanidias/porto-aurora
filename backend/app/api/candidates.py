import json
import re
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import Field
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import (
    Current,
    Db,
    candidate_access,
    is_manager,
    sector_finalist_ids,
    vacancy_scope,
)
from app.core.security import decrypt, encrypt
from app.domain.rules import matches
from app.models import (
    Application,
    AuthSession,
    Candidate,
    CandidateLabel,
    Consent,
    ConsentReceipt,
    Document,
    PipelineStage,
    Referral,
    RolePermission,
    ScoringVersion,
    StageHistory,
    SensitiveData,
    TalentPool,
    TalentPoolMember,
    User,
    UserRole,
    Vacancy,
)
from app.repositories.common import check_version, page, serialize
from app.schemas.auth import StrictModel
from app.schemas.candidates import CandidateInput, Profile, professional_facts
from app.schemas.internal_registration import InternalRegistration, InternalRegistrationInput
from app.schemas.resume_import import ConfirmResumeImport, ResumePersonalInput
from app.schemas.selection_registration import SelectionRegistration, SelectionRegistrationInput
from app.services.application_readiness import application_readiness
from app.services.candidate_journey import journey, require_candidate_section
from app.services.events import audit, event
from app.services.recruitment import candidate_view


def own_readiness(db, actor):
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    return application_readiness(db, candidate)

router = APIRouter(tags=["Candidatos e banco de talentos"])


@router.get("/candidates/me/application-readiness")
def readiness(db: Db, actor: Current):
    return own_readiness(db, actor)


@router.get("/candidates/profile-schema")
def profile_schema(actor: Current):
    return CandidateInput.model_json_schema()


@router.get("/candidates/me")
def own_profile(db: Db, actor: Current):
    row = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    return serialize(row) if row else None


@router.put("/candidates/me")
def save_profile(body: CandidateInput, db: Db, actor: Current):
    row = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    previous = {k: v for k, v in (row.profile if row else {}).items() if k != "facts"}
    if body.profile.model_dump(mode="json") != Profile.model_validate(previous).model_dump(mode="json"):
        require_candidate_section(db, actor, "professional_profile")
    document_ids = [
        str(item.document_id) for item in body.profile.certifications if item.document_id
    ]
    if len(document_ids) != len(set(document_ids)):
        raise DomainError("Cada PDF deve pertencer a uma única certificação.")
    if document_ids:
        documents = db.scalars(select(Document).where(Document.id.in_(document_ids))).all()
        if (
            not row
            or len(documents) != len(document_ids)
            or any(
                document.candidate_id != row.id
                or document.type_name != "CERTIFICADO"
                or document.mime != "application/pdf"
                for document in documents
            )
        ):
            raise DomainError("PDF de certificado inválido para este perfil.")
    if not row:
        row = Candidate(user_id=actor.user.id, name=body.name, email=actor.user.email)
        db.add(row)
    elif body.version:
        check_version(row, body.version)
    profile = body.profile.model_dump(mode="json")
    profile["facts"] = professional_facts(body.profile)
    for key, value in body.model_dump(exclude={"profile", "version"}).items():
        setattr(row, key, value)
    row.phone = re.sub(r"[^0-9+]", "", body.phone)
    if row.phone and not re.fullmatch(r"\+?[0-9]{10,15}", row.phone):
        raise DomainError("Informe telefone com DDD e, se necessário, código do país.")
    row.profile = profile
    actor.user.name = body.name
    event(db, actor, "candidate.profile_updated", row)
    from app.services.candidate_journey import application_permissions
    from app.services.recruitment import calculate_application
    for application in db.scalars(select(Application).where(Application.candidate_id == row.id,
            Application.status.in_(["ACTIVE", "RESERVE"]))):
        if application_permissions(db, application)["rank"] in {1, 2} and application.profile_snapshot != profile:
            application.profile_snapshot = profile.copy()
            model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == application.vacancy_id)
                              .order_by(ScoringVersion.number.desc()).limit(1))
            if model:
                calculate_application(db, actor, application, model)
    return serialize(row)


@router.get("/candidates/me/journey")
def own_journey(db: Db, actor: Current):
    if actor.user.kind != "CANDIDATO":
        raise DomainError("Esta jornada pertence à área do candidato.", 403)
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    return journey(db, candidate)


@router.get("/candidates/me/resume-personal/schema")
def resume_personal_schema(actor: Current):
    from app.schemas.resume_import import ResumePersonal
    return ResumePersonal.model_json_schema()


@router.get("/candidates/me/resume-personal")
def resume_personal(db: Db, actor: Current):
    from app.services.resume_personal import own_personal, personal_response
    # A new candidate can review suggestions before the first profile save.
    require_candidate_section(db, actor, "basic_profile")
    if not db.scalar(select(Candidate.id).where(Candidate.user_id == actor.user.id)):
        return personal_response({})
    return personal_response(own_personal(db, actor)[3])


@router.put("/candidates/me/resume-personal")
def update_resume_personal(body: ResumePersonalInput, db: Db, actor: Current):
    from app.services.resume_personal import save_personal
    return save_personal(db, actor, body.data, body.version)


@router.post("/candidates/me/confirm-resume-import")
def confirm_resume_import(body: ConfirmResumeImport, db: Db, actor: Current):
    from app.services.resume_personal import save_personal
    if not body.confirmed:
        raise DomainError("Confira as informações e confirme antes de salvar.")
    # Both saves use the request transaction: conflicts roll back the entire import.
    candidate = save_profile(body.candidate, db, actor)
    personal = save_personal(db, actor, body.personal, body.personal_version)
    audit(db, actor, "candidate.resume_import_confirmed", db.get(Candidate, candidate["id"]))
    return {"candidate": candidate, "personal": personal}


def registration_candidate(db, actor, lock=False):
    if actor.user.kind != "CANDIDATO":
        raise DomainError("Esta ficha pertence à área do candidato.", 403)
    query = select(Candidate).where(Candidate.user_id == actor.user.id)
    candidate = db.scalar(query.with_for_update() if lock else query)
    if not candidate or candidate.anonymized_at or candidate.merged_into_id:
        raise DomainError("Perfil de candidato não encontrado.", 404)
    return candidate


def registration_response(row, key="selection_registration"):
    stored = json.loads(decrypt(row.encrypted_data)) if row else {}
    registration = stored.get(key, {})
    return {
        "data": registration.get("data"),
        "version": registration.get("version", 0),
        "saved_at": registration.get("saved_at"),
        "confirmed_at": registration.get("confirmed_at"),
        "signature_record": registration.get("signature_record"),
    }


@router.get("/candidates/me/selection-registration/schema")
def registration_schema(actor: Current):
    if actor.user.kind != "CANDIDATO":
        raise DomainError("Esta ficha pertence à área do candidato.", 403)
    return SelectionRegistration.model_json_schema()


@router.get("/candidates/me/selection-registration")
def own_registration(db: Db, actor: Current):
    candidate = registration_candidate(db, actor)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    return registration_response(row)


@router.put("/candidates/me/selection-registration")
def save_registration(body: SelectionRegistrationInput, db: Db, actor: Current):
    require_candidate_section(db, actor, "selection_registration")
    candidate = registration_candidate(db, actor, lock=True)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    stored = json.loads(decrypt(row.encrypted_data)) if row else {}
    previous = stored.get("selection_registration", {})
    if body.version != previous.get("version", 0):
        raise DomainError("A ficha foi alterada em outra sessão. Atualize a página.", 409, "VERSION_CONFLICT")
    now = utcnow().isoformat()
    from app.services.external_profile_xlsx import TEMPLATE_SHA256, data_hash
    data = body.data.model_dump(mode="json")
    proof = None
    if body.data.declaration.accepted:
        from uuid import uuid4
        proof = {"protocol": "Porto Aurora-FICHA-" + uuid4().hex.upper(), "signed_at": now,
                 "user_id": actor.user.id, "email": actor.user.email, "ip": actor.ip,
                 "data_sha256": data_hash(data), "template_sha256": TEMPLATE_SHA256}
    if previous.get("confirmed_at"):
        stored.setdefault("selection_registration_history", []).append(previous)
    stored["selection_registration"] = {
        "form_code": "FORM-PPO-RH-002.02",
        "data": data,
        "version": body.version + 1,
        "saved_at": now,
        "confirmed_at": now if body.data.declaration.accepted else None,
        "signature_record": proof,
    }
    if not row:
        row = SensitiveData(candidate_id=candidate.id, purpose="Ficha de inscrição para seleção externa")
        db.add(row)
    row.encrypted_data = encrypt(json.dumps(stored, ensure_ascii=False))
    audit(db, actor, "candidate.selection_registration_saved", candidate)
    return registration_response(row)


@router.get("/candidates/{candidate_id}/selection-registration.xlsx")
def download_external_registration(candidate_id: str, db: Db, actor: Current):
    from app.services.external_profile_xlsx import external_profile_xlsx
    candidate, registration = rh_internal_profile(candidate_id, db, actor)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    registration = registration_response(row)
    try:
        content = external_profile_xlsx(registration)
    except (ValueError, TypeError, KeyError) as exc:
        raise DomainError(str(exc), 409) from exc
    audit(db, actor, "candidate.external_signed_template_downloaded", candidate)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={
        "Content-Disposition": f'attachment; filename="FORM-PPO-RH-002.02-{candidate.id}.xlsx"', "Cache-Control": "private, no-store"})


@router.get("/candidates/{candidate_id}/selection-registration-download")
def external_registration_download_status(candidate_id: str, db: Db, actor: Current):
    candidate, _ = rh_internal_profile(candidate_id, db, actor)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    registration = registration_response(row)
    return {"available": bool(registration["confirmed_at"] and registration["signature_record"]
                              and (registration["data"] or {}).get("declaration", {}).get("signature_image"))}


@router.get("/candidates/me/internal-registration/schema")
def internal_registration_schema(actor: Current):
    actor.require("internal.view")
    return InternalRegistration.model_json_schema()


@router.get("/candidates/me/internal-registration")
def own_internal_registration(db: Db, actor: Current):
    actor.require("internal.view")
    candidate = registration_candidate(db, actor)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    return registration_response(row, "internal_registration")


@router.put("/candidates/me/internal-registration")
def save_internal_registration(body: InternalRegistrationInput, db: Db, actor: Current):
    actor.require("internal.view")
    candidate = registration_candidate(db, actor, lock=True)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    stored = json.loads(decrypt(row.encrypted_data)) if row else {}
    previous = stored.get("internal_registration", {})
    if body.version != previous.get("version", 0):
        raise DomainError("O perfil foi alterado em outra sessão. Atualize a página.", 409, "VERSION_CONFLICT")
    now = utcnow().isoformat()
    stored["internal_registration"] = {"form_code": "FORM-PPO-RH-002.01", "data": body.data.model_dump(mode="json"),
        "version": body.version + 1, "saved_at": now, "confirmed_at": now if body.data.declaration.accepted else None}
    if not row:
        row = SensitiveData(candidate_id=candidate.id, purpose="Perfil de colaborador para seleção interna")
        db.add(row)
    row.encrypted_data = encrypt(json.dumps(stored, ensure_ascii=False))
    audit(db, actor, "candidate.internal_profile_saved", candidate)
    return registration_response(row, "internal_registration")


def scoped_candidates(actor):
    query = select(Candidate).where(
        Candidate.anonymized_at.is_(None), Candidate.merged_into_id.is_(None)
    )
    if "candidate.all" not in actor.permissions:
        authorized = select(Application.candidate_id).where(
            Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
        )
        query = query.where(Candidate.id.in_(authorized))
    return query


@router.get("/candidates")
def candidates(
    db: Db,
    actor: Current,
    q: str = "",
    city: str = "",
    state: str = "",
    recruitment_type: str = "",
    talent_bank: bool = False,
    page_number: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    actor.require("candidate.view")
    query = scoped_candidates(actor)
    from app.services.talent_bank import internal_users, unsuccessful_candidates
    if talent_bank:
        unsuccessful = unsuccessful_candidates().where(
            Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
        )
        query = query.where(Candidate.id.in_(unsuccessful))
    if recruitment_type == "INTERNAL":
        query = query.where(Candidate.user_id.in_(internal_users()))
    elif recruitment_type == "EXTERNAL":
        query = query.where(Candidate.user_id.not_in(internal_users()))
    # Identity cannot be inferred using search results for an unrevealed blind application.
    blind_ids = (
        select(Application.candidate_id)
        .join(Vacancy, Application.vacancy_id == Vacancy.id)
        .where(Vacancy.blind.is_(True))
    )
    if q:
        document = func.to_tsvector(
            "portuguese",
            Candidate.name
            + " "
            + Candidate.city
            + " "
            + Candidate.profile.cast(__import__("sqlalchemy").Text),
        )
        query = query.where(
            Candidate.id.not_in(blind_ids), document.op("@@")(func.plainto_tsquery("portuguese", q))
        )
    if city:
        query = query.where(Candidate.id.not_in(blind_ids), Candidate.city == city)
    if state:
        query = query.where(Candidate.id.not_in(blind_ids), Candidate.state == state)
    vacancy_titles: dict[str, list[str]] = {}
    finalist_history: dict[str, list[dict]] = {}
    process_history: dict[str, list[dict]] = {}
    employees = set(db.scalars(internal_users()))

    def prepare_candidates(candidates):
        if not candidates:
            return
        applications = db.execute(
            select(Application, Vacancy, PipelineStage)
            .join(Vacancy, Application.vacancy_id == Vacancy.id)
            .join(PipelineStage, PipelineStage.id == Application.stage_id)
            .where(Application.candidate_id.in_([row.id for row in candidates]), vacancy_scope(actor))
            .order_by(Application.created_at.desc())
        )
        for application, vacancy, stage in applications:
            titles = vacancy_titles.setdefault(application.candidate_id, [])
            if vacancy.title not in titles:
                titles.append(vacancy.title)
            process_history.setdefault(application.candidate_id, []).append({
                "application_id": application.id, "vacancy_title": vacancy.title,
                "stage_name": stage.name, "stage_kind": stage.kind, "status": application.status,
                "recruitment_type": application.recruitment_type,
                "registered_at": application.created_at.isoformat(),
                "updated_at": application.updated_at.isoformat(),
            })
        seen = set()
        for application, vacancy, history in db.execute(
            select(Application, Vacancy, StageHistory)
            .join(Vacancy, Application.vacancy_id == Vacancy.id)
            .join(StageHistory, StageHistory.application_id == Application.id)
            .join(PipelineStage, PipelineStage.id == StageHistory.stage_id)
            .where(Application.candidate_id.in_([row.id for row in candidates]), vacancy_scope(actor), PipelineStage.kind == "FINALIST")
            .order_by(StageHistory.entered_at.desc(), StageHistory.id.desc())
        ):
            if application.id in seen:
                continue
            seen.add(application.id)
            finalist_history.setdefault(application.candidate_id, []).append({
                "application_id": application.id, "vacancy_title": vacancy.title,
                "entered_at": history.entered_at.isoformat(),
                "current": application.stage_id == history.stage_id and history.left_at is None,
            })

    return page(
        db,
        query.order_by(Candidate.updated_at.desc()),
        page_number,
        page_size,
        lambda row: candidate_view(db, actor, row) | {
            "vacancy_titles": vacancy_titles.get(row.id, []),
            "finalist_history": finalist_history.get(row.id, []),
            "process_history": process_history.get(row.id, []),
            "recruitment_type": "INTERNAL" if row.user_id in employees else "EXTERNAL",
            "talent_available": bool(row.talent_consent_until and row.talent_consent_until > utcnow()),
        },
        prepare=prepare_candidates,
    )


@router.get("/manager-finalists")
def manager_finalists(db: Db, actor: Current, q: str = "",
                      page_number: Annotated[int, Query(ge=1)] = 1,
                      page_size: Annotated[int, Query(ge=1, le=100)] = 25):
    actor.require("candidate.view")
    if not is_manager(actor):
        raise DomainError("Área exclusiva de gestores.", 403)
    eligible = sector_finalist_ids(actor)
    query = select(Candidate).where(
        Candidate.anonymized_at.is_(None), Candidate.merged_into_id.is_(None),
        Candidate.id.in_(select(Application.candidate_id).where(Application.id.in_(eligible))),
    )
    if q.strip():
        hidden = select(Application.candidate_id).join(Vacancy).join(
            PipelineStage, Application.stage_id == PipelineStage.id,
        ).where(Vacancy.blind.is_(True), PipelineStage.reveal_identity.is_(False))
        query = query.where(Candidate.id.not_in(hidden), Candidate.name.ilike("%" + q.strip() + "%"))
    processes: dict[str, list[dict]] = {}

    def prepare(rows):
        for application, vacancy, stage in db.execute(select(Application, Vacancy, PipelineStage)
                .join(Vacancy, Application.vacancy_id == Vacancy.id)
                .join(PipelineStage, Application.stage_id == PipelineStage.id)
                .where(Application.id.in_(eligible), Application.candidate_id.in_([row.id for row in rows]))
                .order_by(Application.stage_entered_at.desc(), Application.id)):
            processes.setdefault(application.candidate_id, []).append({
                "application_id": application.id, "vacancy_title": vacancy.title,
                "stage_name": stage.name, "status": application.status,
            })

    return page(db, query.order_by(Candidate.updated_at.desc(), Candidate.id), page_number, page_size,
                lambda row: candidate_view(db, actor, row) | {
                    "finalist": True, "finalist_processes": processes.get(row.id, []),
                    "vacancy_titles": list(dict.fromkeys(p["vacancy_title"] for p in processes.get(row.id, []))),
                }, prepare=prepare)


@router.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: str, db: Db, actor: Current):
    row = candidate_access(db, actor, candidate_id)
    audit(db, actor, "candidate.accessed", row)
    return candidate_view(db, actor, row)


@router.get("/candidates/{candidate_id}/duplicates")
def duplicates(candidate_id: str, db: Db, actor: Current):
    row = candidate_access(db, actor, candidate_id, "candidate.merge")
    actor.require("candidate.merge")
    query = scoped_candidates(actor).where(
        Candidate.id != row.id,
        or_(Candidate.email == row.email, (Candidate.phone == row.phone) & (Candidate.phone != "")),
    )
    return {
        "label": "Possível cadastro duplicado",
        "items": [candidate_view(db, actor, item) for item in db.scalars(query.limit(25))],
    }


class MergeInput(StrictModel):
    source_id: str
    reason: str = Field(min_length=10)


@router.post("/candidates/{candidate_id}/merge")
def merge(candidate_id: str, body: MergeInput, db: Db, actor: Current):
    actor.require("candidate.merge")
    target = candidate_access(db, actor, candidate_id)
    source = candidate_access(db, actor, body.source_id)
    if (
        target.id == source.id
        or target.anonymized_at
        or source.anonymized_at
        or source.merged_into_id
        or target.merged_into_id
    ):
        raise DomainError("Consolidação inválida.")
    # Consistent lock ordering protects concurrent consolidation.
    list(
        db.scalars(
            select(Candidate)
            .where(Candidate.id.in_([target.id, source.id]))
            .order_by(Candidate.id)
            .with_for_update()
        )
    )
    before = {
        "source_id": source.id,
        "source_profile": source.profile,
        "target_profile": target.profile,
    }
    source_vacancies = set(
        db.scalars(select(Application.vacancy_id).where(Application.candidate_id == source.id))
    )
    target_vacancies = set(
        db.scalars(select(Application.vacancy_id).where(Application.candidate_id == target.id))
    )
    if source_vacancies & target_vacancies:
        raise DomainError(
            "Há candidaturas na mesma vaga. Resolva o conflito antes de consolidar.", 409
        )
    for application in db.scalars(select(Application).where(Application.candidate_id == source.id)):
        application.candidate_id = target.id
    for document in db.scalars(select(Document).where(Document.candidate_id == source.id)):
        document.candidate_id = target.id
    for referral in db.scalars(select(Referral).where(Referral.candidate_id == source.id)):
        referral.candidate_id = target.id
    for membership in db.scalars(
        select(TalentPoolMember).where(TalentPoolMember.candidate_id == source.id)
    ):
        exists = db.scalar(
            select(TalentPoolMember.id).where(
                TalentPoolMember.candidate_id == target.id,
                TalentPoolMember.pool_id == membership.pool_id,
            )
        )
        if exists:
            db.delete(membership)
        else:
            membership.candidate_id = target.id
    source_user = db.get(User, source.user_id)
    if source_user and source_user.id != target.user_id:
        if source_user.kind != "CANDIDATO":
            raise DomainError("Não é permitido consolidar uma identidade corporativa.", 409)
        source_user.active = False
        for session in db.scalars(select(AuthSession).where(AuthSession.user_id == source_user.id)):
            session.revoked_at = utcnow()
    # Candidate-owned consents, answers and original profile stay associated with their source
    # for provenance; the merge audit connects both identities without rewriting receipts.
    source.merged_into_id = target.id
    audit(
        db,
        actor,
        "candidate.merged",
        target,
        before=before,
        after={"source_id": source.id, "reason": body.reason},
    )
    return serialize(target)


class SensitiveInput(StrictModel):
    purpose: str = Field(min_length=10)
    data: dict[str, str]
    consent: bool


@router.put("/candidates/me/sensitive")
def save_sensitive(body: SensitiveInput, db: Db, actor: Current):
    require_candidate_section(db, actor, "sensitive_profile")
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id).with_for_update())
    if (
        not candidate
        or not body.consent
        or set(body.data) - {"pcd", "accessibility_needs", "diversity"}
    ):
        raise DomainError("Dados sensíveis exigem finalidade e consentimento.")
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    if not row:
        row = SensitiveData(candidate_id=candidate.id)
        db.add(row)
    stored = json.loads(decrypt(row.encrypted_data)) if row.encrypted_data else {}
    stored.update(body.data)
    row.encrypted_data = encrypt(json.dumps(stored))
    row.purpose = body.purpose
    audit(db, actor, "candidate.sensitive_updated", candidate)
    return {"message": "Preferências sensíveis salvas com acesso restrito."}


@router.get("/candidates/{candidate_id}/sensitive")
def sensitive(candidate_id: str, db: Db, actor: Current):
    candidate_access(db, actor, candidate_id, "candidate.sensitive.view")
    actor.require("candidate.sensitive.view")
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate_id))
    if row:
        audit(db, actor, "candidate.sensitive_accessed", row)
    return {
        "data": json.loads(decrypt(row.encrypted_data)) if row else {},
        "purpose": row.purpose if row else "",
    }


@router.get("/candidates/{candidate_id}/selection-documents")
def selection_documents(candidate_id: str, db: Db, actor: Current):
    candidate = candidate_access(db, actor, candidate_id)
    if actor.user.kind != "INTERNAL":
        raise DomainError("Esta consulta pertence à área do RH.", 403)
    if candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("Documentos de identificação indisponíveis durante a seleção sem identidade.", 403)
    can_sensitive = "candidate.sensitive.view" in actor.permissions
    can_registration = can_sensitive or "candidate.registration.view" in actor.permissions
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id)) if can_registration else None
    stored = json.loads(decrypt(row.encrypted_data)) if row else {}
    receipts = db.scalars(candidate_receipts(candidate)).all()
    audit(db, actor, "candidate.selection_documents_accessed", candidate)
    return {"id": candidate.id, "registration": registration_response(row) if can_registration else {"restricted": True},
        "schema": SelectionRegistration.model_json_schema(),
        "receipts": [serialize(receipt, {"document_snapshot"}) for receipt in receipts],
        "accessibility": {key: value for key, value in stored.items() if can_sensitive and key in {"accessibility_needs", "pcd", "diversity"}},
        "purpose": row.purpose if row else ""}


def candidate_receipts(candidate):
    linked = select(Consent.notice_snapshot["receipt_id"].astext).where(Consent.candidate_id == candidate.id)
    return select(ConsentReceipt).where(
        or_(ConsentReceipt.user_id == candidate.user_id, ConsentReceipt.id.in_(linked)),
        ConsentReceipt.context.in_(["CADASTRO", "CANDIDATURA"]),
    ).order_by(ConsentReceipt.created_at.desc(), ConsentReceipt.id.desc())


@router.get("/candidates/{candidate_id}/consent-download")
def consent_download_status(candidate_id: str, db: Db, actor: Current):
    candidate = candidate_access(db, actor, candidate_id)
    if actor.user.kind != "INTERNAL":
        raise DomainError("Esta consulta pertence à área do RH.", 403)
    if candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("Termo indisponível durante a seleção sem identidade.", 403)
    receipt = db.scalar(candidate_receipts(candidate).limit(1))
    return {"available": bool(receipt), "receipt_id": receipt.id if receipt else None,
            "protocol": receipt.protocol if receipt else None}


def rh_internal_profile(candidate_id, db, actor):
    candidate = candidate_access(db, actor, candidate_id)
    if actor.user.kind != "INTERNAL":
        raise DomainError("Esta consulta pertence à área do RH.", 403)
    if not ({"candidate.registration.view", "candidate.sensitive.view"} & actor.permissions):
        actor.require("candidate.registration.view")
    if candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("Ficha indisponível durante a seleção sem identidade.", 403)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    return candidate, registration_response(row, "internal_registration")


@router.get("/candidates/{candidate_id}/internal-profile-downloads")
def internal_profile_downloads(candidate_id: str, db: Db, actor: Current):
    candidate, registration = rh_internal_profile(candidate_id, db, actor)
    internal = bool(db.scalar(select(UserRole.user_id).join(RolePermission, RolePermission.role_id == UserRole.role_id).where(
        UserRole.user_id == candidate.user_id, RolePermission.permission == "internal.view").limit(1)))
    resume = db.scalar(select(Document).where(Document.candidate_id == candidate.id,
        Document.type_name == "CURRICULO", Document.scan_status != "DELETED").order_by(Document.created_at.desc(), Document.revision.desc()).limit(1))
    return {"is_internal": internal or bool(registration["data"]), "available": bool(registration["data"]), "version": registration["version"],
            "saved_at": registration["saved_at"], "confirmed_at": registration["confirmed_at"],
            "resume": serialize(resume, {"storage_key"}) if resume else None}


@router.get("/candidates/{candidate_id}/internal-registration.xlsx")
def download_internal_profile_xlsx(candidate_id: str, db: Db, actor: Current):
    from app.services.internal_profile_xlsx import internal_profile_xlsx

    candidate, registration = rh_internal_profile(candidate_id, db, actor)
    if not registration["data"]:
        raise DomainError("O colaborador ainda não preencheu a ficha interna.", 404)
    content = internal_profile_xlsx(registration)
    audit(db, actor, "candidate.internal_template_downloaded", candidate)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={
        "Content-Disposition": f'attachment; filename="FORM-PPO-RH-002.01-{candidate.id}.xlsx"',
        "Cache-Control": "no-store"})


@router.get("/candidates/{candidate_id}/internal-registration.pdf")
def download_internal_profile(candidate_id: str, db: Db, actor: Current):
    from app.services.internal_profile_pdf import internal_profile_pdf

    candidate, registration = rh_internal_profile(candidate_id, db, actor)
    if not registration["data"]:
        raise DomainError("O colaborador ainda não preencheu a ficha interna.", 404)
    content = internal_profile_pdf(registration, candidate.name)
    audit(db, actor, "candidate.internal_profile_downloaded", candidate)
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="FORM-PPO-RH-002.01-{candidate.id}.pdf"',
        "Cache-Control": "no-store"})


class PoolInput(StrictModel):
    name: str = Field(min_length=2)
    description: str = ""
    filters: dict = Field(default_factory=dict)


@router.get("/talent-pools")
def pools(db: Db, actor: Current, q: str = "", page_number: Annotated[int, Query(ge=1)] = 1):
    actor.require("talent.manage")
    return page(
        db,
        select(TalentPool).where(TalentPool.name.ilike("%" + q + "%")).order_by(TalentPool.name),
        page_number,
        25,
    )


@router.post("/talent-pools", status_code=201)
def create_pool(body: PoolInput, db: Db, actor: Current):
    actor.require("talent.manage")
    matches(body.filters, {})
    row = TalentPool(**body.model_dump(), created_by=actor.user.id)
    db.add(row)
    audit(db, actor, "talent_pool.created", row)
    return serialize(row)


@router.get("/talent-pools/{pool_id}/members")
def pool_members(
    pool_id: str, db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1
):
    actor.require("talent.manage")
    pool = db.get(TalentPool, pool_id)
    if not pool:
        raise DomainError("Banco não encontrado.", 404)
    query = scoped_candidates(actor).where(Candidate.talent_consent_until > utcnow())
    if not pool.filters:
        query = query.where(
            Candidate.id.in_(
                select(TalentPoolMember.candidate_id).where(TalentPoolMember.pool_id == pool.id)
            )
        )
        return page(
            db,
            query.order_by(Candidate.updated_at.desc()),
            page_number,
            25,
            lambda row: candidate_view(db, actor, row),
        )
    # Deterministic filters operate on authorized, consented records; paginate after filtering.
    rows = [
        row
        for row in db.scalars(query.execution_options(yield_per=100))
        if matches(pool.filters, serialize(row) | row.profile.get("facts", {}))
    ]
    return {
        "items": [
            candidate_view(db, actor, row)
            for row in rows[(page_number - 1) * 25 : page_number * 25]
        ],
        "total": len(rows),
        "page": page_number,
        "page_size": 25,
    }


@router.post("/talent-pools/{pool_id}/members/{candidate_id}")
def add_member(pool_id: str, candidate_id: str, db: Db, actor: Current):
    actor.require("talent.manage")
    candidate = candidate_access(db, actor, candidate_id)
    if (
        not db.get(TalentPool, pool_id)
        or not candidate.talent_consent_until
        or candidate.talent_consent_until <= utcnow()
    ):
        raise DomainError("Banco inválido ou consentimento ausente/expirado.")
    existing = db.scalar(
        select(TalentPoolMember).where(
            TalentPoolMember.pool_id == pool_id, TalentPoolMember.candidate_id == candidate_id
        )
    )
    if not existing:
        row = TalentPoolMember(pool_id=pool_id, candidate_id=candidate_id, added_by=actor.user.id)
        db.add(row)
        audit(db, actor, "talent_pool.member_added", row)
    return {"message": "Candidato incluído no banco."}


class LabelInput(StrictModel):
    label: str = Field(min_length=1, max_length=180)
    kind: str = "TAG"


@router.post("/candidates/{candidate_id}/labels")
def label(candidate_id: str, body: LabelInput, db: Db, actor: Current):
    candidate_access(db, actor, candidate_id)
    actor.require("talent.manage")
    if body.kind not in {"TAG", "FAVORITE"}:
        raise DomainError("Tipo de marcação inválido.")
    row = CandidateLabel(candidate_id=candidate_id, user_id=actor.user.id, **body.model_dump())
    db.add(row)
    audit(db, actor, "candidate.label_added", row)
    return serialize(row)
