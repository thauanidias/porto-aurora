from statistics import mean, pstdev
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import Field
from sqlalchemy import select

from app.api.candidates import candidates, scoped_candidates
from app.api.interviews import consensus
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db, application_access, vacancy_access, vacancy_scope
from app.domain.scoring import calculate
from app.models import (
    Application,
    ApplicationScore,
    AuditLog,
    Candidate,
    CandidateLabel,
    Evaluation,
    Message,
    ScoringVersion,
    Task,
    User,
    Vacancy,
)
from app.repositories.common import check_version, serialize
from app.schemas.auth import StrictModel
from app.services.compatibility import compatibility_summary, rank_compatibility
from app.services.events import audit, notify
from app.services.recruitment import candidate_view

router = APIRouter(tags=["Busca, comparação e colaboração"])


@router.get("/search")
def search(db: Db, actor: Current, q: Annotated[str, Query(min_length=2, max_length=100)]):
    results = []
    if "vacancy.view" in actor.permissions:
        for row in db.scalars(
            select(Vacancy)
            .where(vacancy_scope(actor), Vacancy.title.ilike("%" + q + "%"))
            .limit(10)
        ):
            results.append(
                {"id": row.id, "type": "Vaga", "name": row.title, "link": "/app/vagas/" + row.id}
            )
    if "candidate.view" in actor.permissions:
        for row in candidates(db, actor, q=q, page_size=10)["items"]:
            results.append(
                {
                    "id": row["id"],
                    "type": "Candidato",
                    "name": row["name"],
                    "link": "/app/candidatos/" + row["id"],
                }
            )
    for task in db.scalars(
        select(Task)
        .where(Task.assigned_to == actor.user.id, Task.title.ilike("%" + q + "%"))
        .limit(10)
    ):
        results.append(
            {"id": task.id, "type": "Tarefa", "name": task.title, "link": "/app/trabalho"}
        )
    return {"items": results}


@router.get("/vacancies/{vacancy_id}/compare")
def compare(vacancy_id: str, db: Db, actor: Current, ids: str = ""):
    vacancy_access(db, actor, vacancy_id, "candidate.evaluate")
    selected = list(dict.fromkeys(ids.split(","))) if ids else []
    if not 1 <= len(selected) <= 6:
        raise DomainError("Selecione de um a seis candidatos.")
    items = []
    for app_id in selected:
        application = application_access(db, actor, app_id, "candidate.evaluate")
        if application.vacancy_id != vacancy_id:
            raise DomainError("Candidatura não pertence à vaga.")
        candidate = db.get(Candidate, application.candidate_id)
        score = db.scalar(
            select(ApplicationScore)
            .where(ApplicationScore.application_id == app_id)
            .order_by(ApplicationScore.created_at.desc())
            .limit(1)
        )
        evaluation = consensus(app_id, db, actor)
        breakdown = score.breakdown if score else {}
        items.append(
            {
                "id": application.id,
                "candidate": candidate_view(db, actor, candidate, application),
                "status": application.status,
                "objective": breakdown.get("objective_total"),
                "total": float(score.total)
                if score and score.total is not None and not evaluation["sealed"]
                else None,
                "criteria": breakdown.get("items", []),
                "knockout": score.knockout if score else None,
                "consensus": evaluation,
            }
        )
    audit(
        db,
        actor,
        "candidate.compared",
        db.get(Vacancy, vacancy_id),
        after={"applications": selected},
        vacancy_id=vacancy_id,
    )
    return {
        "items": items,
        "notice": "A aderência apoia a análise humana. A decisão exige justificativa e cumprimento das etapas.",
    }


@router.get("/vacancies/{vacancy_id}/rediscover")
def rediscover(
    vacancy_id: str, db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1
):
    vacancy_access(db, actor, vacancy_id, "talent.manage")
    model = db.scalar(
        select(ScoringVersion)
        .where(ScoringVersion.vacancy_id == vacancy_id)
        .order_by(ScoringVersion.number.desc())
        .limit(1)
    )
    if not model:
        raise DomainError("Configure o modelo de aderência da vaga.")
    query = scoped_candidates(actor).where(
        Candidate.talent_consent_until > utcnow(),
        Candidate.id.not_in(
            select(Application.candidate_id).where(Application.vacancy_id == vacancy_id)
        ),
    )
    items = []
    for candidate in db.scalars(query.execution_options(yield_per=100)):
        facts = candidate.profile | candidate.profile.get("facts", {})
        # Results from earlier selection tests do not belong to this vacancy.
        facts = facts | {"test_score": None, "evaluation_score": None}
        score = calculate(model.criteria, facts)
        summary = compatibility_summary(SimpleNamespace(
            model_id=model.id, total=score["total"], breakdown=score,
            knockout=score["knockout"], created_at=utcnow(),
        ), model)
        items.append(
            {
                "id": candidate.id,
                "candidate": candidate_view(db, actor, candidate),
                "score": summary["percentage"],
                "compatibility": summary,
                "registered_at": candidate.created_at,
                "knockout": score["knockout"],
            }
        )
    items = rank_compatibility(items)
    audit(
        db, actor, "talent.rediscovered", model, after={"count": len(items)}, vacancy_id=vacancy_id
    )
    return {
        "items": items[(page_number - 1) * 25 : page_number * 25],
        "total": len(items),
        "page": page_number,
        "page_size": 25,
        "model_version": model.number,
        "notice": "Simulação com o perfil atual e consentimento vigente. Um convite não cria candidatura.",
    }


@router.get("/analytics/calibration")
def calibration(db: Db, actor: Current):
    actor.require("report.view")
    authorized = select(Application.id).where(
        Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor)))
    )
    pending = select(Evaluation.application_id).where(
        Evaluation.independent.is_(True), Evaluation.submitted_at.is_(None)
    )
    records = list(
        db.scalars(
            select(Evaluation).where(
                Evaluation.application_id.in_(authorized),
                Evaluation.application_id.not_in(pending),
                Evaluation.score.is_not(None),
            )
        )
    )
    grouped: dict[str, list[Evaluation]] = {}
    for item in records:
        grouped.setdefault(item.evaluator_id, []).append(item)
    items = []
    for key, values in grouped.items():
        deviations = []
        for item in values:
            peers = [
                float(other.score or 0)
                for other in records
                if other.application_id == item.application_id
                and other.evaluator_id != key
                and other.category == item.category
            ]
            if peers:
                deviations.append(float(item.score or 0) - mean(peers))
        scores = [float(item.score or 0) for item in values]
        user = db.get(User, key)
        items.append(
            {
                "id": key,
                "name": user.name if user else "Usuário",
                "count": len(values),
                "mean": round(mean(scores), 2),
                "dispersion": round(pstdev(scores), 2),
                "peer_deviation": round(mean(deviations), 2) if deviations else None,
                "comparable_count": len(deviations),
            }
        )
    return {
        "items": items,
        "notice": "Desvio = nota menos média dos demais avaliadores na mesma candidatura e categoria. Amostras pequenas exigem cautela; avaliações pendentes permanecem lacradas.",
    }


class NoteUpdate(StrictModel):
    version: int
    body: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=5, max_length=2000)


@router.put("/messages/{message_id}")
def edit_note(message_id: str, body: NoteUpdate, db: Db, actor: Current):
    row = db.get(Message, message_id)
    if not row or row.sender_id != actor.user.id or row.visibility == "CANDIDATE":
        raise DomainError("Somente suas notas internas podem ser editadas.", 403)
    app = application_access(db, actor, row.application_id)
    actor.require("message.send")
    check_version(row, body.version)
    before = serialize(row)
    row.body = body.body
    audit(
        db,
        actor,
        "note.updated",
        row,
        before,
        serialize(row) | {"reason": body.reason},
        app.vacancy_id,
    )
    return serialize(row)


@router.get("/messages/{message_id}/history")
def note_history(message_id: str, db: Db, actor: Current):
    row = db.get(Message, message_id)
    if not row:
        raise DomainError("Nota não encontrada.", 404)
    application_access(db, actor, row.application_id, "message.send")
    actor.require("message.send")
    if (
        row.visibility == "CANDIDATE"
        or row.visibility == "PRIVATE"
        and row.sender_id != actor.user.id
        or row.visibility == "RH"
        and "candidate.all" not in actor.permissions
    ):
        raise DomainError("Acesso não autorizado.", 403)
    return {
        "items": [
            serialize(entry)
            for entry in db.scalars(
                select(AuditLog)
                .where(AuditLog.entity_id == message_id, AuditLog.action == "note.updated")
                .order_by(AuditLog.created_at.desc())
            )
        ]
    }


class Mention(StrictModel):
    user_id: str


@router.post("/messages/{message_id}/mentions")
def mention(message_id: str, body: Mention, db: Db, actor: Current):
    row = db.get(Message, message_id)
    if not row or row.sender_id != actor.user.id or row.visibility not in {"TEAM", "RH"}:
        raise DomainError("Somente notas compartilhadas podem mencionar pessoas.", 403)
    application = application_access(db, actor, row.application_id, "message.send")
    actor.require("message.send")
    user = db.get(User, body.user_id)
    if not user or not user.active or user.kind != "INTERNAL":
        raise DomainError("Destinatário inválido.")
    from app.core.permissions import Actor
    from app.models import RolePermission, UserRole

    permissions = set(
        db.scalars(
            select(RolePermission.permission)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user.id)
        )
    )
    target = Actor(user, permissions, "", actor.ip, actor.request_id)
    application_access(db, target, application.id)
    if row.visibility == "RH" and "candidate.all" not in permissions:
        raise DomainError("O destinatário não pode acessar esta nota.", 403)
    notify(
        db,
        user.id,
        "Você foi mencionado",
        "Há uma nota no processo seletivo.",
        "MENTION",
        "/app/candidaturas/" + application.id,
    )
    audit(
        db,
        actor,
        "note.mentioned",
        row,
        after={"user_id": user.id},
        vacancy_id=application.vacancy_id,
    )
    return {"message": "Menção registrada."}


@router.get("/candidates/{candidate_id}/labels")
def labels(candidate_id: str, db: Db, actor: Current):
    from app.core.permissions import candidate_access

    candidate_access(db, actor, candidate_id)
    actor.require("talent.manage")
    return {
        "items": [
            serialize(row)
            for row in db.scalars(
                select(CandidateLabel).where(
                    CandidateLabel.candidate_id == candidate_id,
                    (CandidateLabel.kind == "TAG") | (CandidateLabel.user_id == actor.user.id),
                )
            )
        ]
    }


@router.delete("/candidate-labels/{label_id}")
def remove_label(label_id: str, db: Db, actor: Current):
    actor.require("talent.manage")
    row = db.get(CandidateLabel, label_id)
    if not row or row.user_id != actor.user.id:
        raise DomainError("Marcação não encontrada.", 404)
    audit(db, actor, "candidate.label_removed", row)
    db.delete(row)
    return {"message": "Marcação removida."}


@router.get("/candidates/{candidate_id}/processes")
def candidate_processes(candidate_id: str, db: Db, actor: Current):
    from app.api.applications import application_view
    from app.core.permissions import candidate_access

    candidate_access(db, actor, candidate_id)
    actor.require("candidate.view")
    query = select(Application).where(
        Application.candidate_id == candidate_id,
        Application.vacancy_id.in_(select(Vacancy.id).where(vacancy_scope(actor))),
    )
    return {
        "items": [
            application_view(db, actor, row)
            for row in db.scalars(query.order_by(Application.created_at.desc()).limit(100))
        ]
    }
