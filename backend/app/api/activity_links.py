from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import Field, HttpUrl, TypeAdapter, field_validator
from sqlalchemy import select

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, candidate_access, vacancy_access, vacancy_scope
from app.models import Application, Candidate, CandidateActivityLink, Interview, InterviewParticipant, Vacancy
from app.repositories.common import check_version, page, required, serialize
from app.schemas.auth import StrictModel
from app.services.candidate_journey import application_permissions
from app.services.events import event, notify

router = APIRouter(tags=["Links de entrevistas e testes"])
LinkKind = Literal["INTERVIEW", "TEST"]


class LinkContent(StrictModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3, max_length=5000)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("title", "description", "url", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def safe_url(cls, value):
        url = TypeAdapter(HttpUrl).validate_python(value)
        if url.username or url.password:
            raise ValueError("O link não pode conter usuário ou senha.")
        return str(url)


class LinkInput(LinkContent):
    application_id: str
    kind: LinkKind


class LinkUpdate(LinkContent):
    version: int = Field(ge=1)
    active: bool


def manage_application(db, actor, application_id):
    if actor.user.kind != "INTERNAL":
        raise DomainError("Somente o RH pode disponibilizar links.", 403)
    application = required(db, Application, application_id)
    vacancy_access(db, actor, application.vacancy_id, "candidate.move")
    return application


def link_view(db, actor, row):
    application = required(db, Application, row.application_id)
    vacancy = required(db, Vacancy, application.vacancy_id)
    access = application_permissions(db, application)
    unlocked = access["permissions"]["interviews" if row.kind == "INTERVIEW" else "tests"]
    completed = bool(row.completed_at)
    if row.kind == "INTERVIEW":
        interviews = db.scalars(select(Interview).join(InterviewParticipant,
            InterviewParticipant.interview_id == Interview.id).where(
                InterviewParticipant.application_id == application.id,
                Interview.status.not_in(["CANCELED", "CANCELLED"]))).all()
        completed = completed or access["phase"] in {"TEST", "ADMISSION"} or bool(interviews and all(item.status == "COMPLETED" for item in interviews))
    result = serialize(row) | {"vacancy_title": vacancy.title, "stage_unlocked": unlocked,
                               "completed": completed,
                               "can_manage": actor.user.kind == "INTERNAL" and "candidate.move" in actor.permissions}
    if actor.user.kind == "CANDIDATO":
        result.pop("created_by", None)
        result.pop("can_manage", None)
        if not unlocked:
            result.pop("url", None)
    return result


def notify_link(db, actor, row, updated=False):
    application = required(db, Application, row.application_id)
    candidate = required(db, Candidate, application.candidate_id)
    unlocked = link_view(db, actor, row)["stage_unlocked"]
    label = "Entrevista" if row.kind == "INTERVIEW" else "Teste"
    suffix = " atualizada" if row.kind == "INTERVIEW" else " atualizado"
    title = label + (suffix if updated else " disponível" if unlocked else " preparada pelo RH" if row.kind == "INTERVIEW" else " preparado pelo RH")
    body = row.title + (". Consulte o link e as orientações no portal." if unlocked else ". Aguarde o RH liberar a etapa desta candidatura.")
    notify(db, candidate.user_id, title, body, row.kind,
           "/candidato/entrevistas" if row.kind == "INTERVIEW" else "/candidato/testes")


@router.get("/candidate-activity-links")
def activity_links(db: Db, actor: Current, candidate_id: str = "", application_id: str = "",
                   kind: LinkKind | None = None, page_number: Annotated[int, Query(ge=1)] = 1):
    query = select(CandidateActivityLink).join(Application, Application.id == CandidateActivityLink.application_id)
    if actor.user.kind == "CANDIDATO":
        if candidate_id:
            candidate_access(db, actor, candidate_id)
        query = query.join(Candidate, Candidate.id == Application.candidate_id).where(
            Candidate.user_id == actor.user.id, CandidateActivityLink.active.is_(True))
    else:
        actor.require("candidate.view")
        candidate_access(db, actor, candidate_id)
        query = query.where(Application.candidate_id == candidate_id,
            Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))))
    if application_id:
        query = query.where(Application.id == application_id)
    if kind:
        query = query.where(CandidateActivityLink.kind == kind)
    return page(db, query.order_by(CandidateActivityLink.created_at.desc()), page_number, 100,
                lambda row: link_view(db, actor, row))


@router.post("/candidate-activity-links", status_code=201)
def create_link(body: LinkInput, db: Db, actor: Current):
    application = manage_application(db, actor, body.application_id)
    row = CandidateActivityLink(**body.model_dump(), created_by=actor.user.id)
    db.add(row)
    db.flush()
    event(db, actor, "candidate.activity_link_created", row, application.vacancy_id)
    notify_link(db, actor, row)
    return link_view(db, actor, row)


@router.put("/candidate-activity-links/{link_id}")
def update_link(link_id: str, body: LinkUpdate, db: Db, actor: Current):
    row = required(db, CandidateActivityLink, link_id)
    application = manage_application(db, actor, row.application_id)
    check_version(row, body.version)
    if any(getattr(row, key) != getattr(body, key) for key in ("title", "description", "url")):
        row.completed_at = None
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    event(db, actor, "candidate.activity_link_updated", row, application.vacancy_id)
    if row.active:
        notify_link(db, actor, row, updated=True)
    db.flush()
    return link_view(db, actor, row)


@router.post("/candidate-activity-links/{link_id}/complete")
def complete_link(link_id: str, db: Db, actor: Current):
    row = db.scalar(select(CandidateActivityLink).where(CandidateActivityLink.id == link_id).with_for_update())
    if not row:
        raise DomainError("Atividade não encontrada.", 404)
    application = required(db, Application, row.application_id)
    candidate = required(db, Candidate, application.candidate_id)
    if actor.user.kind != "CANDIDATO" or candidate.user_id != actor.user.id:
        raise DomainError("Atividade não encontrada.", 404)
    if row.kind != "TEST" or not row.active or not application_permissions(db, application)["permissions"]["tests"]:
        raise DomainError("Aguarde a liberação deste teste pelo RH.", 409)
    if not row.completed_at:
        row.completed_at = utcnow()
        event(db, actor, "candidate.external_test_completed", row, application.vacancy_id)
        vacancy = required(db, Vacancy, application.vacancy_id)
        notify(db, vacancy.recruiter_id, "Candidato informou a conclusão do teste", row.title,
               "TEST", "/app/candidaturas/" + application.id + "?aba=activities")
        db.flush()
    return link_view(db, actor, row)


@router.post("/applications/{application_id}/complete-external-tests")
def complete_external_test_phase(application_id: str, db: Db, actor: Current):
    application = manage_application(db, actor, application_id)
    db.scalar(select(Application).where(Application.id == application.id).with_for_update())
    if application_permissions(db, application)["phase"] != "TEST" or application.status not in {"ACTIVE", "RESERVE"}:
        raise DomainError("A candidatura precisa estar na etapa de testes.", 409)
    links = db.scalars(select(CandidateActivityLink).where(CandidateActivityLink.application_id == application.id,
        CandidateActivityLink.kind == "TEST", CandidateActivityLink.active.is_(True)).with_for_update()).all()
    if not links:
        raise DomainError("Disponibilize o link do teste antes de confirmar a conclusão.", 409)
    for row in links:
        if not row.completed_at:
            row.completed_at = utcnow()
            event(db, actor, "candidate.external_test_completion_confirmed_by_rh", row, application.vacancy_id)
    db.flush()
    return {"status": "COMPLETED", "message": "Fase de testes por link concluída."}
