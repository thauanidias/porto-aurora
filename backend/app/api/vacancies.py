from copy import deepcopy
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field, model_validator
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, vacancy_access, vacancy_scope
from app.domain.rules import transition
from app.domain.scoring import validate_criteria
from app.models import (
    Application,
    Approval,
    ConfigRecord,
    OrgUnit,
    PipelineStage,
    ProcessForm,
    ScoringVersion,
    StageHistory,
    User,
    Vacancy,
    VacancyMessage,
    VacancyRequest,
)
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.schemas.vacancy_details import ApplicationQuestion
from app.schemas.recruitment import (
    ApprovalInput,
    PipelineInput,
    RequestInput,
    ScoreInput,
    StatusInput,
    VacancyInput,
    VacancyUpdate,
)
from app.services.candidate_journey import SECTIONS, CandidatePhase, application_permissions
from app.services.events import audit, event, notify
from app.services.recruitment import create_vacancy, publication_checklist, publish_direct
from app.services.workflow import decide, submit

router = APIRouter(tags=["Vagas e solicitações"])


class VacancyQuestionsInput(StrictModel):
    version: int = Field(ge=1)
    questions: list[ApplicationQuestion] = Field(max_length=20)

    @model_validator(mode="after")
    def valid_questions(self):
        if len({q.key for q in self.questions}) != len(self.questions):
            raise ValueError("Cada pergunta precisa ter um identificador diferente.")
        for question in self.questions:
            question.label = question.label.strip()
            if not 3 <= len(question.label) <= 500:
                raise ValueError("Escreva perguntas de 3 a 500 caracteres.")
            question.options = [option.strip() for option in question.options]
            if question.kind in {"SINGLE", "MULTIPLE"}:
                if not 2 <= len(question.options) <= 20 or any(not option or len(option) > 200 for option in question.options):
                    raise ValueError("Informe de 2 a 20 alternativas, com até 200 caracteres cada.")
                if len({option.casefold() for option in question.options}) != len(question.options):
                    raise ValueError("As alternativas não podem se repetir.")
            elif question.options:
                raise ValueError("Alternativas são usadas apenas em perguntas de escolha.")
        return self


@router.put("/vacancies/{vacancy_id}/questions")
def save_vacancy_questions(vacancy_id: str, body: VacancyQuestionsInput, db: Db, actor: Current):
    vacancy = vacancy_access(db, actor, vacancy_id, "vacancy.edit")
    db.scalar(select(Vacancy).where(Vacancy.id == vacancy.id).with_for_update())
    check_version(vacancy, body.version)
    if vacancy.status in {"CLOSED", "CANCELED", "ARCHIVED"}:
        raise DomainError("Reabra a vaga antes de alterar as perguntas.", 409)
    questions = [question.model_dump() for question in body.questions]
    vacancy.details = {**vacancy.details, "questions": questions}
    forms = db.scalars(select(ProcessForm).join(Application, Application.id == ProcessForm.application_id).where(
        Application.vacancy_id == vacancy.id, ProcessForm.status == "SENT", ProcessForm.encrypted_data == "").with_for_update()).all()
    for form in forms:
        form.questions = questions
    event(db, actor, "vacancy.questions_updated", vacancy, vacancy.id)
    return serialize(vacancy) | {"updated_unstarted_forms": len(forms)}


class CandidateFlowInput(StrictModel):
    version: int = Field(ge=1)
    phases: dict[str, CandidatePhase]


@router.put("/vacancies/{vacancy_id}/candidate-flow")
def configure_candidate_flow(vacancy_id: str, body: CandidateFlowInput, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id, "vacancy.edit")
    check_version(row, body.version)
    stages = db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == row.id)).all()
    if set(body.phases) != {stage.id for stage in stages}:
        raise DomainError("Configure somente as etapas existentes desta vaga.")
    applications = db.scalars(select(Application).where(Application.vacancy_id == row.id)).all()
    previous = {application.id: application_permissions(db, application)["permissions"] for application in applications}
    for stage in stages:
        stage.candidate_phase = body.phases[stage.id]
    row.updated_at = utcnow()
    event(db, actor, "candidate_flow.updated", row, row.id)
    for application in applications:
        released = [SECTIONS[key][1] for key, allowed in application_permissions(db, application)["permissions"].items()
                    if key in SECTIONS and allowed and not previous[application.id][key]]
        if released:
            from app.models import Candidate
            candidate = required(db, Candidate, application.candidate_id)
            notify(db, candidate.user_id, "Novas atividades liberadas", ", ".join(released),
                   "CANDIDATE", "/candidato/candidaturas/" + application.id)
    return {"message": "Liberação por etapas atualizada."}


def conversation_access(db, actor, vacancy_id):
    if actor.user.kind != "INTERNAL" or not ({"message.send", "request.create"} & actor.permissions):
        raise DomainError("Conversa restrita ao gestor e ao RH responsáveis pela vaga.", 403)
    return vacancy_access(db, actor, vacancy_id)


class VacancyMessageInput(StrictModel):
    body: str = Field(min_length=1, max_length=5000)


@router.get("/vacancies/{vacancy_id}/messages")
def vacancy_messages(vacancy_id: str, db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1):
    conversation_access(db, actor, vacancy_id)
    return page(db, select(VacancyMessage).where(VacancyMessage.vacancy_id == vacancy_id)
                .order_by(VacancyMessage.created_at.desc(), VacancyMessage.id.desc()), page_number, 25,
                lambda row: serialize(row) | {"sender_name": required(db, User, row.sender_id).name})


@router.post("/vacancies/{vacancy_id}/messages", status_code=201)
def send_vacancy_message(vacancy_id: str, body: VacancyMessageInput, db: Db, actor: Current):
    vacancy = conversation_access(db, actor, vacancy_id)
    content = body.body.strip()
    if not content:
        raise DomainError("Escreva uma mensagem antes de enviar.")
    row = VacancyMessage(vacancy_id=vacancy.id, sender_id=actor.user.id, body=content)
    db.add(row)
    audit(db, actor, "vacancy.message_sent", row, vacancy_id=vacancy.id)
    for recipient in {vacancy.manager_id, vacancy.recruiter_id} - {None, actor.user.id}:
        notify(db, recipient, "Nova mensagem na vaga", vacancy.title,
               "VACANCY_MESSAGE", "/app/vagas/" + vacancy.id + "?tab=messages")
    return serialize(row) | {"sender_name": actor.user.name}
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]


def request_view(db, actor, row):
    feedback = db.scalar(select(Approval).where(Approval.request_id == row.id)
                         .order_by(Approval.created_at.desc(), Approval.id.desc()))
    vacancy = db.scalar(select(Vacancy).where(Vacancy.request_id == row.id))
    step = row.workflow_snapshot[row.current_step] if row.workflow_snapshot else {}
    return serialize(row) | {
        "requested_by_name": required(db, User, row.requested_by).name,
        "org_unit_name": required(db, OrgUnit, row.org_unit_id).name,
        "rh_feedback": feedback.comment if feedback else "",
        "last_decision": feedback.decision if feedback else None,
        "vacancy_id": vacancy.id if vacancy else None,
        "can_decide": row.status == "PENDING_APPROVAL" and
            (step.get("delegate_id") or step.get("approver_id")) == actor.user.id,
    }


def request_workflow(db, selected=None):
    if selected:
        return selected
    ids = list(db.scalars(select(ConfigRecord.id).where(
        ConfigRecord.kind == "workflows", ConfigRecord.active.is_(True),
        ConfigRecord.data["target"].astext == "REQUEST",
    )))
    if len(ids) != 1:
        raise DomainError("Selecione o fluxo de análise do RH." if ids else
                          "O RH precisa configurar um fluxo de aprovação de solicitações antes do envio.", 422)
    return ids[0]


@router.get("/vacancy-request-workflows")
def request_workflows(db: Db, actor: Current, page_number: Page = 1, page_size: Size = 100):
    actor.require("request.create")
    return page(db, select(ConfigRecord).where(
        ConfigRecord.kind == "workflows", ConfigRecord.active.is_(True),
        ConfigRecord.data["target"].astext == "REQUEST",
    ).order_by(ConfigRecord.name), page_number, page_size,
        lambda row: {"id": row.id, "name": row.name})


@router.get("/vacancy-requests")
def requests(db: Db, actor: Current, q: str = "", page_number: Page = 1, page_size: Size = 25):
    if not {"request.create", "request.approve", "vacancy.all"} & actor.permissions:
        raise DomainError("Acesso não autorizado.", 403)
    query = select(VacancyRequest)
    if "vacancy.all" not in actor.permissions:
        query = query.where(
            or_(
                VacancyRequest.requested_by == actor.user.id,
                VacancyRequest.workflow_snapshot.contains([{"approver_id": actor.user.id}]),
                VacancyRequest.workflow_snapshot.contains([{"delegate_id": actor.user.id}]),
            )
        )
    return page(
        db,
        query.where(VacancyRequest.title.ilike("%" + q + "%")).order_by(
            VacancyRequest.created_at.desc()
        ),
        page_number,
        page_size,
        lambda row: request_view(db, actor, row),
    )


@router.post("/vacancy-requests", status_code=201)
def new_request(body: RequestInput, db: Db, actor: Current):
    actor.require("request.create")
    org = db.get(OrgUnit, body.org_unit_id)
    if not org or not org.active:
        raise DomainError("Selecione uma estrutura ativa.")
    if "vacancy.all" not in actor.permissions and actor.user.org_unit_id != org.id:
        raise DomainError("Solicite vagas somente para sua estrutura.", 403)
    if body.request_type == "REPLACEMENT" and not body.replaced_employee:
        raise DomainError("Informe o colaborador substituído.")
    row = VacancyRequest(
        title=body.title,
        org_unit_id=org.id,
        requested_by=actor.user.id,
        quantity=body.quantity,
        details=body.model_dump(exclude={"title", "org_unit_id", "quantity", "request_workflow_id"}),
    )
    db.add(row)
    event(db, actor, "request.created", row)
    return serialize(row)


@router.post("/vacancy-requests/send", status_code=201)
def send_request(body: RequestInput, db: Db, actor: Current):
    actor.require("request.create")
    workflow_id = request_workflow(db, body.request_workflow_id)
    created = new_request(body, db, actor)
    row = required(db, VacancyRequest, created["id"])
    submit(db, actor, row, workflow_id)
    db.flush()
    return request_view(db, actor, row)


def request_access(db, actor, request_id):
    row = db.scalar(select(VacancyRequest).where(VacancyRequest.id == request_id).with_for_update())
    if not row:
        raise DomainError("Solicitação não encontrada.", 404)
    approvers = {step.get("delegate_id") or step["approver_id"] for step in row.workflow_snapshot}
    if (
        row.requested_by != actor.user.id
        and "vacancy.all" not in actor.permissions
        and actor.user.id not in approvers
    ):
        raise DomainError("Solicitação não encontrada.", 404)
    return row


@router.get("/vacancy-requests/{request_id}")
def get_request(request_id: str, db: Db, actor: Current):
    return request_view(db, actor, request_access(db, actor, request_id))


class RequestUpdate(RequestInput):
    version: int = Field(ge=1)


@router.put("/vacancy-requests/{request_id}")
def edit_request(request_id: str, body: RequestUpdate, db: Db, actor: Current):
    actor.require("request.create")
    row = request_access(db, actor, request_id)
    if row.requested_by != actor.user.id and "vacancy.all" not in actor.permissions:
        raise DomainError("Somente o solicitante ou o RH pode editar este pedido.", 403)
    check_version(row, body.version)
    if row.status != "DRAFT":
        raise DomainError("Somente rascunhos ou solicitações devolvidas podem ser editados.", 409)
    org = db.get(OrgUnit, body.org_unit_id)
    if not org or not org.active or body.org_unit_id != row.org_unit_id:
        raise DomainError("Mantenha o setor da solicitação original ativo.", 422)
    if body.request_type == "REPLACEMENT" and not body.replaced_employee:
        raise DomainError("Informe o colaborador substituído.")
    row.title, row.quantity = body.title, body.quantity
    row.details = body.model_dump(exclude={"title", "org_unit_id", "quantity", "request_workflow_id", "version"})
    event(db, actor, "request.updated", row)
    return request_view(db, actor, row)


@router.post("/vacancy-requests/{request_id}/submit")
def submit_request(request_id: str, body: StatusInput, db: Db, actor: Current):
    row = request_access(db, actor, request_id)
    actor.require("request.create")
    check_version(row, body.version)
    submit(db, actor, row, request_workflow(db, body.workflow_id))
    return serialize(row)


@router.post("/vacancy-requests/{request_id}/approve")
def approve_request(request_id: str, body: ApprovalInput, db: Db, actor: Current):
    row = request_access(db, actor, request_id)
    check_version(row, body.version)
    decide(db, actor, row, body.decision, body.comment)
    db.flush()
    return serialize(row)


@router.post("/vacancy-requests/{request_id}/vacancy", status_code=201)
def convert_request(request_id: str, body: VacancyInput, db: Db, actor: Current):
    row = request_access(db, actor, request_id)
    if row.status != "APPROVED" or db.scalar(
        select(Vacancy.id).where(Vacancy.request_id == row.id)
    ):
        raise DomainError("Solicitação não aprovada ou já convertida.", 409)
    data = body.model_dump()
    if data["org_unit_id"] != row.org_unit_id or data["quantity"] != row.quantity:
        raise DomainError("Estrutura e quantidade devem corresponder à solicitação aprovada.")
    if data["manager_id"] != row.requested_by:
        raise DomainError("O gestor da vaga deve ser o solicitante para manter o acompanhamento.", 422)
    vacancy = create_vacancy(db, actor, data | {"request_id": row.id})
    vacancy.status = "APPROVED"
    row.status = "CONVERTED"
    event(db, actor, "request.converted", row, vacancy.id)
    notify(db, row.requested_by, "Sua solicitação virou uma vaga", row.title,
           "REQUEST", "/gestor/vagas/" + vacancy.id)
    if body.publish_on_save:
        publish_direct(db, actor, vacancy)
    return serialize(vacancy)


@router.get("/vacancies")
def vacancies(
    db: Db,
    actor: Current,
    q: str = "",
    status: str = "",
    audience: str = "",
    page_number: Page = 1,
    page_size: Size = 25,
):
    actor.require("vacancy.view")
    query = select(Vacancy).where(
        vacancy_scope(actor),
        or_(Vacancy.title.ilike("%" + q + "%"), Vacancy.code.ilike("%" + q + "%")),
    )
    if status:
        query = query.where(Vacancy.status == status)
    if audience:
        query = query.where(Vacancy.audience == audience)
    return page(db, query.order_by(Vacancy.created_at.desc()), page_number, page_size)


@router.post("/vacancies", status_code=201)
def new_vacancy(body: VacancyInput, db: Db, actor: Current):
    if not db.get(OrgUnit, body.org_unit_id):
        raise DomainError("Estrutura inválida.")
    row = create_vacancy(db, actor, body.model_dump())
    if body.publish_on_save:
        publish_direct(db, actor, row)
    return serialize(row)


@router.get("/vacancies/{vacancy_id}")
def get_vacancy(vacancy_id: str, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id)
    stages = db.scalars(
        select(PipelineStage)
        .where(PipelineStage.vacancy_id == row.id)
        .order_by(PipelineStage.position)
    )
    models = db.scalars(
        select(ScoringVersion)
        .where(ScoringVersion.vacancy_id == row.id)
        .order_by(ScoringVersion.number.desc())
    )
    return serialize(row) | {
        "org_unit_name": required(db, OrgUnit, row.org_unit_id).name,
        "recruiter_name": required(db, User, row.recruiter_id).name,
        "manager_name": required(db, User, row.manager_id).name,
        "stages": [serialize(s) for s in stages],
        "scoring_models": [serialize(m) for m in models],
        "checklist": publication_checklist(
            db, row, approval_required=not (
                row.status == "DRAFT" and "vacancy.publish" in actor.permissions
            )
        ),
    }


@router.put("/vacancies/{vacancy_id}")
def edit_vacancy(vacancy_id: str, body: VacancyUpdate, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id, "vacancy.edit")
    check_version(row, body.version)
    if row.status not in {"DRAFT", "APPROVED"}:
        raise DomainError(
            "Edite a vaga antes da publicação. Para reabrir, use o fluxo de reabertura.", 409
        )
    before = serialize(row)
    structured = row.details.get("structured_workflow", False)
    for key, value in body.model_dump(
        exclude={"version", "vacancy_template_id", "publish_on_save"}
    ).items():
        setattr(row, key, value)
    if structured:
        row.details = row.details | {"structured_workflow": True}
    audit(db, actor, "vacancy.updated", row, before=before, after=serialize(row), vacancy_id=row.id)
    db.flush()
    if body.publish_on_save:
        publish_direct(db, actor, row)
    return serialize(row)


@router.put("/vacancies/{vacancy_id}/pipeline")
def pipeline(vacancy_id: str, body: PipelineInput, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id, "vacancy.edit")
    check_version(row, body.version)
    if row.status not in {"DRAFT", "APPROVED"} or db.scalar(
        select(Application.id).where(Application.vacancy_id == row.id)
    ):
        raise DomainError("Pipeline com candidaturas não pode ser substituído.", 409)
    if len({s.position for s in body.stages}) != len(body.stages):
        raise DomainError("Posições das etapas devem ser únicas.")
    for stage in db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == row.id)):
        db.delete(stage)
    db.flush()
    for stage_input in body.stages:
        db.add(PipelineStage(vacancy_id=row.id, **stage_input.model_dump()))
    row.updated_at = utcnow()
    event(db, actor, "pipeline.updated", row, row.id)
    return {"message": "Pipeline salvo."}


@router.post("/vacancies/{vacancy_id}/scoring-models", status_code=201)
def scoring(vacancy_id: str, body: ScoreInput, db: Db, actor: Current):
    vacancy_access(db, actor, vacancy_id, "score.manage")
    if body.bands:
        import math
        bands = {b.get("key"): b for b in body.bands}
        try:
            moderate, high = float(bands["moderate"]["min"]), float(bands["high"]["min"])
            valid = len(body.bands) == 3 and set(bands) == {"low", "moderate", "high"} and math.isfinite(moderate) and math.isfinite(high) and 0 < moderate < high <= 100
            valid = valid and float(bands["low"]["min"]) == 0 and float(bands["low"]["max"]) == moderate and float(bands["moderate"]["max"]) == high and float(bands["high"]["max"]) == 100
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise DomainError("Configure as três faixas: baixa de 0 até moderada, moderada até alta e alta até 100.")
    db.scalar(select(Vacancy).where(Vacancy.id == vacancy_id).with_for_update())
    criteria = [
        rule.model_dump() for rule in validate_criteria([c.model_dump() for c in body.criteria])
    ]
    if (
        set(body.composition) - {"OBJECTIVE", "TEST", "RH", "MANAGER", "TECHNICAL"}
        or sum(body.composition.values()) != 100
        or any(not 0 <= n <= 100 for n in body.composition.values())
    ):
        raise DomainError("Composição deve somar 100% com componentes válidos.")
    number = (
        db.scalar(
            select(func.max(ScoringVersion.number)).where(ScoringVersion.vacancy_id == vacancy_id)
        )
        or 0
    ) + 1
    model = ScoringVersion(
        vacancy_id=vacancy_id,
        number=number,
        criteria=criteria,
        composition=body.composition,
        bands=body.bands,
        reason=body.reason,
        created_by=actor.user.id,
    )
    db.add(model)
    event(db, actor, "scoring_model.versioned", model, vacancy_id)
    return serialize(model)


class CompatibilityRecalculation(StrictModel):
    reason: str = Field(min_length=10, max_length=2000)


@router.post("/vacancies/{vacancy_id}/suggest-compatibility-criteria")
def suggest_compatibility_criteria(vacancy_id: str, db: Db, actor: Current):
    from app.services.curriculum_matching import suggest_vacancy_criteria
    vacancy = vacancy_access(db, actor, vacancy_id, "score.manage")
    return suggest_vacancy_criteria(vacancy)


@router.post("/vacancies/{vacancy_id}/recalculate-compatibility")
def recalculate_compatibility(vacancy_id: str, body: CompatibilityRecalculation, db: Db, actor: Current):
    from app.services.recruitment import calculate_application

    vacancy = vacancy_access(db, actor, vacancy_id, "score.manage")
    model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == vacancy_id)
                      .order_by(ScoringVersion.number.desc()).limit(1))
    if not model or not any(not c.get("not_applicable") for c in model.criteria):
        raise DomainError("Configure os critérios profissionais da vaga antes de calcular a compatibilidade.")
    applications = list(db.scalars(select(Application).where(Application.vacancy_id == vacancy_id,
        Application.status.in_(["ACTIVE", "RESERVE"]))
        .order_by(Application.id).with_for_update()))
    for application in applications:
        calculate_application(db, actor, application, model)
    audit(db, actor, "vacancy.compatibility_recalculated", vacancy,
          after={"model_id": model.id, "count": len(applications), "reason": body.reason}, vacancy_id=vacancy_id)
    return {"updated": len(applications)}


@router.post("/vacancies/{vacancy_id}/status")
def vacancy_status(vacancy_id: str, body: StatusInput, db: Db, actor: Current):
    permission = "vacancy.publish" if body.status == "PUBLISHED" else "vacancy.edit"
    row = vacancy_access(db, actor, vacancy_id, permission)
    check_version(row, body.version)
    if body.status == "PUBLISHED" and row.status == "DRAFT":
        publish_direct(db, actor, row)
        return serialize(row)
    transition(row.status, body.status)
    if body.status == "PENDING_APPROVAL":
        submit(db, actor, row, body.workflow_id or "")
    else:
        if body.status == "PUBLISHED":
            failed = [item["label"] for item in publication_checklist(db, row) if not item["ok"]]
            if failed:
                raise DomainError("Pendências para publicar: " + ", ".join(failed))
            row.published_at = row.published_at or utcnow()
        if (
            body.status in {"CLOSED", "CANCELED", "ARCHIVED", "DRAFT"}
            and len(body.reason.strip()) < 5
        ):
            raise DomainError("Informe o motivo desta ação.")
        if body.status in {"CLOSED", "CANCELED"}:
            row.closed_at = utcnow()
            for application in db.scalars(
                select(Application).where(
                    Application.vacancy_id == row.id, Application.status.in_(["ACTIVE", "RESERVE"])
                )
            ):
                application.status = "REJECTED"
                application.closure_reason = body.reason
                application.closed_at = utcnow()
                for history in db.scalars(
                    select(StageHistory).where(
                        StageHistory.application_id == application.id,
                        StageHistory.left_at.is_(None),
                    )
                ):
                    history.left_at = application.closed_at
                event(db, actor, "application.closed", application, row.id)
            row.details = row.details | {
                "closure_reason": body.reason,
                "filled": db.scalar(
                    select(func.count())
                    .select_from(Application)
                    .where(Application.vacancy_id == row.id, Application.status == "HIRED")
                ),
            }
        row.status = body.status
        if row.status == "PUBLISHED":
            from app.services.talent_bank import enroll_talents
            enroll_talents(db, actor, row)
        event(db, actor, "vacancy.status_changed", row, row.id)
    db.flush()
    return serialize(row)


@router.post("/vacancies/{vacancy_id}/approve")
def approve_vacancy(vacancy_id: str, body: ApprovalInput, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id, "vacancy.approve")
    check_version(row, body.version)
    decide(db, actor, row, body.decision, body.comment)
    db.flush()
    return serialize(row)


@router.post("/vacancies/{vacancy_id}/clone", status_code=201)
def clone(vacancy_id: str, db: Db, actor: Current):
    row = vacancy_access(db, actor, vacancy_id, "vacancy.create")
    fields = set(VacancyInput.model_fields) - {"vacancy_template_id", "publish_on_save"}
    data = {key: deepcopy(getattr(row, key)) for key in fields}
    data["title"] = data["title"][:172] + " (cópia)"
    data["deadline"] = utcnow() + timedelta(days=30)
    cloned = create_vacancy(db, actor, data)
    for stage in db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == row.id)):
        db.add(
            PipelineStage(
                vacancy_id=cloned.id,
                **{
                    k: deepcopy(getattr(stage, k))
                    for k in (
                        "name",
                        "position",
                        "kind",
                        "candidate_phase",
                        "required",
                        "reveal_identity",
                        "sla_hours",
                        "rules",
                    )
                },
            )
        )
    model = db.scalar(
        select(ScoringVersion)
        .where(ScoringVersion.vacancy_id == row.id)
        .order_by(ScoringVersion.number.desc())
        .limit(1)
    )
    if model:
        db.add(
            ScoringVersion(
                vacancy_id=cloned.id,
                number=1,
                criteria=deepcopy(model.criteria),
                composition=deepcopy(model.composition),
                bands=deepcopy(model.bands),
                reason="Clonagem da vaga " + row.code,
                created_by=actor.user.id,
            )
        )
    return serialize(cloned)
