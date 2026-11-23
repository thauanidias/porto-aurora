from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import (
    Current,
    Db,
    application_access,
    is_manager,
    sector_finalist_ids,
    vacancy_access,
    vacancy_scope,
)
from app.domain.rules import matches
from app.models import (
    Application,
    ApplicationScore,
    Candidate,
    ChecklistItem,
    ConfigRecord,
    Consent,
    Evaluation,
    Message,
    Offer,
    PipelineStage,
    ScoringVersion,
    StageHistory,
    StageReview,
    User,
    Vacancy,
)
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.schemas.recruitment import ApplicationInput, DecisionInput, MoveInput
from app.services.candidate_journey import application_permissions, require_application_section
from app.services.compatibility import compatibility_summary
from app.services.events import audit, event, notify
from app.services.recruitment import apply, calculate_application, candidate_view, move

router = APIRouter(tags=["Candidaturas"])


@router.post("/applications/{application_id}/curriculum-analysis")
def curriculum_analysis(application_id: str, db: Db, actor: Current):
    from app.services.curriculum_matching import analyze_curriculum

    application = application_access(db, actor, application_id, "score.manage")
    vacancy = vacancy_access(db, actor, application.vacancy_id, "score.manage")
    candidate = required(db, Candidate, application.candidate_id)
    if candidate.anonymized_at or candidate.merged_into_id or candidate_view(db, actor, candidate, application).get("blind"):
        raise DomainError("O perfil não está disponível para análise curricular nesta etapa.", 409)
    if db.scalar(select(Evaluation.id).where(Evaluation.application_id == application.id,
            Evaluation.independent.is_(True), Evaluation.submitted_at.is_(None))):
        raise DomainError("Aguarde a conclusão das avaliações independentes.", 409)
    model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == vacancy.id)
                      .order_by(ScoringVersion.number.desc()).limit(1))
    if not model:
        raise DomainError("Configure os critérios e pesos da vaga antes de analisar.", 409)
    analysis = analyze_curriculum(db, application, vacancy, model)
    score = calculate_application(db, actor, application, model, curriculum_analysis=analysis)
    audit(db, actor, "application.curriculum_analyzed", application,
          after={"model_id": model.id, "score_id": score.id, "document_id": analysis["document_id"]}, vacancy_id=vacancy.id)
    return analysis


@router.get("/applications/{application_id}/curriculum-analysis/history")
def curriculum_analysis_history(application_id: str, db: Db, actor: Current):
    application = application_access(db, actor, application_id, "score.manage")
    candidate = required(db, Candidate, application.candidate_id)
    if candidate_view(db, actor, candidate, application).get("blind"):
        raise DomainError("Histórico indisponível durante a avaliação às cegas.", 403)
    if db.scalar(select(Evaluation.id).where(Evaluation.application_id == application.id,
            Evaluation.independent.is_(True), Evaluation.submitted_at.is_(None))):
        raise DomainError("Aguarde a conclusão das avaliações independentes.", 409)
    entries = db.scalars(select(ApplicationScore).where(ApplicationScore.application_id == application.id)
                        .order_by(ApplicationScore.created_at.desc(), ApplicationScore.id.desc()).limit(50))
    return {"items": [{"id": score.id, "created_at": score.created_at, "model_id": score.model_id,
                       "analysis": score.breakdown["curriculum_analysis"]}
                      for score in entries if score.breakdown.get("curriculum_analysis")]}


def prime_application_views(db, rows):
    # Retain batch-loaded identities for SQLAlchemy's per-request identity map.
    db.info["application_view_refs"] = [
        *db.scalars(select(Candidate).where(Candidate.id.in_({r.candidate_id for r in rows}))),
        *db.scalars(select(Vacancy).where(Vacancy.id.in_({r.vacancy_id for r in rows}))),
        *db.scalars(select(PipelineStage).where(PipelineStage.id.in_({r.stage_id for r in rows}))),
    ]
    ids = {r.id for r in rows}
    current_stages = {r.id: r.stage_id for r in rows}
    latest_reviews = {}
    for review in db.scalars(select(StageReview).where(StageReview.application_id.in_(ids))
            .order_by(StageReview.created_at.desc(), StageReview.id.desc())):
        if review.stage_id == current_stages.get(review.application_id):
            latest_reviews.setdefault(review.application_id, {"status": review.status, "reviewed_at": review.created_at})
    db.info["application_screening_reviews"] = latest_reviews
    scores: dict[str, ApplicationScore] = {}
    for score in db.scalars(select(ApplicationScore).where(ApplicationScore.application_id.in_(ids))
                           .order_by(ApplicationScore.created_at.desc(), ApplicationScore.id.desc())):
        scores.setdefault(score.application_id, score)
    models: dict[str, ScoringVersion] = {}
    for model in db.scalars(select(ScoringVersion).where(
            ScoringVersion.vacancy_id.in_({r.vacancy_id for r in rows})).order_by(ScoringVersion.number.desc())):
        models.setdefault(model.vacancy_id, model)
    sealed = set(db.scalars(select(Evaluation.application_id).where(
        Evaluation.application_id.in_(ids), Evaluation.independent.is_(True), Evaluation.submitted_at.is_(None))))
    db.info["application_compatibility"] = {
        r.id: compatibility_summary(scores.get(r.id), models.get(r.vacancy_id), r.id in sealed)
        for r in rows
    }


def application_view(db, actor, row):
    candidate = required(db, Candidate, row.candidate_id)
    vacancy = db.get(Vacancy, row.vacancy_id)
    stage = db.get(PipelineStage, row.stage_id)
    result = serialize(row)
    result.update(
        {
            "candidate": candidate_view(db, actor, candidate, row),
            "vacancy_title": vacancy.title,
            "stage_name": stage.name,
            "candidate_access": application_permissions(db, row),
        }
    )
    if result["candidate"].get("blind"):
        for key in ("profile_snapshot", "answers", "cv_id", "utm"):
            result.pop(key, None)
    if candidate.user_id == actor.user.id:
        from app.services.admission_documents import candidate_documents_complete
        result["documents_welcome_ready"] = bool(result["candidate_access"]["permissions"]["admission"] and candidate_documents_complete(db, candidate.id))
        from app.models import ProcessForm
        result["process_form_status"] = db.scalar(select(ProcessForm.status).where(ProcessForm.application_id == row.id)) or "NOT_SENT"
        result.pop("test_questionnaire", None)
        result.pop("profile_snapshot", None)
        result.pop("closure_reason", None)
        result["return_available"] = bool(
            row.status == "WITHDRAWN"
            and vacancy.status == "PUBLISHED"
            and vacancy.deadline
            and vacancy.deadline > utcnow()
            and vacancy.details.get("allow_withdrawal_return")
        )
        result["notice_id"] = vacancy.details.get("notice_id")
        result["candidate_access"] = application_permissions(db, row)
        result["selection_questions"] = [{k: v for k, v in question.items()
            if k in {"key", "label", "kind", "required", "options"}}
            for question in vacancy.details.get("questions", [])]
    elif "candidate.view" in actor.permissions:
        if "application_screening_reviews" in db.info:
            result["screening_review"] = db.info["application_screening_reviews"].get(row.id)
        else:
            review = db.scalar(select(StageReview).where(StageReview.application_id == row.id, StageReview.stage_id == row.stage_id)
                .order_by(StageReview.created_at.desc(), StageReview.id.desc()).limit(1))
            result["screening_review"] = {"status": review.status, "reviewed_at": review.created_at} if review else None
        cached = db.info.get("application_compatibility", {})
        if row.id in cached:
            result["compatibility"] = cached[row.id]
        else:
            score = db.scalar(select(ApplicationScore).where(ApplicationScore.application_id == row.id)
                              .order_by(ApplicationScore.created_at.desc(), ApplicationScore.id.desc()).limit(1))
            model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == row.vacancy_id)
                              .order_by(ScoringVersion.number.desc()).limit(1))
            sealed = db.scalar(select(Evaluation.id).where(Evaluation.application_id == row.id,
                Evaluation.independent.is_(True), Evaluation.submitted_at.is_(None))) is not None
            result["compatibility"] = compatibility_summary(score, model, sealed)
    if result["candidate"].get("blind") and result.get("compatibility", {}).get("curriculum"):
        result["compatibility"] = {**result["compatibility"], "curriculum": None}
    if result.get("compatibility", {}).get("curriculum"):
        from app.models import Document
        report = result["compatibility"]["curriculum"]
        doc = db.get(Document, row.cv_id) if row.cv_id else None
        if not doc or report.get("document_sha256") != doc.sha256 or report.get("vacancy_updated_at") != vacancy.updated_at.isoformat():
            result["compatibility"] = {**result["compatibility"], "curriculum": {**report, "status": "OUTDATED"}}
    return result


@router.get("/applications")
def applications(
    db: Db,
    actor: Current,
    vacancy_id: str = "",
    candidate_id: str = "",
    recruitment_type: Literal["INTERNAL", "EXTERNAL"] | None = None,
    q: str = "",
    status: str = "",
    stage_id: str = "",
    screening_only: bool = False,
    order_by: Literal["recent", "compatibility"] = "recent",
    include_ranking: bool = False,
    group_by_vacancy: bool = False,
    passed_screening: bool = False,
    registered_from: datetime | None = None,
    registered_to: datetime | None = None,
    page_number: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    query = select(Application)
    if actor.user.kind == "CANDIDATO" or "candidate.view" not in actor.permissions:
        query = query.join(Candidate).where(Candidate.user_id == actor.user.id)
    else:
        actor.require("candidate.view")
        assigned = select(Evaluation.application_id).where(Evaluation.evaluator_id == actor.user.id)
        query = query.where(
            (Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))))
            | Application.id.in_(assigned)
            | (Application.id.in_(sector_finalist_ids(actor)) if is_manager(actor) else False)
        )
    ranking_scope = query
    if vacancy_id:
        query = query.where(Application.vacancy_id == vacancy_id)
    if candidate_id:
        query = query.where(Application.candidate_id == candidate_id)
    if recruitment_type:
        query = query.where(Application.recruitment_type == recruitment_type)
    if status:
        query = query.where(Application.status == status)
    if stage_id:
        query = query.where(Application.stage_id == stage_id)
    if screening_only:
        from app.services.candidate_journey import stage_phase
        screening_stages = [stage.id for stage in db.scalars(select(PipelineStage).where(
            PipelineStage.vacancy_id == vacancy_id) if vacancy_id else select(PipelineStage))
            if stage_phase(db, stage) == "SELECTION"]
        query = query.where(Application.stage_id.in_(screening_stages))
    if passed_screening:
        from app.services.candidate_journey import stage_phase
        pipeline = list(db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy_id)
                                  if vacancy_id else select(PipelineStage)))
        screened_stages = [stage.id for stage in pipeline if stage_phase(db, stage) == "SELECTION"]
        later_stages = [stage.id for stage in pipeline if stage_phase(db, stage) in {"FORM", "INTERVIEW", "TEST", "ADMISSION"}]
        latest_review = select(StageReview.status).where(
            StageReview.application_id == Application.id, StageReview.stage_id.in_(screened_stages),
        ).order_by(StageReview.created_at.desc(), StageReview.id.desc()).limit(1).correlate(Application).scalar_subquery()
        passed = (Application.stage_id.in_(later_stages)
                  & Application.status.in_(["ACTIVE", "RESERVE", "SELECTED", "PRE_ADMISSION", "HIRED"])
                  & (latest_review == "APPROVED"))
        query = query.where(passed)
        ranking_scope = ranking_scope.where(passed)
    if any(value and value.tzinfo is None for value in (registered_from, registered_to)):
        raise DomainError("Informe o fuso horário no período de cadastro.")
    if registered_from and registered_to and registered_from > registered_to:
        raise DomainError("O início do período deve ser anterior ao fim.")
    if registered_from:
        query = query.where(Application.created_at >= registered_from)
    if registered_to:
        query = query.where(Application.created_at <= registered_to)
    if q:
        query = query.where(or_(
            Application.candidate_id.in_(select(Candidate.id).where(Candidate.name.ilike("%" + q + "%"))),
            Application.vacancy_id.in_(select(Vacancy.id).where(Vacancy.title.ilike("%" + q + "%"))),
        ))
    if group_by_vacancy:
        actor.require("candidate.view")
        counts = dict(db.execute(select(Application.vacancy_id, func.count()).where(
            Application.id.in_(query.with_only_columns(Application.id))).group_by(Application.vacancy_id)).all())
        jobs = select(Vacancy).where(Vacancy.id.in_(counts)).order_by(Vacancy.created_at.desc(), Vacancy.id)
        return page(db, jobs, page_number, page_size, lambda job: {
            "id": job.id, "title": job.title, "code": job.code, "status": job.status,
            "audience": job.audience, "application_count": counts[job.id],
        })
    stage_counts: dict[str, int] = {stage: count for stage, count in db.execute(select(Application.stage_id, func.count())
        .where(Application.id.in_(query.with_only_columns(Application.id)))
        .group_by(Application.stage_id)).all()}
    if order_by == "compatibility":
        from app.services.compatibility import rank_compatibility
        actor.require("candidate.view")
        if not vacancy_id:
            raise DomainError("Escolha uma vaga para consultar o ranking de compatibilidade.")
        records = list(db.scalars(query.order_by(Application.id)))
        prime_application_views(db, records)
        ranked = rank_compatibility([application_view(db, actor, row) for row in records])
        start = (page_number - 1) * page_size
        return {"items": ranked[start:start + page_size], "total": len(ranked), "page": page_number,
                "page_size": page_size, "stage_counts": stage_counts}
    result = page(
        db,
        query.order_by(Application.created_at.desc()),
        page_number,
        page_size,
        lambda row: application_view(db, actor, row),
        prepare=lambda rows: prime_application_views(db, rows),
    ) | {"stage_counts": stage_counts}
    if include_ranking:
        from app.services.compatibility import rank_compatibility
        actor.require("candidate.view")
        vacancy_ids = {item["vacancy_id"] for item in result["items"]}
        rank_query = ranking_scope.where(Application.vacancy_id.in_(vacancy_ids),
                                        Application.status.in_(["ACTIVE", "RESERVE"]))
        if recruitment_type:
            rank_query = rank_query.where(Application.recruitment_type == recruitment_type)
        records = list(db.scalars(rank_query))
        prime_application_views(db, records)
        groups: dict[tuple[str, str], list[dict]] = {}
        for record in records:
            groups.setdefault((record.vacancy_id, record.recruitment_type), []).append(application_view(db, actor, record))
        positions = {item["id"]: item["compatibility_rank"] for group in groups.values() for item in rank_compatibility(group)}
        for item in result["items"]:
            item["compatibility_rank"] = positions.get(item["id"])
    return result


@router.post("/applications", status_code=201)
def create_application(body: ApplicationInput, db: Db, actor: Current):
    return application_view(db, actor, apply(db, actor, body))


class SelectionAnswers(StrictModel):
    version: int = Field(ge=1)
    answers: dict
    consent: bool


class QuestionAnswers(StrictModel):
    version: int = Field(ge=1)
    answers: dict


def validate_question_answers(questions, answers):
    if set(answers) - {q["key"] for q in questions}:
        raise DomainError("Há respostas para perguntas inexistentes.")
    for question in questions:
        value = answers.get(question["key"])
        if question.get("required") and value in (None, "", []):
            raise DomainError("Responda a pergunta: " + question["label"])
        if value is None or value == "":
            continue
        kind = question.get("kind")
        if (kind == "BOOLEAN" and type(value) is not bool
            or kind == "NUMBER" and (type(value) not in {int, float} or not __import__("math").isfinite(value))
            or kind == "TEXT" and (not isinstance(value, str) or len(value) > 10000)
            or kind == "SINGLE" and value not in question.get("options", [])
            or kind == "MULTIPLE" and (not isinstance(value, list) or any(v not in question.get("options", []) for v in value))):
            raise DomainError("Resposta inválida: " + question["label"])


@router.put("/applications/{application_id}/questions")
def save_questions(application_id: str, body: QuestionAnswers, db: Db, actor: Current):
    from app.models import ConsentReceipt
    row = application_access(db, actor, application_id)
    candidate = required(db, Candidate, row.candidate_id)
    if candidate.user_id != actor.user.id:
        raise DomainError("Somente o candidato pode preencher suas respostas.", 403)
    require_application_section(db, row, "questions")
    check_version(row, body.version)
    vacancy = required(db, Vacancy, row.vacancy_id)
    validate_question_answers(vacancy.details.get("questions", []), body.answers)
    receipt = db.scalar(select(ConsentReceipt.id).where(ConsentReceipt.user_id == actor.user.id,
        ConsentReceipt.context.in_(["CADASTRO", "CANDIDATURA"])))
    notice = db.get(ConfigRecord, vacancy.details.get("notice_id"))
    if not receipt or not notice or not notice.active:
        raise DomainError("Aceite o termo de consentimento em Meu perfil antes de enviar as respostas.")
    row.answers = body.answers
    event(db, actor, "application.questions_completed", row, row.vacancy_id)
    calculate_application(db, actor, row)
    notify(db, vacancy.recruiter_id, "Perguntas da vaga respondidas", vacancy.title,
           "CANDIDATE", "/app/candidaturas/" + row.id)
    db.flush()
    return application_view(db, actor, row)


@router.put("/applications/{application_id}/selection")
def save_selection(application_id: str, body: SelectionAnswers, db: Db, actor: Current):
    from app.models import ConsentReceipt
    row = application_access(db, actor, application_id)
    candidate = required(db, Candidate, row.candidate_id)
    if candidate.user_id != actor.user.id:
        raise DomainError("Somente o candidato pode preencher suas respostas.", 403)
    require_application_section(db, row, "selection_registration")
    check_version(row, body.version)
    vacancy = required(db, Vacancy, row.vacancy_id)
    if body.answers:
        require_application_section(db, row, "questions")
        validate_question_answers(vacancy.details.get("questions", []), body.answers)
    receipt = db.scalar(select(ConsentReceipt.id).where(ConsentReceipt.user_id == actor.user.id,
        ConsentReceipt.context.in_(["CADASTRO", "CANDIDATURA"])))
    notice = db.get(ConfigRecord, vacancy.details.get("notice_id"))
    if not body.consent or not receipt or not notice or not notice.active:
        raise DomainError("Leia e aceite o termo de consentimento antes de confirmar a candidatura.")
    if body.answers:
        row.answers = body.answers
    row.profile_snapshot = candidate.profile.copy()
    if not row.cv_id:
        from app.models import Document
        row.cv_id = db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
            Document.type_name == "CURRICULO", Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"]))
            .order_by(Document.created_at.desc()).limit(1))
    db.add(Consent(candidate_id=candidate.id, notice_id=notice.id, notice_version=notice.version,
        notice_snapshot=notice.data, purpose="RECRUITMENT", granted=True, ip=actor.ip))
    event(db, actor, "application.selection_completed", row, row.vacancy_id)
    calculate_application(db, actor, row)
    notify(db, vacancy.recruiter_id, "Seleção confirmada pelo candidato", vacancy.title,
           "CANDIDATE", "/app/candidaturas/" + row.id)
    db.flush()
    return application_view(db, actor, row)


@router.get("/applications/{application_id}")
def application_detail(application_id: str, db: Db, actor: Current):
    row = application_access(db, actor, application_id)
    candidate = required(db, Candidate, row.candidate_id)
    own = candidate.user_id == actor.user.id
    history = db.scalars(
        select(StageHistory)
        .where(StageHistory.application_id == row.id)
        .order_by(StageHistory.entered_at)
    )
    result = application_view(db, actor, row) | {
        "history": [
            serialize(h, {"reason", "changed_by"} if own else set())
            | {"stage_name": required(db, PipelineStage, h.stage_id).name}
            | ({} if own else {"changed_by_name": "Candidato" if required(db, User, h.changed_by).kind == "CANDIDATO" else required(db, User, h.changed_by).name})
            for h in history
        ]
    }
    if not own:
        audit(db, actor, "candidate.accessed", candidate, vacancy_id=row.vacancy_id)
        result["scores"] = [
            serialize(s)
            for s in db.scalars(
                select(ApplicationScore)
                .where(ApplicationScore.application_id == row.id)
                .order_by(ApplicationScore.created_at.desc())
            )
        ]
    if not own and db.scalar(
        select(Evaluation.id).where(
            Evaluation.application_id == row.id,
            Evaluation.independent.is_(True),
            Evaluation.submitted_at.is_(None),
        )
    ):
        for score in result["scores"]:
            detail = score["breakdown"]
            score["total"] = None
            score["sealed"] = True
            score["breakdown"] = {
                key: value for key, value in detail.items() if key not in {"total", "components"}
            }
    return result


class BulkMoveItem(MoveInput):
    id: str


class BulkMove(StrictModel):
    moves: list[BulkMoveItem] = Field(min_length=1, max_length=100)


@router.post("/applications/bulk/move")
def bulk_move(body: BulkMove, db: Db, actor: Current):
    results = []
    for item in body.moves:
        row = application_access(db, actor, item.id, "candidate.move")
        check_version(row, item.version)
        results.append(move(db, actor, row, item.stage_id, item.reason, item.override).id)
    return {"updated": results}


@router.post("/applications/{application_id}/move")
def move_application(application_id: str, body: MoveInput, db: Db, actor: Current):
    row = application_access(db, actor, application_id, "candidate.move")
    check_version(row, body.version)
    move(db, actor, row, body.stage_id, body.reason, body.override)
    db.flush()
    return application_view(db, actor, row)


class Recalculate(StrictModel):
    model_id: str
    reason: str = Field(min_length=10)


@router.post("/applications/{application_id}/recalculate")
def recalculate(application_id: str, body: Recalculate, db: Db, actor: Current):
    row = application_access(db, actor, application_id, "score.manage")
    actor.require("score.manage")
    model = db.get(ScoringVersion, body.model_id)
    if not model or model.vacancy_id != row.vacancy_id:
        raise DomainError("Modelo não pertence à vaga.")
    score = calculate_application(db, actor, row, model)
    audit(
        db,
        actor,
        "score.recalculated",
        score,
        after={"reason": body.reason, "model_id": model.id},
        vacancy_id=row.vacancy_id,
    )
    return serialize(score)


@router.post("/applications/{application_id}/decision")
def decision(application_id: str, body: DecisionInput, db: Db, actor: Current):
    row = application_access(db, actor, application_id)
    check_version(row, body.version)
    candidate = required(db, Candidate, row.candidate_id)
    if body.send_rejection_email and body.decision != "REJECTED":
        raise DomainError("Selecione a decisão Não selecionada para enviar este retorno.")
    if body.decision == "WITHDRAWN":
        if candidate.user_id != actor.user.id:
            raise DomainError("Somente o candidato pode retirar sua candidatura.", 403)
    else:
        actor.require("candidate.select")
        vacancy_access(db, actor, row.vacancy_id, "candidate.select")
    if body.decision != "WITHDRAWN" and len(body.reason.strip()) < 5:
        raise DomainError("Registre a justificativa da decisão.")
    if row.status in {"REJECTED", "WITHDRAWN", "HIRED"}:
        raise DomainError("Candidatura já encerrada.", 409)
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == row.vacancy_id).with_for_update())
    if vacancy is None:
        raise DomainError("Vaga não encontrada.", 404)
    if body.decision == "SELECTED":
        selected = (
            db.scalar(
                select(func.count())
                .select_from(Application)
                .where(
                    Application.vacancy_id == row.vacancy_id,
                    Application.status.in_(["SELECTED", "PRE_ADMISSION", "HIRED"]),
                )
            )
            or 0
        )
        if row.status in {"SELECTED", "PRE_ADMISSION", "HIRED"}:
            raise DomainError("Candidato já selecionado.", 409)
        if selected >= vacancy.quantity:
            raise DomainError("Todas as posições já foram preenchidas ou reservadas.", 409)
        required_stages = {
            stage.id
            for stage in db.scalars(
                select(PipelineStage).where(
                    PipelineStage.vacancy_id == row.vacancy_id, PipelineStage.required.is_(True)
                )
            )
            if matches(stage.rules, row.profile_snapshot.get("facts", {}))
        }

        complete = set(
            db.scalars(
                select(StageHistory.stage_id).where(
                    StageHistory.application_id == row.id, StageHistory.left_at.is_not(None)
                )
            )
        )
        latest_score = db.scalar(
            select(ApplicationScore)
            .where(ApplicationScore.application_id == row.id)
            .order_by(ApplicationScore.created_at.desc())
            .limit(1)
        )
        if (required_stages - complete or (latest_score and latest_score.knockout)) and not (
            body.override and vacancy.details.get("allow_override") and len(body.reason) >= 10
        ):
            raise DomainError("Conclua as etapas obrigatórias antes da seleção.", 409)
        row.selected_at = utcnow()
    if body.decision == "HIRED":
        accepted = db.scalar(
            select(Offer.id).where(Offer.application_id == row.id, Offer.status == "ACCEPTED")
        )
        pending = db.scalar(
            select(ChecklistItem.id).where(
                ChecklistItem.application_id == row.id,
                ChecklistItem.required.is_(True),
                ChecklistItem.status != "APPROVED",
            )
        )
        if not accepted or pending:
            raise DomainError("Conclua o aceite da oferta e a pré-admissão.", 409)
    if body.decision == "REJECTED" and len(body.reason.strip()) < 5:
        raise DomainError("Informe o motivo do encerramento.")
    if body.override:
        audit(
            db,
            actor,
            "decision.override",
            row,
            after={"reason": body.reason, "decision": body.decision},
            vacancy_id=row.vacancy_id,
        )
    row.status = body.decision
    if body.send_rejection_email:
        from app.services.rejection_feedback import queue_feedback
        queue_feedback(db, actor, row, candidate, vacancy, body=body.rejection_email_body)
    if body.decision != "WITHDRAWN" and len(body.reason.strip()) < 5:
        raise DomainError("Registre a justificativa da decisão.")
    if row.status in {"REJECTED", "WITHDRAWN", "HIRED"}:
        row.closed_at = utcnow()
        row.closure_reason = body.reason
        for history in db.scalars(
            select(StageHistory).where(
                StageHistory.application_id == row.id, StageHistory.left_at.is_(None)
            )
        ):
            history.left_at = utcnow()
    remaining_rejected = 0
    if body.decision == "SELECTED" and selected + 1 == vacancy.quantity:
        from app.services.rejection_feedback import reject_remaining
        remaining_rejected = reject_remaining(db, actor, vacancy)
    event(
        db,
        actor,
        "candidate.hired" if row.status == "HIRED" else "application.decision",
        row,
        row.vacancy_id,
    )
    db.flush()
    return serialize(row) | {"remaining_rejected": remaining_rejected}


class MessageInput(StrictModel):
    subject: str = Field(min_length=2, max_length=180)
    body: str = Field(min_length=1, max_length=10000)
    visibility: str = "CANDIDATE"


class RejectionEmailInput(StrictModel):
    subject: str = Field(min_length=2, max_length=180, pattern=r"^[^\r\n]+$")
    body: str = Field(min_length=10, max_length=10000)


@router.get("/applications/{application_id}/rejection-email")
def rejection_email(application_id: str, db: Db, actor: Current):
    actor.require("message.send")
    application = application_access(db, actor, application_id)
    vacancy_access(db, actor, application.vacancy_id, "message.send")
    from app.services.rejection_feedback import feedback_entry, feedback_template
    from app.services.smtp_config import smtp_runtime
    vacancy = required(db, Vacancy, application.vacancy_id)
    entry = feedback_entry(db, application)
    config = smtp_runtime(db)
    template = feedback_template(vacancy, required(db, Candidate, application.candidate_id))
    return template | {
        "subject": entry.payload["subject"] if entry else template["subject"],
        "body": entry.payload["body"] if entry else template["body"],
        "status": entry.status if entry else "NOT_REQUESTED",
        "delivery_enabled": config.enabled,
        "test_mode": config.test_mode,
    }


@router.post("/applications/{application_id}/rejection-email")
def send_rejection_email(application_id: str, body: RejectionEmailInput, db: Db, actor: Current):
    actor.require("message.send")
    application = application_access(db, actor, application_id)
    vacancy = vacancy_access(db, actor, application.vacancy_id, "message.send")
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    candidate = required(db, Candidate, application.candidate_id)
    from app.services.rejection_feedback import queue_feedback
    entry = queue_feedback(db, actor, application, candidate, vacancy, body.subject, body.body)
    return {"status": entry.status}


@router.get("/messages/unread-count")
def unread_message_count(db: Db, actor: Current):
    from app.services.message_reads import unread_messages
    return {"unread": unread_messages(db, actor)}


class ReadConversation(StrictModel):
    message_id: str = Field(min_length=36, max_length=36)


@router.post("/applications/{application_id}/messages/read")
def read_conversation(application_id: str, body: ReadConversation, db: Db, actor: Current):
    application = application_access(db, actor, application_id)
    if required(db, Candidate, application.candidate_id).user_id == actor.user.id:
        require_application_section(db, application, "messages")
    message = db.scalar(select(Message).where(Message.id == body.message_id,
        Message.application_id == application.id, Message.visibility == "CANDIDATE"))
    if not message:
        raise DomainError("Mensagem não encontrada.", 404)
    from app.services.message_reads import mark_conversation_read
    mark_conversation_read(db, actor, application, message)
    return {"read": True}


@router.get("/applications/{application_id}/stage-task-status")
def application_task_status(application_id: str, db: Db, actor: Current):
    actor.require("candidate.view")
    application = application_access(db, actor, application_id)
    from app.services.stage_tasks import stage_tasks
    return stage_tasks(db, application)


@router.get("/applications/{application_id}/messages")
def messages(application_id: str, db: Db, actor: Current,
             page_number: Annotated[int, Query(ge=1)] = 1,
             conversation_only: bool = False):
    row = application_access(db, actor, application_id)
    own = required(db, Candidate, row.candidate_id).user_id == actor.user.id
    if own:
        require_application_section(db, row, "messages")
    query = select(Message).where(Message.application_id == row.id)
    if own or conversation_only:
        query = query.where(Message.visibility == "CANDIDATE")
    else:
        query = query.where(
            (Message.visibility != "PRIVATE") | (Message.sender_id == actor.user.id)
        )
        if "candidate.all" not in actor.permissions:
            query = query.where(Message.visibility != "RH")
    def view(message):
        result = serialize(message)
        sender = db.get(User, message.sender_id)
        result["sender_name"] = "Candidato" if sender and sender.kind == "CANDIDATO" else sender.name if sender else "RH"
        result["sender_kind"] = sender.kind if sender else "INTERNAL"
        return result

    return page(db, query.order_by(Message.created_at.desc(), Message.id.desc()), page_number, 25 if conversation_only else 100, view)


@router.post("/applications/{application_id}/messages", status_code=201)
def send_message(application_id: str, body: MessageInput, db: Db, actor: Current):
    row = application_access(db, actor, application_id)
    own = required(db, Candidate, row.candidate_id).user_id == actor.user.id
    if own:
        require_application_section(db, row, "messages")
    if not own:
        actor.require("message.send")
    if body.visibility not in {"CANDIDATE", "TEAM", "RH", "PRIVATE"} or (
        own and body.visibility != "CANDIDATE"
    ):
        raise DomainError("Visibilidade inválida.")
    message = Message(application_id=row.id, sender_id=actor.user.id, **body.model_dump())
    db.add(message)
    event(db, actor, "message.created", message, row.vacancy_id)
    if body.visibility == "CANDIDATE":
        candidate = required(db, Candidate, row.candidate_id)
        vacancy = required(db, Vacancy, row.vacancy_id)
        recipient = vacancy.recruiter_id if own else candidate.user_id
        user = db.get(User, recipient)
        if user and user.active and recipient != actor.user.id:
            link = ("/app" if own else "/candidato") + "/candidaturas/" + row.id + "?aba=messages"
            notify(db, recipient, "Nova mensagem na candidatura", "Há uma nova mensagem em " + vacancy.title + ".", "MESSAGE", link)
    return serialize(message)


class ReturnInput(StrictModel):
    version: int = Field(ge=1)
    notice_id: str
    consent: bool


@router.post("/applications/{application_id}/return")
def return_application(application_id: str, body: ReturnInput, db: Db, actor: Current):
    row = application_access(db, actor, application_id)
    check_version(row, body.version)
    candidate = required(db, Candidate, row.candidate_id)
    if candidate.user_id != actor.user.id:
        raise DomainError("Somente o candidato pode solicitar seu retorno.", 403)
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == row.vacancy_id).with_for_update())
    if (
        not vacancy
        or row.status != "WITHDRAWN"
        or vacancy.status != "PUBLISHED"
        or not vacancy.deadline
        or vacancy.deadline <= utcnow()
        or not vacancy.details.get("allow_withdrawal_return")
    ):
        raise DomainError("A política desta vaga não permite retorno nesta situação.", 409)
    notice = db.get(ConfigRecord, body.notice_id)
    if (
        not body.consent
        or not notice
        or not notice.active
        or notice.kind != "privacy-notices"
        or vacancy.details.get("notice_id") != notice.id
    ):
        raise DomainError("Aceite o aviso de privacidade vigente.")
    before = serialize(row)
    row.status = "ACTIVE"
    row.closed_at = None
    row.closure_reason = ""
    row.stage_entered_at = utcnow()
    db.add(
        StageHistory(
            application_id=row.id,
            stage_id=row.stage_id,
            entered_at=row.stage_entered_at,
            changed_by=actor.user.id,
            reason="Retorno solicitado pelo candidato conforme política da vaga.",
        )
    )
    db.add(
        Consent(
            candidate_id=candidate.id,
            notice_id=notice.id,
            notice_version=notice.version,
            notice_snapshot=notice.data,
            purpose="RECRUITMENT_RETURN",
            granted=True,
            ip=actor.ip,
        )
    )
    audit(db, actor, "application.returned", row, before=before, vacancy_id=row.vacancy_id)
    return application_view(db, actor, row)
