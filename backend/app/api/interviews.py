from datetime import datetime
from statistics import mean, pstdev
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, vacancy_access, vacancy_scope
from app.models import (
    Application,
    Candidate,
    CandidateActivityLink,
    ConfigRecord,
    Evaluation,
    Interview,
    InterviewParticipant,
    PipelineStage,
    User,
    Vacancy,
)
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.services.candidate_journey import (
    application_permissions,
    require_application_section,
    stage_phase,
)
from app.services.events import audit, event, notify
from app.services.recruitment import calculate_application, candidate_view

router = APIRouter(tags=["Entrevistas e avaliações"])


class InterviewInput(StrictModel):
    vacancy_id: str
    title: str = Field(min_length=3, max_length=180)
    kind: Literal["RH", "TECHNICAL", "MANAGER", "PANEL", "GROUP", "IN_PERSON", "ONLINE"]
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(default=1, ge=1, le=100)
    location: str = Field(min_length=2, max_length=1000)
    interviewers: list[str] = Field(min_length=1, max_length=20)
    application_ids: list[str] = Field(default_factory=list, max_length=100)
    template_id: str | None = None


@router.get("/interviews/me")
def own_interviews(db: Db, actor: Current):
    own = select(InterviewParticipant.interview_id).join(
        Application, InterviewParticipant.application_id == Application.id
    ).join(Candidate, Application.candidate_id == Candidate.id).where(
        Candidate.user_id == actor.user.id,
        InterviewParticipant.user_id == actor.user.id,
    )
    query = select(Interview).where(Interview.id.in_(own), Interview.status == "SCHEDULED")

    def view(row):
        names = db.scalars(select(User.name).join(
            InterviewParticipant, InterviewParticipant.user_id == User.id
        ).where(
            InterviewParticipant.interview_id == row.id,
            InterviewParticipant.application_id.is_(None),
            User.kind == "INTERNAL",
        ).order_by(User.name)).all()
        applications = db.scalars(select(Application).join(InterviewParticipant,
            InterviewParticipant.application_id == Application.id).where(
                InterviewParticipant.interview_id == row.id, InterviewParticipant.user_id == actor.user.id))
        unlocked = any(application_permissions(db, item)["permissions"]["interviews"] for item in applications)
        return {"id": row.id, "starts_at": row.starts_at, "interviewers": names,
                "stage_unlocked": unlocked}

    return page(db, query.order_by(Interview.starts_at), 1, 100, view)


@router.get("/interviews/candidates")
def interview_candidates(
    db: Db,
    actor: Current,
    q: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    from app.api.applications import application_view, prime_application_views

    actor.require("candidate.view")
    stage_ids = [stage.id for stage in db.scalars(
        select(PipelineStage).where(
            PipelineStage.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
        )
    ) if stage_phase(db, stage) in {"INTERVIEW", "TEST"}]
    query = select(Application).join(Candidate).join(
        Vacancy, Application.vacancy_id == Vacancy.id
    ).where(
        Application.stage_id.in_(stage_ids),
        Application.status.in_(["ACTIVE", "RESERVE"]),
        or_(Candidate.name.ilike("%" + q + "%"), Vacancy.title.ilike("%" + q + "%")),
    )
    links: dict[str, list[dict[str, str]]] = {}

    def prepare(rows):
        prime_application_views(db, rows)
        for link in db.scalars(select(CandidateActivityLink).where(
            CandidateActivityLink.application_id.in_({row.id for row in rows}),
            CandidateActivityLink.kind == "INTERVIEW", CandidateActivityLink.active.is_(True),
        ).order_by(CandidateActivityLink.created_at.desc(), CandidateActivityLink.id)):
            links.setdefault(link.application_id, []).append({
                "id": link.id, "title": link.title, "description": link.description, "url": link.url,
            })

    return page(db, query.order_by(Application.stage_entered_at.desc(), Application.id),
                page_number, 25, lambda row: application_view(db, actor, row) | {
                    "interview_links": links.get(row.id, []),
                }, prepare=prepare)


@router.get("/interviews/manager-agenda")
def manager_agenda(db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1):
    actor.require("candidate.view")
    if actor.user.kind != "INTERNAL":
        raise DomainError("Acesso restrito à equipe interna.", 403)
    query = select(Interview).join(Vacancy, Vacancy.id == Interview.vacancy_id).where(
        Vacancy.manager_id == actor.user.id)

    def agenda_item(interview):
        vacancy = db.get(Vacancy, interview.vacancy_id)
        participants = db.scalars(select(InterviewParticipant).where(
            InterviewParticipant.interview_id == interview.id)).all()
        candidates = []
        for participant in participants:
            if participant.application_id:
                application = db.get(Application, participant.application_id)
                candidate = db.get(Candidate, application.candidate_id) if application else None
                if candidate:
                    candidates.append({"name": candidate_view(db, actor, candidate, application)["name"]})
        return serialize(interview) | {"vacancy_title": vacancy.title, "candidates": candidates}

    return page(db, query.order_by(Interview.starts_at.desc()), page_number, 50, serializer=agenda_item)


@router.get("/interviews")
def interviews(
    db: Db,
    actor: Current,
    start: datetime | None = None,
    end: datetime | None = None,
    q: str = "",
    application_id: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    query = select(Interview).where(Interview.title.ilike("%" + q + "%"))
    if application_id:
        application_access(db, actor, application_id)
        query = query.where(Interview.id.in_(select(InterviewParticipant.interview_id)
            .where(InterviewParticipant.application_id == application_id)))
    own = select(InterviewParticipant.interview_id).where(
        InterviewParticipant.user_id == actor.user.id
    )
    if actor.user.kind == "CANDIDATO":
        query = query.where(Interview.id.in_(own))
    else:
        actor.require("candidate.view")
        query = query.where(
            or_(
                Interview.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))),
                Interview.id.in_(own),
            )
        )
    if start:
        query = query.where(Interview.ends_at >= start)
    if end:
        query = query.where(Interview.starts_at <= end)
    return page(db, query.order_by(Interview.starts_at), page_number, 100)


@router.post("/interviews", status_code=201)
def create_interview(body: InterviewInput, db: Db, actor: Current):
    vacancy = vacancy_access(db, actor, body.vacancy_id, "interview.manage")
    if (
        not body.starts_at.tzinfo
        or not body.ends_at.tzinfo
        or body.ends_at <= body.starts_at
        or body.starts_at <= utcnow()
    ):
        raise DomainError("Data ou duração inválida.")
    if len(body.application_ids) > body.capacity:
        raise DomainError("Participantes excedem a capacidade.")
    # Lock interviewer rows in stable order to prevent concurrent overlapping bookings.
    for user_id in sorted(set(body.interviewers)):
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user or not user.active or user.kind != "INTERNAL":
            raise DomainError("Entrevistador inválido.")
        conflict = db.scalar(
            select(Interview.id)
            .join(InterviewParticipant, InterviewParticipant.interview_id == Interview.id)
            .where(
                InterviewParticipant.user_id == user_id,
                Interview.status == "SCHEDULED",
                Interview.starts_at < body.ends_at,
                Interview.ends_at > body.starts_at,
            )
        )
        if conflict:
            raise DomainError("Entrevistador já possui compromisso neste horário.", 409)
    template = db.get(ConfigRecord, body.template_id) if body.template_id else None
    if template and template.kind != "interview-templates":
        raise DomainError("Roteiro inválido.")
    row = Interview(
        **body.model_dump(exclude={"interviewers", "application_ids", "template_id"}),
        template=template.data if template else {},
        created_by=actor.user.id,
    )
    db.add(row)
    db.flush()
    for user_id in set(body.interviewers):
        db.add(InterviewParticipant(interview_id=row.id, user_id=user_id))
        notify(db, user_id, "Entrevista agendada", row.title, "INTERVIEW",
               "/gestor/entrevistas" if user_id == vacancy.manager_id else "/app/entrevistas")
    for application_id in set(body.application_ids):
        application = application_access(db, actor, application_id, "interview.manage")
        if application.vacancy_id != row.vacancy_id:
            raise DomainError("Candidato pertence a outra vaga.")
        candidate = required(db, Candidate, application.candidate_id)
        db.add(
            InterviewParticipant(
                interview_id=row.id, user_id=candidate.user_id, application_id=application.id
            )
        )
        notify(
            db,
            candidate.user_id,
            "Entrevista agendada",
            row.title + " — " + row.starts_at.isoformat(),
            "INTERVIEW",
            "/candidato/entrevistas",
        )
    vacancy = required(db, Vacancy, row.vacancy_id)
    if vacancy.manager_id not in set(body.interviewers):
        notify(db, vacancy.manager_id, "Entrevista agendada para sua vaga",
               vacancy.title + " — " + row.starts_at.isoformat(), "INTERVIEW", "/gestor/entrevistas")
    event(db, actor, "interview.created", row, row.vacancy_id)
    return serialize(row)


@router.get("/applications/{application_id}/interview-slots")
def slots(application_id: str, db: Db, actor: Current):
    application = application_access(db, actor, application_id)
    if actor.user.kind == "CANDIDATO" and not application_permissions(db, application)["permissions"]["interviews"]:
        return {"items": []}
    query = select(Interview).where(
        Interview.vacancy_id == application.vacancy_id,
        Interview.starts_at > utcnow(),
        Interview.status == "SCHEDULED",
    )
    rows = []
    for row in db.scalars(query.order_by(Interview.starts_at).limit(100)):
        count = (
            db.scalar(
                select(func.count())
                .select_from(InterviewParticipant)
                .where(
                    InterviewParticipant.interview_id == row.id,
                    InterviewParticipant.application_id.is_not(None),
                )
            )
            or 0
        )
        if count < row.capacity:
            rows.append(serialize(row, {"template", "created_by"}))
    return {"items": rows}


@router.post("/applications/{application_id}/interview-slots/{interview_id}/book")
def book(application_id: str, interview_id: str, db: Db, actor: Current):
    application = application_access(db, actor, application_id)
    if required(db, Candidate, application.candidate_id).user_id != actor.user.id:
        raise DomainError("Somente o candidato pode reservar.", 403)
    require_application_section(db, application, "interviews")
    row = db.scalar(select(Interview).where(Interview.id == interview_id).with_for_update())
    if (
        not row
        or row.vacancy_id != application.vacancy_id
        or row.starts_at <= utcnow()
        or row.status != "SCHEDULED"
    ):
        raise DomainError("Horário indisponível.", 409)
    current = db.scalar(
        select(InterviewParticipant.id).where(
            InterviewParticipant.interview_id == row.id,
            InterviewParticipant.user_id == actor.user.id,
        )
    )
    if current:
        return {"message": "Reserva já confirmada."}
    count = (
        db.scalar(
            select(func.count())
            .select_from(InterviewParticipant)
            .where(
                InterviewParticipant.interview_id == row.id,
                InterviewParticipant.application_id.is_not(None),
            )
        )
        or 0
    )
    if count >= row.capacity:
        raise DomainError("Horário já reservado. Escolha outro.", 409)
    conflict = db.scalar(
        select(Interview.id)
        .join(InterviewParticipant, InterviewParticipant.interview_id == Interview.id)
        .where(
            InterviewParticipant.user_id == actor.user.id,
            Interview.status == "SCHEDULED",
            Interview.starts_at < row.ends_at,
            Interview.ends_at > row.starts_at,
        )
    )
    if conflict:
        raise DomainError("Você já possui entrevista neste horário.", 409)
    db.add(
        InterviewParticipant(
            interview_id=row.id, user_id=actor.user.id, application_id=application.id
        )
    )
    event(db, actor, "interview.booked", row, row.vacancy_id)
    notify(db, row.created_by, "Horário reservado", row.title, "INTERVIEW")
    return {"message": "Entrevista confirmada."}


def interview_access(db, actor, interview_id):
    row = db.get(Interview, interview_id)
    if not row:
        raise DomainError("Entrevista não encontrada.", 404)
    own = db.scalar(
        select(InterviewParticipant.id).where(
            InterviewParticipant.interview_id == row.id,
            InterviewParticipant.user_id == actor.user.id,
        )
    )
    if not own:
        vacancy_access(db, actor, row.vacancy_id, "interview.manage")
    return row


@router.get("/interviews/{interview_id}/calendar.ics")
def calendar_file(interview_id: str, db: Db, actor: Current):
    row = interview_access(db, actor, interview_id)

    def escaped(value):
        return (
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\r", "")
            .replace(",", "\\,")
            .replace(";", "\\;")
        )

    content = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Porto Aurora//Talentos//PT-BR",
            "BEGIN:VEVENT",
            "UID:" + row.id + "@tgpm-talentos",
            "DTSTAMP:" + utcnow().strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART:" + row.starts_at.strftime("%Y%m%dT%H%M%SZ"),
            "DTEND:" + row.ends_at.strftime("%Y%m%dT%H%M%SZ"),
            "SUMMARY:" + escaped(row.title),
            "LOCATION:" + escaped(row.location),
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return Response(
        content,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="entrevista.ics"'},
    )


class InterviewStatus(StrictModel):
    version: int
    status: Literal["COMPLETED", "CANCELED", "NO_SHOW"]
    reason: str = Field(min_length=5)


@router.post("/interviews/{interview_id}/status")
def interview_status(interview_id: str, body: InterviewStatus, db: Db, actor: Current):
    row = interview_access(db, actor, interview_id)
    actor.require("interview.manage")
    check_version(row, body.version)
    row.status = body.status
    audit(db, actor, "interview.status_updated", row, after={"status": body.status, "reason": body.reason}, vacancy_id=row.vacancy_id)
    event(
        db,
        actor,
        "interview.completed" if body.status == "COMPLETED" else "interview.canceled",
        row,
        row.vacancy_id,
    )
    return serialize(row)


class EvaluationInput(StrictModel):
    application_id: str
    evaluator_id: str
    scorecard_id: str
    interview_id: str | None = None


@router.post("/evaluations", status_code=201)
def assign_evaluation(body: EvaluationInput, db: Db, actor: Current):
    application = application_access(db, actor, body.application_id, "interview.manage")
    actor.require("interview.manage")
    template = db.get(ConfigRecord, body.scorecard_id)
    evaluator = db.get(User, body.evaluator_id)
    if (
        not template
        or template.kind != "scorecards"
        or not evaluator
        or not evaluator.active
        or evaluator.kind != "INTERNAL"
    ):
        raise DomainError("Ficha ou avaliador inválido.")
    row = Evaluation(
        application_id=application.id,
        interview_id=body.interview_id,
        evaluator_id=body.evaluator_id,
        category=template.data["category"],
        criteria=template.data["criteria"],
        independent=template.data["independent"],
    )
    db.add(row)
    event(db, actor, "evaluation.assigned", row, application.vacancy_id)
    notify(
        db,
        evaluator.id,
        "Avaliação pendente",
        "Uma ficha de avaliação foi atribuída a você.",
        "INTERVIEW",
    )
    return serialize(row)


def evaluation_view(db, actor, row):
    application = db.get(Application, row.application_id)
    vacancy = db.get(Vacancy, application.vacancy_id)
    candidate = db.get(Candidate, application.candidate_id)
    context = {
        "candidate_name": candidate_view(db, actor, candidate, application).get("name"),
        "vacancy_title": vacancy.title,
        "status": "DONE" if row.submitted_at else "OPEN",
    }
    if row.evaluator_id == actor.user.id:
        return serialize(row) | context
    pending = db.scalar(
        select(Evaluation.id).where(
            Evaluation.application_id == row.application_id, Evaluation.submitted_at.is_(None)
        )
    )
    if row.independent and pending:
        return serialize(row, {"answers", "score", "recommendation"}) | context | {"sealed": True}
    return serialize(row) | context


@router.get("/evaluations")
def evaluations(
    db: Db,
    actor: Current,
    application_id: str = "",
    q: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    actor.require("candidate.evaluate")
    query = select(Evaluation).where(Evaluation.category.ilike("%" + q + "%"))
    if application_id:
        application_access(db, actor, application_id, "candidate.evaluate")
        query = query.where(Evaluation.application_id == application_id)
    else:
        query = query.where(Evaluation.evaluator_id == actor.user.id)
    return page(
        db,
        query.order_by(Evaluation.created_at.desc()),
        page_number,
        25,
        lambda row: evaluation_view(db, actor, row),
    )


class EvaluationAnswers(StrictModel):
    version: int
    answers: dict
    recommendation: Literal["ADVANCE", "RESERVE", "DO_NOT_ADVANCE"]
    reason: str = Field(default="", max_length=2000)


@router.post("/evaluations/{evaluation_id}/submit")
def submit_evaluation(evaluation_id: str, body: EvaluationAnswers, db: Db, actor: Current):
    actor.require("candidate.evaluate")
    row = db.get(Evaluation, evaluation_id)
    if not row or row.evaluator_id != actor.user.id:
        raise DomainError("Avaliação não encontrada.", 404)
    check_version(row, body.version)
    if row.submitted_at and len(body.reason.strip()) < 10:
        raise DomainError("Alteração de avaliação concluída exige justificativa.")
    total = 0.0
    weights = 0.0
    for criterion in row.criteria:
        answer = body.answers.get(criterion["key"], {})
        value = answer.get("value")
        if (
            not isinstance(value, (int, float))
            or not criterion["min_value"] <= value <= criterion["max_value"]
        ):
            raise DomainError("Informe nota válida para " + criterion["name"])
        if (
            criterion["extreme_comment"]
            and value in {criterion["min_value"], criterion["max_value"]}
            and len(answer.get("comment", "").strip()) < 5
        ):
            raise DomainError("Notas extremas exigem comentário.")
        total += (
            (value - criterion["min_value"])
            / (criterion["max_value"] - criterion["min_value"])
            * 100
            * criterion["weight"]
        )
        weights += criterion["weight"]
    before = serialize(row)
    row.answers = body.answers
    row.recommendation = body.recommendation
    row.score = round(total / weights, 2)
    row.submitted_at = utcnow()
    application = required(db, Application, row.application_id)
    audit(db, actor, "evaluation.submitted", row, before, serialize(row), application.vacancy_id)
    calculate_application(db, actor, application)
    return serialize(row)


@router.get("/applications/{application_id}/consensus")
def consensus(application_id: str, db: Db, actor: Current):
    actor.require("candidate.evaluate")
    application_access(db, actor, application_id, "candidate.evaluate")
    rows = list(db.scalars(select(Evaluation).where(Evaluation.application_id == application_id)))
    sealed = any(row.independent and not row.submitted_at for row in rows)
    values = [float(row.score) for row in rows if row.score is not None]
    return {
        "evaluations": [evaluation_view(db, actor, row) for row in rows],
        "sealed": sealed,
        "mean": mean(values) if values and not sealed else None,
        "dispersion": pstdev(values) if values and not sealed else None,
        "divergence": max(values) - min(values) if values and not sealed else None,
    }
