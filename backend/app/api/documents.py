from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import Field
from sqlalchemy import func, or_, select

from app.core.config import settings
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, candidate_access, vacancy_scope
from app.integrations.files import prepare_profile_photo, scan, store_file, validate_file
from app.models import (
    Application,
    Candidate,
    CandidateDocumentSource,
    Document,
    Outbox,
    PipelineStage,
    RolePermission,
    StageHistory,
    UserRole,
    Vacancy,
)
from app.repositories.common import check_version, page, serialize
from app.schemas.auth import StrictModel
from app.services.admission_documents import (
    ADMISSION_CATALOG,
    ADMISSION_TYPES,
    admission_eligible,
)
from app.services.events import audit, notify

router = APIRouter(tags=["Documentos"])


def document_view(row):
    result = serialize(row, {"storage_key"})
    result["type_label"] = next(
        (item["title"] for item in ADMISSION_CATALOG if item["type_name"] == row.type_name),
        None,
    )
    return result


def document_source_candidate(db, actor, candidate_id):
    from app.services.recruitment import candidate_view

    if actor.user.kind != "INTERNAL":
        raise DomainError("Área exclusiva do RH.", 403)
    actor.require("candidate.sensitive.view")
    candidate = candidate_access(db, actor, candidate_id)
    if candidate.anonymized_at or candidate.merged_into_id or candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("Documentos indisponíveis para este perfil nesta etapa.", 403)
    return candidate


def internal_candidate(db, candidate):
    return bool(db.scalar(select(UserRole.user_id).join(RolePermission, RolePermission.role_id == UserRole.role_id).where(
        UserRole.user_id == candidate.user_id, RolePermission.permission == "internal.view").limit(1)) or db.scalar(
        select(Application.id).where(Application.candidate_id == candidate.id, Application.recruitment_type == "INTERNAL").limit(1)))


@router.get("/candidates/{candidate_id}/external-document-sources")
def external_document_sources(candidate_id: str, db: Db, actor: Current):
    target = document_source_candidate(db, actor, candidate_id)
    items = []
    for link in db.scalars(select(CandidateDocumentSource).where(CandidateDocumentSource.candidate_id == target.id)):
        try:
            source = document_source_candidate(db, actor, link.source_candidate_id)
        except DomainError:
            continue
        documents = db.scalars(select(Document).where(Document.id.in_(link.documents.get("ids", [])),
            Document.candidate_id == source.id, Document.scan_status != "DELETED").order_by(Document.created_at.desc())).all()
        items.append({"id": link.id, "source_id": source.id, "source_name": source.name, "source_email": source.email,
                      "linked_at": link.created_at, "documents": [document_view(doc) for doc in documents]})
    return {"is_internal": internal_candidate(db, target), "items": items}


class LinkExternalDocuments(StrictModel):
    source_candidate_id: str
    identity_confirmed: Literal[True]
    reason: str = Field(min_length=10, max_length=1000)


@router.post("/candidates/{candidate_id}/external-document-sources", status_code=201)
def link_external_documents(candidate_id: str, body: LinkExternalDocuments, db: Db, actor: Current):
    actor.require("document.review")
    target = document_source_candidate(db, actor, candidate_id)
    source = document_source_candidate(db, actor, body.source_candidate_id)
    db.execute(select(Candidate).where(Candidate.id == target.id).with_for_update())
    has_external_history = db.scalar(select(Application.id).where(Application.candidate_id == source.id,
        Application.recruitment_type == "EXTERNAL").limit(1))
    if target.id == source.id or not internal_candidate(db, target) or (internal_candidate(db, source) and not has_external_history):
        raise DomainError("Selecione o cadastro externo da mesma pessoa e um perfil interno de destino.")
    if len(body.reason.strip()) < 10:
        raise DomainError("Informe como a identidade foi conferida.")
    documents = list(db.scalars(select(Document.id).where(Document.candidate_id == source.id,
        Document.type_name.not_in(["FOTO_PERFIL", "RESPOSTA_TESTE", "TEST_RESPONSE"]),
        Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"]), Document.status != "REJECTED")))
    if not documents:
        raise DomainError("Este cadastro não possui documentos disponíveis para associação.", 409)
    link = db.scalar(select(CandidateDocumentSource).where(CandidateDocumentSource.candidate_id == target.id,
        CandidateDocumentSource.source_candidate_id == source.id))
    if not link:
        link = CandidateDocumentSource(candidate_id=target.id, source_candidate_id=source.id)
        db.add(link)
    link.documents, link.linked_by, link.reason = {"ids": documents}, actor.user.id, body.reason.strip()
    audit(db, actor, "candidate.external_documents_linked", link,
          after={"source_candidate_id": source.id, "document_count": len(documents)})
    return {"id": link.id, "document_count": len(documents)}


@router.delete("/candidates/{candidate_id}/external-document-sources/{link_id}")
def unlink_external_documents(candidate_id: str, link_id: str, db: Db, actor: Current):
    actor.require("document.review")
    target = document_source_candidate(db, actor, candidate_id)
    link = db.get(CandidateDocumentSource, link_id)
    if not link or link.candidate_id != target.id:
        raise DomainError("Associação não encontrada.", 404)
    audit(db, actor, "candidate.external_documents_unlinked", link)
    db.delete(link)
    return {"removed": True}


@router.get("/document-candidates")
def document_candidates(db: Db, actor: Current, q: str = "", page_number: int = Query(default=1, ge=1)):
    from app.services.candidate_journey import stage_phase
    from app.services.recruitment import candidate_view

    actor.require("candidate.view")
    if actor.user.kind != "INTERNAL":
        raise DomainError("Área exclusiva do RH.", 403)
    scoped_vacancies = select(Vacancy.id).where(vacancy_scope(actor))
    stages = [stage.id for stage in db.scalars(select(PipelineStage).where(
        PipelineStage.vacancy_id.in_(scoped_vacancies)
    )) if stage_phase(db, stage) in {"TEST", "ADMISSION"}]
    eligible = select(Application.candidate_id).where(
        Application.vacancy_id.in_(scoped_vacancies), or_(
            Application.stage_id.in_(stages),
            Application.id.in_(select(StageHistory.application_id).where(StageHistory.stage_id.in_(stages))),
            Application.status.in_(["SELECTED", "PRE_ADMISSION", "HIRED"]),
        ),
    )
    query = select(Candidate).where(Candidate.id.in_(eligible))
    if q:
        hidden = select(Application.candidate_id).join(Vacancy).join(
            PipelineStage, Application.stage_id == PipelineStage.id
        ).where(Vacancy.blind.is_(True), PipelineStage.reveal_identity.is_(False))
        query = query.where(Candidate.id.not_in(hidden), Candidate.name.ilike("%" + q + "%"))
    counts = {}
    processes: dict[str, list[dict[str, str]]] = {}

    def prepare(candidates):
        ids = [candidate.id for candidate in candidates]
        for candidate_id, count in db.execute(select(Document.candidate_id, func.count()).where(
            Document.candidate_id.in_(ids), Document.scan_status != "DELETED",
        ).group_by(Document.candidate_id)):
            counts[candidate_id] = count
        for candidate_id, title, stage_name in db.execute(select(Application.candidate_id, Vacancy.title, PipelineStage.name)
            .join(Vacancy, Application.vacancy_id == Vacancy.id)
            .join(PipelineStage, Application.stage_id == PipelineStage.id)
            .where(Application.candidate_id.in_(ids), Application.vacancy_id.in_(scoped_vacancies))
            .order_by(Application.created_at.desc())):
            processes.setdefault(candidate_id, []).append({"vacancy_title": title, "stage_name": stage_name})

    def view(candidate):
        record = candidate_view(db, actor, candidate)
        return {"id": candidate.id, "name": record["name"], "blind": bool(record.get("blind")),
                "city": record.get("city", ""), "version": candidate.version,
                "document_count": 0 if record.get("blind") else counts.get(candidate.id, 0),
                "processes": processes.get(candidate.id, [])}

    return page(db, query.order_by(Candidate.updated_at.desc(), Candidate.id), page_number, 25, view, prepare=prepare)


def retire_photos(db, candidate_id):
    for photo in db.scalars(select(Document).where(
        Document.candidate_id == candidate_id, Document.type_name == "FOTO_PERFIL",
        Document.scan_status != "DELETED",
    )):
        db.add(Outbox(kind="DELETE_FILE", dedup_key="delete:" + photo.id,
                      payload={"storage_key": photo.storage_key}))
        photo.scan_status = "DELETED"
        photo.status = "REMOVED"


@router.delete("/candidates/me/photo")
def remove_photo(db: Db, actor: Current):
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    if not candidate:
        raise DomainError("Perfil não encontrado.", 404)
    db.execute(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    retire_photos(db, candidate.id)
    audit(db, actor, "candidate.photo_removed", candidate)
    return {"removed": True}


@router.post("/documents", status_code=201)
async def upload(
    db: Db,
    actor: Current,
    file: Annotated[UploadFile, File()],
    type_name: Annotated[str, Form()] = "CURRICULO",
    application_id: Annotated[str | None, Form()] = None,
    candidate_id: Annotated[str | None, Form()] = None,
):
    from app.services.candidate_journey import (
        require_application_section,
        require_candidate_section,
    )
    if type_name not in ADMISSION_TYPES | {"FOTO_PERFIL", "PRE_ADMISSION", "TEST_RESPONSE"}:
        require_candidate_section(db, actor, "resume")
    if type_name == "TEST_RESPONSE":
        require_candidate_section(db, actor, "tests")
        if application_id and actor.user.kind == "CANDIDATO":
            require_application_section(db, application_access(db, actor, application_id), "tests")
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    if candidate_id:
        actor.require("document.review")
        if actor.user.kind != "INTERNAL":
            raise DomainError("Somente o RH pode enviar documentos para outro candidato.", 403)
        candidate = candidate_access(db, actor, candidate_id, "document.review")
    if application_id:
        application = application_access(db, actor, application_id)
        if candidate_id and application.candidate_id != candidate_id:
            raise DomainError("A candidatura não pertence ao candidato informado.", 422)
        if not candidate or candidate.id != application.candidate_id:
            actor.require("document.review")
            candidate = candidate_access(db, actor, application.candidate_id)
    if not candidate and type_name == "CURRICULO" and not application_id and actor.user.kind == "CANDIDATO":
        candidate = Candidate(user_id=actor.user.id, name=actor.user.name,
                              email=actor.user.email, profile={})
        db.add(candidate)
        db.flush()
    if not candidate:
        raise DomainError("Preencha o perfil antes de enviar documentos.")
    photo = type_name == "FOTO_PERFIL"
    admission = type_name in ADMISSION_TYPES
    if type_name.startswith("ADM_") and not admission:
        raise DomainError("Tipo de documento admissional inválido.")
    if admission:
        db.execute(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    if (admission or type_name == "PRE_ADMISSION") and actor.user.kind == "CANDIDATO":
        if not admission_eligible(db, candidate):
            raise DomainError("O envio de documentos admissionais aguarda liberação do RH.", 403)
        if not candidate.admission_documents_approved:
            raise DomainError("O envio de documentos admissionais aguarda aprovação do RH.", 403)
    if admission:
        db.execute(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
        latest = db.scalar(select(Document).where(
            Document.candidate_id == candidate.id, Document.type_name == type_name,
        ).order_by(Document.revision.desc()).limit(1))
        if latest and latest.status != "REJECTED":
            raise DomainError("Este documento já foi enviado. Um novo envio depende de correção solicitada pelo RH.", 409)
    if photo and (candidate.user_id != actor.user.id or application_id):
        raise DomainError("A foto deve ser enviada pelo próprio candidato em seu perfil.", 403)
    if photo:
        db.execute(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    content = await file.read((5 if photo else settings().max_upload_mb) * 1024 * 1024 + 1)
    if photo:
        content = prepare_profile_photo(content)
        mime, suffix = "image/jpeg", ".jpg"
    else:
        mime, suffix = validate_file(file.filename or "", content, allow_doc=type_name == "CURRICULO")
    if type_name == "CERTIFICADO" and mime != "application/pdf":
        raise DomainError("Envie o certificado em PDF.")
    if admission and mime != "application/pdf":
        raise DomainError("Envie o documento admissional em PDF, com todas as páginas no mesmo arquivo.")
    scan_status = scan(content)
    revision = (
        db.scalar(
            select(func.max(Document.revision)).where(
                Document.candidate_id == candidate.id, Document.type_name == type_name
            )
        )
        or 0
    ) + 1
    key, sha = store_file(content, suffix)
    safe_name = "foto-perfil.jpg" if photo else Path((file.filename or "documento").replace("\\", "/")).name[:170]
    row = Document(
        candidate_id=candidate.id,
        application_id=application_id,
        uploaded_by=actor.user.id,
        type_name=type_name,
        filename=safe_name,
        storage_key=key,
        sha256=sha,
        size=len(content),
        mime=mime,
        revision=revision,
        scan_status=scan_status,
    )
    try:
        if photo:
            retire_photos(db, candidate.id)
        db.add(row)
        audit(db, actor, "document.uploaded", row)
        db.commit()
    except Exception:
        (Path(settings().upload_dir) / key).unlink(missing_ok=True)
        raise
    return serialize(row, {"storage_key"})


@router.post("/documents/{document_id}/profile-import", status_code=202)
def start_profile_import(document_id: str, db: Db, actor: Current):
    from app.services.candidate_journey import require_candidate_section
    from app.services.resume_jobs import owned_document, read_job, write_job
    from app.tasks.worker import resume_import
    require_candidate_section(db, actor, "resume")
    owned_document(db, actor.user.id, document_id)
    previous = read_job(actor.user.id, document_id)
    if previous and previous["status"] in {"QUEUED", "RUNNING", "COMPLETED"}:
        return previous
    data = {"status": "QUEUED", "message": "Currículo na fila de leitura…"}
    if not previous and not write_job(actor.user.id, document_id, data, only_new=True):
        return read_job(actor.user.id, document_id)
    if previous:
        write_job(actor.user.id, document_id, data)
    try:
        resume_import.delay(actor.user.id, document_id)
    except Exception as exc:
        write_job(actor.user.id, document_id, {"status": "FAILED", "message": "Serviço de leitura indisponível. Tente novamente."})
        raise DomainError("Serviço de leitura indisponível. O currículo continua anexado.", 503) from exc
    return data


@router.get("/documents/{document_id}/profile-import")
def profile_import_status(document_id: str, db: Db, actor: Current):
    from app.services.candidate_journey import require_candidate_section
    from app.services.resume_jobs import owned_document, read_job
    require_candidate_section(db, actor, "resume")
    owned_document(db, actor.user.id, document_id)
    result = read_job(actor.user.id, document_id)
    if not result:
        raise DomainError("Esta leitura expirou. Clique em preencher com este currículo para iniciar novamente.", 404)
    return result


@router.get("/documents/{document_id}/profile-suggestions")
def resume_suggestions(document_id: str, db: Db, actor: Current):
    from app.services.candidate_journey import require_candidate_section
    require_candidate_section(db, actor, "resume")
    from app.services.resume_profile import profile_suggestions, resume_text

    row = db.get(Document, document_id)
    candidate = db.get(Candidate, row.candidate_id) if row else None
    if not row or not candidate or candidate.user_id != actor.user.id:
        raise DomainError("Currículo não encontrado.", 404)
    if row.type_name != "CURRICULO" or row.scan_status not in {"CLEAN", "NOT_CONFIGURED"}:
        raise DomainError("Este arquivo não está disponível para leitura.", 409)
    from app.services.resume_cache import read_result, store_result
    if settings().resume_ai_enabled:
        cached = read_result(actor.user.id, row.sha256)
        if cached is not None:
            return {**cached, "cached": True}
    content = (Path(settings().upload_dir) / row.storage_key).read_bytes()
    text = resume_text(content, row.mime)
    from app.services.resume_ai import extract_local
    result = extract_local(text) if settings().resume_ai_enabled and text else {"suggestions": profile_suggestions(text), "missing": [], "uncertain": []}
    response = {**result, "text": text,
            "engine": "local-ai" if settings().resume_ai_enabled else "local-rules",
            "message": "Revise os dados sugeridos e complete as demais informações antes de salvar."
            if text else "Não encontramos texto selecionável. O arquivo está salvo em Documentos; preencha o perfil manualmente."}
    if settings().resume_ai_enabled and text:
        store_result(actor.user.id, row.sha256, response)
    return {**response, "cached": False}


@router.get("/documents/admission-checklist")
def admission_checklist(db: Db, actor: Current, candidate_id: str = ""):
    candidate = candidate_access(db, actor, candidate_id) if candidate_id else db.scalar(
        select(Candidate).where(Candidate.user_id == actor.user.id)
    )
    if candidate:
        from app.services.recruitment import candidate_view

        if candidate_view(db, actor, candidate).get("blind"):
            raise DomainError("Documentos indisponíveis durante triagem sem identidade.", 403)
    documents = db.scalars(select(Document).where(
        Document.candidate_id == candidate.id, Document.type_name.in_(ADMISSION_TYPES),
        Document.scan_status != "DELETED",
    ).order_by(Document.created_at.desc())).all() if candidate else []
    by_type: dict[str, dict] = {}
    for row in documents:
        by_type.setdefault(row.type_name, serialize(row, {"storage_key"}))
    eligible = admission_eligible(db, candidate)
    rh_can_manage = bool(candidate and actor.user.kind == "INTERNAL" and "document.review" in actor.permissions)
    return {"source": "FORM-PPO-RH-002.06", "eligible": eligible, "can_upload": bool(rh_can_manage or candidate and eligible and candidate.user_id == actor.user.id and candidate.admission_documents_approved),
            "has_profile": bool(candidate),
            "approved": bool(candidate and eligible and candidate.admission_documents_approved),
            "can_approve": bool(rh_can_manage and eligible),
            "internal_account": actor.user.kind == "INTERNAL", "items": [
        {**item, "document": by_type.get(item["type_name"])} for item in ADMISSION_CATALOG
    ]}


@router.post("/candidates/{candidate_id}/approve-document-uploads")
def approve_document_uploads(candidate_id: str, db: Db, actor: Current):
    actor.require("document.review")
    candidate = candidate_access(db, actor, candidate_id, "document.review")
    if actor.user.kind != "INTERNAL":
        raise DomainError("Apenas o RH pode liberar o envio.", 403)
    db.execute(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    from app.services.admission_documents import admission_can_release
    if not admission_can_release(db, candidate):
        raise DomainError("Conclua os testes e avance para a etapa de documentos antes de liberar o envio.", 409)
    if not candidate.admission_documents_approved:
        candidate.admission_documents_approved = True
        audit(db, actor, "candidate.admission_documents_approved", candidate)
        notify(db, candidate.user_id, "Envio de documentos liberado", "O RH liberou os documentos admissionais. Acesse a área de Documentos para conferir os itens e enviar os arquivos aplicáveis ao seu caso.", "DOCUMENT", "/candidato/documentos")
    return {"approved": True}


@router.get("/documents")
def documents(
    db: Db, actor: Current, candidate_id: str = "", type_name: str = "",
    include_photo: bool = False,
    page_number: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
):
    candidate = (
        candidate_access(db, actor, candidate_id)
        if candidate_id
        else db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    )
    if not candidate:
        return {"items": [], "total": 0, "page": page_number, "page_size": page_size}
    from app.services.recruitment import candidate_view

    if candidate_view(db, actor, candidate).get("blind"):
        return {"items": [], "total": 0, "page": page_number, "page_size": page_size}
    query = select(Document).where(
        Document.candidate_id == candidate.id, Document.scan_status != "DELETED",
    )
    if type_name:
        query = query.where(Document.type_name == type_name)
    elif not include_photo:
        query = query.where(Document.type_name != "FOTO_PERFIL")
    return page(
        db,
        query.order_by(Document.created_at.desc(), Document.id.desc()),
        page_number,
        page_size,
        document_view,
    )


@router.get("/documents/{document_id}/download")
def download(document_id: str, db: Db, actor: Current):
    row = db.get(Document, document_id)
    if not row or not row.candidate_id:
        raise DomainError("Documento não encontrado.", 404)
    candidate_access(db, actor, row.candidate_id)
    from app.services.recruitment import candidate_view

    candidate = db.get(Candidate, row.candidate_id)
    if candidate_view(db, actor, candidate).get("blind"):
        raise DomainError("Documento indisponível durante triagem sem identidade.", 403)
    if row.scan_status not in {"CLEAN", "NOT_CONFIGURED"}:
        raise DomainError("Arquivo aguardando validação.", 409)
    path = Path(settings().upload_dir) / row.storage_key
    if not path.is_file():
        raise DomainError("Arquivo indisponível.", 404)
    audit(db, actor, "document.downloaded", row)
    return FileResponse(path, media_type=row.mime, filename=row.filename)


class Review(StrictModel):
    version: int
    status: Literal["APPROVED", "REJECTED"]
    comment: str = ""


@router.put("/documents/{document_id}/review")
def review(document_id: str, body: Review, db: Db, actor: Current):
    actor.require("document.review")
    row = db.get(Document, document_id)
    if not row or not row.candidate_id:
        raise DomainError("Documento não encontrado.", 404)
    candidate_access(db, actor, row.candidate_id, "document.review")
    check_version(row, body.version)
    if body.status == "REJECTED" and len(body.comment.strip()) < 5:
        raise DomainError("Informe o motivo da rejeição.")
    before = serialize(row, {"storage_key"})
    row.status, row.comment, row.reviewed_by = body.status, body.comment, actor.user.id
    audit(db, actor, "document.reviewed", row, before, serialize(row, {"storage_key"}))
    candidate = db.get(Candidate, row.candidate_id)
    if candidate is None:
        raise DomainError("Candidato não encontrado.", 404)
    rejected = body.status == "REJECTED"
    notify(
        db, candidate.user_id,
        "Documento precisa de correção" if rejected else "Documento aprovado",
        "O RH analisou um documento. Acesse sua área de Documentos para consultar "
        + ("a justificativa e enviar a correção solicitada." if rejected else "o resultado."),
        "DOCUMENT", "/candidato/documentos",
    )
    return serialize(row, {"storage_key"})
