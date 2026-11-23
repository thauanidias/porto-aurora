from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field, HttpUrl, TypeAdapter, field_validator, model_validator
from sqlalchemy import func, select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, vacancy_scope
from app.domain.assessment import Question, grade
from app.models import (
    Application,
    Assessment,
    Candidate,
    Document,
    TestAssignment,
    TestAttempt,
    Vacancy,
)
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.services.candidate_journey import application_permissions, require_application_section
from app.services.events import event, notify
from app.services.recruitment import calculate_application

router = APIRouter(tags=["Testes"])


class AssessmentInput(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    duration_minutes: int = Field(default=60, ge=1, le=480)
    attempts_allowed: int = Field(default=1, ge=1, le=10)
    pass_score: float = Field(default=60, ge=0, le=100, allow_inf_nan=False)
    shuffle: bool = False
    questions: list[Question] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_questions(self):
        if len({q.key for q in self.questions}) != len(self.questions):
            raise ValueError("Identificadores de questões devem ser únicos")
        return self


@router.get("/tests/schema")
def assessment_schema(actor: Current):
    actor.require("test.manage")
    return AssessmentInput.model_json_schema()


@router.get("/tests")
def tests(db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1, q: str = ""):
    actor.require("test.manage")
    return page(
        db,
        select(Assessment)
        .where(Assessment.name.ilike("%" + q + "%"))
        .order_by(Assessment.created_at.desc()),
        page_number,
        25,
    )


@router.post("/tests", status_code=201)
def create_test(body: AssessmentInput, db: Db, actor: Current):
    actor.require("test.manage")
    row = Assessment(**body.model_dump(), created_by=actor.user.id)
    db.add(row)
    event(db, actor, "test.created", row)
    return serialize(row)


class AssignInput(StrictModel):
    application_id: str
    opens_at: datetime
    due_at: datetime
    external_url: str = Field(default="", max_length=2048, title="Link externo do teste", description="Informe o link fornecido pelo RH para esta pessoa. Deixe vazio para usar o teste interno.")

    @field_validator("external_url")
    @classmethod
    def validate_external_url(cls, value):
        value = value.strip()
        if not value:
            return ""
        url = TypeAdapter(HttpUrl).validate_python(value)
        if url.username or url.password:
            raise ValueError("O link não pode conter usuário ou senha.")
        return str(url)


@router.post("/tests/{test_id}/assign", status_code=201)
def assign_test(test_id: str, body: AssignInput, db: Db, actor: Current):
    actor.require("test.manage")
    application = application_access(db, actor, body.application_id, "test.manage")
    assessment = db.get(Assessment, test_id)
    if not assessment or not assessment.active:
        raise DomainError("Teste inválido.")
    if (
        not body.opens_at.tzinfo
        or not body.due_at.tzinfo
        or body.due_at <= body.opens_at
        or body.due_at <= utcnow()
    ):
        raise DomainError("Janela de realização inválida.")
    row = TestAssignment(
        application_id=application.id,
        assessment_id=assessment.id,
        snapshot=serialize(assessment) | {"external_url": body.external_url},
        opens_at=body.opens_at,
        due_at=body.due_at,
        created_by=actor.user.id,
    )
    db.add(row)
    event(db, actor, "test.assigned", row, application.vacancy_id)
    candidate = required(db, Candidate, application.candidate_id)
    unlocked = application_permissions(db, application)["permissions"]["tests"]
    notify(db, candidate.user_id, "Teste disponível" if unlocked else "Teste preparado pelo RH",
           assessment.name if unlocked else assessment.name + ". Aguarde o avanço desta candidatura para a etapa de testes.",
           "TEST", "/candidato/testes")
    return serialize(row)


@router.get("/test-assignments")
def assignments(db: Db, actor: Current, application_id: str = ""):
    query = select(TestAssignment).join(
        Application, TestAssignment.application_id == Application.id
    )
    if application_id:
        query = query.where(TestAssignment.application_id == application_id)
    own = (
        actor.user.kind == "CANDIDATO"
        or not {"test.manage", "candidate.evaluate"} & actor.permissions
    )
    if own:
        query = query.join(Candidate, Application.candidate_id == Candidate.id).where(
            Candidate.user_id == actor.user.id
        )
    else:
        query = query.where(
            Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
        )

    def view(row):
        result = serialize(row)
        result["snapshot"] = {k: v for k, v in row.snapshot.items() if k != "questions"}
        if own:
            result["stage_unlocked"] = application_permissions(db, db.get(Application, row.application_id))["permissions"]["tests"]
            if not result["stage_unlocked"]:
                result["snapshot"].pop("external_url", None)
        result["attempts"] = [
            serialize(a, {"grading"})
            for a in db.scalars(
                select(TestAttempt)
                .where(TestAttempt.assignment_id == row.id)
                .order_by(TestAttempt.number)
            )
        ]
        graded = [attempt for attempt in result["attempts"] if attempt["status"] == "GRADED"]
        result["result"] = ("APPROVED" if any(attempt["score"] >= row.snapshot.get("pass_score", 60)
            for attempt in graded) else "REJECTED") if graded else "PENDING"
        return result

    return page(db, query.order_by(TestAssignment.due_at), 1, 100, view)


@router.post("/test-assignments/{assignment_id}/start")
def start(assignment_id: str, db: Db, actor: Current):
    row = db.scalar(
        select(TestAssignment).where(TestAssignment.id == assignment_id).with_for_update()
    )
    if not row:
        raise DomainError("Teste não encontrado.", 404)
    application = application_access(db, actor, row.application_id)
    if required(db, Candidate, application.candidate_id).user_id != actor.user.id:
        raise DomainError("Somente o candidato pode realizar o teste.", 403)
    require_application_section(db, application, "tests")
    if row.snapshot.get("external_url"):
        raise DomainError("Este teste deve ser realizado no link externo liberado pelo RH.", 409)
    now = utcnow()
    if now < row.opens_at or now > row.due_at:
        raise DomainError("O teste está fora da janela de realização.", 409)
    current = db.scalar(
        select(TestAttempt).where(
            TestAttempt.assignment_id == row.id, TestAttempt.status == "STARTED"
        )
    )
    if not current:
        count = (
            db.scalar(
                select(func.count())
                .select_from(TestAttempt)
                .where(TestAttempt.assignment_id == row.id)
            )
            or 0
        )
        if count >= row.snapshot["attempts_allowed"]:
            raise DomainError("Limite de tentativas atingido.", 409)
        current = TestAttempt(assignment_id=row.id, number=count + 1, started_at=now)
        db.add(current)
        db.flush()
    questions = [
        {k: v for k, v in q.items() if k not in {"correct", "tolerance"}}
        for q in row.snapshot["questions"]
    ]
    if row.snapshot["shuffle"]:
        import random

        random.Random(current.id).shuffle(questions)
    deadline = min(
        row.due_at, current.started_at + timedelta(minutes=row.snapshot["duration_minutes"])
    )
    return serialize(current) | {"questions": questions, "deadline": deadline.isoformat()}


class SubmitAnswers(StrictModel):
    answers: dict
    version: int


@router.post("/test-attempts/{attempt_id}/submit")
def submit_answers(attempt_id: str, body: SubmitAnswers, db: Db, actor: Current):
    attempt = db.scalar(select(TestAttempt).where(TestAttempt.id == attempt_id).with_for_update())
    if not attempt:
        raise DomainError("Tentativa não encontrada.", 404)
    assignment = required(db, TestAssignment, attempt.assignment_id)
    application = application_access(db, actor, assignment.application_id)
    if required(db, Candidate, application.candidate_id).user_id != actor.user.id:
        raise DomainError("Acesso não autorizado.", 403)
    require_application_section(db, application, "tests")
    check_version(attempt, body.version)
    if attempt.status != "STARTED":
        raise DomainError("Tentativa já concluída.", 409)
    limit = min(
        assignment.due_at,
        attempt.started_at + timedelta(minutes=assignment.snapshot["duration_minutes"]),
    )
    if utcnow() > limit + timedelta(seconds=5):
        raise DomainError("O tempo do teste expirou.", 409)
    keys = {q["key"] for q in assignment.snapshot["questions"]}
    if set(body.answers) - keys:
        raise DomainError("Resposta para questão inexistente.")
    for question in assignment.snapshot["questions"]:
        if question["kind"] == "UPLOAD" and body.answers.get(question["key"]):
            doc = db.get(Document, body.answers[question["key"]])
            if not doc or doc.candidate_id != application.candidate_id:
                raise DomainError("Arquivo de resposta inválido.")
    result = grade(assignment.snapshot["questions"], body.answers)
    attempt.answers = body.answers
    attempt.grading = result["items"]
    attempt.score = result["score"]
    attempt.status = result["status"]
    attempt.submitted_at = utcnow()
    event(db, actor, "test.completed", attempt, application.vacancy_id)
    if attempt.status == "GRADED":
        calculate_application(db, actor, application)
    return serialize(attempt, {"grading"})


class ManualGrade(StrictModel):
    grading: dict
    version: int


@router.post("/test-attempts/{attempt_id}/grade")
def grade_attempt(attempt_id: str, body: ManualGrade, db: Db, actor: Current):
    actor.require("candidate.evaluate")
    attempt = db.get(TestAttempt, attempt_id)
    if not attempt:
        raise DomainError("Tentativa não encontrada.", 404)
    assignment = required(db, TestAssignment, attempt.assignment_id)
    application = application_access(db, actor, assignment.application_id, "candidate.evaluate")
    check_version(attempt, body.version)
    if not attempt.submitted_at:
        raise DomainError("Aguarde a conclusão do teste.")
    result = grade(assignment.snapshot["questions"], attempt.answers, body.grading)
    attempt.grading = result["items"]
    attempt.score = result["score"]
    attempt.status = result["status"]
    attempt.graded_by = actor.user.id
    event(db, actor, "test.graded", attempt, application.vacancy_id)
    calculate_application(db, actor, application)
    return serialize(attempt)


@router.put("/test-attempts/{attempt_id}/answers")
def save_answers(attempt_id: str, body: SubmitAnswers, db: Db, actor: Current):
    attempt = db.scalar(select(TestAttempt).where(TestAttempt.id == attempt_id).with_for_update())
    if not attempt:
        raise DomainError("Tentativa não encontrada.", 404)
    assignment = required(db, TestAssignment, attempt.assignment_id)
    application = application_access(db, actor, assignment.application_id)
    if required(db, Candidate, application.candidate_id).user_id != actor.user.id:
        raise DomainError("Acesso não autorizado.", 403)
    limit = min(
        assignment.due_at,
        attempt.started_at + timedelta(minutes=assignment.snapshot["duration_minutes"]),
    )
    if attempt.status != "STARTED" or utcnow() > limit:
        raise DomainError("O período do teste terminou.", 409)
    check_version(attempt, body.version)
    if set(body.answers) - {q["key"] for q in assignment.snapshot["questions"]}:
        raise DomainError("Questão inexistente.")
    attempt.answers = body.answers
    db.flush()
    return {"version": attempt.version, "message": "Respostas salvas."}


@router.get("/test-attempts/{attempt_id}/review")
def review_attempt(attempt_id: str, db: Db, actor: Current):
    actor.require("candidate.evaluate")
    attempt = required(db, TestAttempt, attempt_id)
    assignment = required(db, TestAssignment, attempt.assignment_id)
    application_access(db, actor, assignment.application_id, "candidate.evaluate")
    if not attempt.submitted_at:
        raise DomainError("Aguarde a conclusão do teste.", 409)
    return serialize(attempt) | {"questions": assignment.snapshot["questions"]}
