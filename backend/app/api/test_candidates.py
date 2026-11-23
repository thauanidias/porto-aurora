from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field, field_validator
from sqlalchemy import or_, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, vacancy_access, vacancy_scope
from app.models import Application, Candidate, CandidateActivityLink, PipelineStage, Vacancy
from app.repositories.common import check_version, page, required
from app.schemas.auth import StrictModel
from app.services.candidate_journey import (
    application_permissions,
    require_application_section,
    stage_phase,
)
from app.services.events import event, notify

router = APIRouter(tags=["Candidatos em testes"])


@router.get("/test-candidates")
def test_candidates(db: Db, actor: Current, q: str = "", page_number: Annotated[int, Query(ge=1)] = 1):
    from app.api.applications import application_view, prime_application_views
    actor.require("candidate.view")
    stages = [s.id for s in db.scalars(select(PipelineStage).where(
        PipelineStage.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))))) if stage_phase(db, s) == "TEST"]
    query = select(Application).join(Candidate).join(Vacancy, Vacancy.id == Application.vacancy_id).where(
        Application.stage_id.in_(stages), Application.status.in_(["ACTIVE", "RESERVE"]),
        or_(Candidate.name.ilike("%" + q + "%"), Vacancy.title.ilike("%" + q + "%")))
    links: dict[str, list[dict[str, str]]] = {}

    def prepare(rows):
        prime_application_views(db, rows)
        for link in db.scalars(select(CandidateActivityLink).where(
            CandidateActivityLink.application_id.in_({r.id for r in rows}),
            CandidateActivityLink.kind == "TEST", CandidateActivityLink.active.is_(True))
            .order_by(CandidateActivityLink.created_at.desc())):
            links.setdefault(link.application_id, []).append({"id": link.id, "title": link.title,
                "description": link.description, "url": link.url})
    return page(db, query.order_by(Application.stage_entered_at.desc(), Application.id), page_number, 25,
        lambda row: application_view(db, actor, row) | {"test_links": links.get(row.id, [])}, prepare=prepare)


class Question(StrictModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    text: str = Field(min_length=3, max_length=500)
    required: bool = True

    @field_validator("text", mode="before")
    @classmethod
    def trim(cls, value):
        return value.strip() if isinstance(value, str) else value


class QuestionnaireInput(StrictModel):
    version: int = Field(ge=1)
    questions: list[Question] = Field(min_length=1, max_length=10)

    @field_validator("questions")
    @classmethod
    def unique_keys(cls, questions):
        if len({q.key for q in questions}) != len(questions):
            raise ValueError("As perguntas devem ter identificadores únicos.")
        return questions


@router.put("/applications/{application_id}/test-questionnaire")
def edit_questionnaire(application_id: str, body: QuestionnaireInput, db: Db, actor: Current):
    application = required(db, Application, application_id)
    vacancy_access(db, actor, application.vacancy_id, "test.manage")
    locked = db.scalar(select(Application).where(Application.id == application_id).with_for_update())
    if locked is None:
        raise DomainError("Candidatura não encontrada.", 404)
    application = locked
    check_version(application, body.version)
    require_application_section(db, application, "tests")
    current = application.test_questionnaire or {}
    application.test_questionnaire = current | {"questions": [q.model_dump() for q in body.questions],
                                               "revision": current.get("revision", 0) + 1}
    event(db, actor, "test.questionnaire_updated", application, application.vacancy_id)
    candidate = required(db, Candidate, application.candidate_id)
    notify(db, candidate.user_id, "Questionário de testes disponível", "Responda às perguntas disponibilizadas pelo RH.",
           "TEST", "/candidato/testes")
    db.flush()
    return {"id": application.id, "version": application.version, "questionnaire": application.test_questionnaire}


@router.get("/test-questionnaires/me")
def own_questionnaires(db: Db, actor: Current):
    applications = db.scalars(select(Application).join(Candidate).where(Candidate.user_id == actor.user.id)
                              .order_by(Application.updated_at.desc()))
    return {"items": [{"id": a.id, "version": a.version,
        "vacancy_title": required(db, Vacancy, a.vacancy_id).title, "questionnaire": a.test_questionnaire}
        for a in applications if a.test_questionnaire.get("questions")
        and application_permissions(db, a)["permissions"]["tests"]]}


class QuestionnaireAnswers(StrictModel):
    version: int = Field(ge=1)
    revision: int = Field(ge=1)
    answers: dict[str, str] = Field(max_length=10)


@router.put("/applications/{application_id}/test-questionnaire/answers")
def answer_questionnaire(application_id: str, body: QuestionnaireAnswers, db: Db, actor: Current):
    application = application_access(db, actor, application_id)
    if required(db, Candidate, application.candidate_id).user_id != actor.user.id:
        raise DomainError("Somente o candidato pode responder ao questionário.", 403)
    check_version(application, body.version)
    require_application_section(db, application, "tests")
    current = application.test_questionnaire or {}
    if body.revision != current.get("revision"):
        raise DomainError("As perguntas foram alteradas. Atualize a página antes de responder.", 409)
    questions = current.get("questions", [])
    answers = {key: value.strip() for key, value in body.answers.items()}
    if set(answers) - {q["key"] for q in questions} or any(len(v) > 5000 for v in answers.values()):
        raise DomainError("Respostas inválidas para este questionário.")
    for question in questions:
        if question["required"] and not answers.get(question["key"]):
            raise DomainError("Responda à pergunta: " + question["text"])
    application.test_questionnaire = current | {"answers": answers, "answered_revision": body.revision,
        "answered_questions": questions, "submitted_at": utcnow().isoformat()}
    event(db, actor, "test.questionnaire_answered", application, application.vacancy_id)
    db.flush()
    return {"id": application.id, "version": application.version, "questionnaire": application.test_questionnaire}
