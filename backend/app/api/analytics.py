from statistics import mean
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.core.db import utcnow
from app.core.permissions import Current, Db, vacancy_scope
from app.models import (
    Application,
    ApplicationScore,
    Evaluation,
    PipelineStage,
    StageHistory,
    SurveyResponse,
    User,
    Vacancy,
)

router = APIRouter(tags=["Análise de processo"])


@router.get("/analytics/processes")
def processes(db: Db, actor: Current):
    actor.require("report.view")
    now = utcnow()
    vacancies = list(db.scalars(select(Vacancy).where(vacancy_scope(actor))))
    ids = [v.id for v in vacancies]
    applications = list(db.scalars(select(Application).where(Application.vacancy_id.in_(ids))))
    app_ids = [a.id for a in applications]
    stages = list(db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id.in_(ids))))
    history = list(db.scalars(select(StageHistory).where(StageHistory.application_id.in_(app_ids))))
    pending_eval = set(
        db.scalars(
            select(Evaluation.application_id).where(
                Evaluation.application_id.in_(app_ids),
                Evaluation.independent.is_(True),
                Evaluation.submitted_at.is_(None),
            )
        )
    )
    stage_rows = []
    for stage in stages:
        visits = [h for h in history if h.stage_id == stage.id]
        active = [
            a for a in applications if a.stage_id == stage.id and a.status in {"ACTIVE", "RESERVE"}
        ]
        completed = {h.application_id for h in visits if h.left_at}
        entered = {h.application_id for h in visits}
        durations = [((h.left_at or now) - h.entered_at).total_seconds() / 3600 for h in visits]
        stage_rows.append(
            {
                "id": stage.id,
                "name": stage.name,
                "vacancy": next(v.title for v in vacancies if v.id == stage.vacancy_id),
                "entered": len(entered),
                "active": len(active),
                "advanced": len(completed),
                "conversion": round(len(completed) / len(entered) * 100, 2) if entered else None,
                "mean_hours": round(mean(durations), 2) if durations else None,
                "overdue": sum(
                    (now - a.stage_entered_at).total_seconds() > stage.sla_hours * 3600
                    for a in active
                ),
            }
        )
    capacity = []
    for uid in sorted({v.recruiter_id for v in vacancies}):
        user = db.get(User, uid)
        assigned = [
            v
            for v in vacancies
            if v.recruiter_id == uid and v.status in {"PUBLISHED", "PAUSED", "APPROVED"}
        ]
        active_apps = [
            a
            for a in applications
            if a.vacancy_id in {v.id for v in assigned}
            and a.status in {"ACTIVE", "RESERVE", "SELECTED", "PRE_ADMISSION"}
        ]
        capacity.append(
            {
                "id": uid,
                "name": user.name if user else "Usuário",
                "open_vacancies": len(assigned),
                "active_applications": len(active_apps),
            }
        )
    latest = {}
    for score in db.scalars(
        select(ApplicationScore)
        .where(ApplicationScore.application_id.in_(app_ids))
        .order_by(ApplicationScore.created_at)
    ):
        latest[score.application_id] = score
    distribution = []
    for status in [
        "ACTIVE",
        "SELECTED",
        "RESERVE",
        "REJECTED",
        "WITHDRAWN",
        "PRE_ADMISSION",
        "HIRED",
    ]:
        scores = [
            float(latest[a.id].total or 0)
            for a in applications
            if a.status == status
            and a.id in latest
            and latest[a.id].total is not None
            and a.id not in pending_eval
        ]
        distribution.append(
            {
                "id": status,
                "status": status,
                "count": len(scores),
                "mean_score": round(mean(scores), 2) if scores else None,
            }
        )
    response_scores = [
        r.answers.get("nps")
        for r in db.scalars(
            select(SurveyResponse).where(
                SurveyResponse.candidate_id.in_({a.candidate_id for a in applications})
            )
        )
    ]
    nps = [n for n in response_scores if type(n) is int and 0 <= n <= 10]
    return {
        "stages": stage_rows,
        "capacity": capacity,
        "model_outcomes": distribution,
        "satisfaction": {
            "responses": len(nps),
            "nps": round((sum(n >= 9 for n in nps) - sum(n <= 6 for n in nps)) / len(nps) * 100, 2)
            if nps
            else None,
        },
        "withdrawal_rate": round(
            sum(a.status == "WITHDRAWN" for a in applications) / len(applications) * 100, 2
        )
        if applications
        else None,
        "formulas": {
            "conversion": "Candidaturas que saíram da etapa / candidaturas que entraram × 100; não indica aprovação.",
            "overdue": "Candidaturas ativas com permanência maior que o SLA da etapa.",
            "nps": "Percentual de notas 9–10 menos percentual de notas 0–6.",
            "model_outcomes": "Média dos últimos scores por situação; avaliações independentes pendentes excluídas. Associação descritiva, sem inferência causal.",
        },
    }


@router.get("/analytics/vacancies")
def vacancy_report(db: Db, actor: Current, q: str = "", status: str = "", month: str = "",
                   page_number: Annotated[int, Query(ge=1)] = 1):
    return vacancy_report_data(db, actor, q, status, page_number, month)


def vacancy_report_data(db, actor, q="", status="", page_number=1, month="", vacancy_id="", export=False):
    actor.require("report.view")
    conditions = [vacancy_scope(actor), or_(Vacancy.published_at.is_not(None),
                  Vacancy.status.in_(["PUBLISHED", "PAUSED", "CLOSED"]))]
    if q.strip():
        conditions.append(or_(Vacancy.title.ilike("%" + q.strip() + "%"),
                              Vacancy.code.ilike("%" + q.strip() + "%")))
    if status:
        conditions.append(Vacancy.status == status)
    if vacancy_id:
        conditions.append(Vacancy.id == vacancy_id)
    if month:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from app.core.errors import DomainError
        import re
        try:
            if not re.fullmatch(r"\d{4}-\d{2}", month):
                raise ValueError()
            year, number = map(int, month.split("-"))
            start = datetime(year, number, 1, tzinfo=ZoneInfo("America/Fortaleza"))
            end = datetime(year + (number == 12), 1 if number == 12 else number + 1, 1, tzinfo=start.tzinfo)
        except ValueError:
            raise DomainError("Informe um mês válido no formato AAAA-MM.")
        conditions.extend([Vacancy.published_at >= start, Vacancy.published_at < end])
    counts = select(
        Application.vacancy_id.label("vacancy_id"),
        func.count(Application.id).label("applications"),
        func.count(func.distinct(Application.candidate_id)).label("candidates"),
        func.count(Application.id).filter(Application.status.in_(["ACTIVE", "RESERVE"])).label("in_progress"),
        func.count(Application.id).filter(Application.status.in_(["SELECTED", "PRE_ADMISSION"])).label("selected"),
        func.count(Application.id).filter(Application.status == "HIRED").label("hired"),
        func.count(Application.id).filter(Application.status == "REJECTED").label("rejected"),
        func.count(Application.id).filter(Application.status == "WITHDRAWN").label("withdrawn"),
    ).group_by(Application.vacancy_id).subquery()
    keys = ["applications", "candidates", "in_progress", "selected", "hired", "rejected", "withdrawn"]
    records = db.execute(select(Vacancy, *[func.coalesce(counts.c[key], 0) for key in keys])
                         .outerjoin(counts, counts.c.vacancy_id == Vacancy.id).where(*conditions)
                         .order_by(Vacancy.published_at.desc().nullslast(), Vacancy.id)).all()
    totals = {key: sum(row[index + 1] for row in records) for index, key in enumerate(keys)}
    totals["vacancies"] = len(records)
    totals["positions"] = sum(row[0].quantity for row in records)
    totals["published"] = sum(row[0].status == "PUBLISHED" for row in records)
    current_page = records if export else records[(page_number - 1) * 25:page_number * 25]
    stage_counts = {}
    for vacancy_id, name, count in db.execute(
        select(Application.vacancy_id, PipelineStage.name, func.count(Application.id))
        .join(PipelineStage, PipelineStage.id == Application.stage_id)
        .where(Application.vacancy_id.in_([row[0].id for row in current_page]),
               Application.status.in_(["ACTIVE", "RESERVE", "SELECTED", "PRE_ADMISSION"]))
        .group_by(Application.vacancy_id, PipelineStage.id)
        .order_by(PipelineStage.position)
    ):
        stage_counts.setdefault(vacancy_id, []).append({"name": name, "count": count})
    items = []
    for vacancy, *values in current_page:
        items.append({"id": vacancy.id, "title": vacancy.title, "code": vacancy.code,
                      "status": vacancy.status, "audience": vacancy.audience,
                      "quantity": vacancy.quantity, "published_at": vacancy.published_at,
                      "stages": stage_counts.get(vacancy.id, []),
                      **dict(zip(keys, values, strict=True))})
    return {"items": items, "total": len(records), "page": page_number, "page_size": 25,
            "summary": totals}


@router.get("/analytics/vacancies/export.xlsx")
def export_vacancy_report(db: Db, actor: Current, month: str = "", vacancy_id: str = "", q: str = "", status: str = ""):
    from fastapi.responses import Response
    from app.core.errors import DomainError
    from app.services.vacancy_report_xlsx import build_report
    from app.services.events import audit
    if not month and not vacancy_id:
        raise DomainError("Escolha um mês ou uma vaga para exportar.")
    data = vacancy_report_data(db, actor, q, status, 1, month, vacancy_id, True)
    if vacancy_id and not data["items"]:
        raise DomainError("Vaga não encontrada nos filtros ou acesso não autorizado.", 404)
    content = build_report(db, actor, data, month)
    audit(db, actor, "report.vacancies_exported", actor.user, after={"month": month, "vacancy_id": vacancy_id, "vacancies": data["total"]})
    filename = "Porto Aurora-relatorio-vagas-" + (month if month else "vaga") + ".xlsx"
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="' + filename + '"', "Cache-Control": "no-store"})
