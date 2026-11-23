from html import escape
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Current, Db
from app.models import ConfigRecord, PipelineStage, Vacancy
from app.repositories.common import page, serialize
from app.services.smtp_config import smtp_runtime

router = APIRouter(tags=["Portal público"])


@router.get("/public/postal-code/{postal_code}")
def postal_code_lookup(postal_code: str, actor: Current):
    import httpx
    if len(postal_code) != 8 or not postal_code.isascii() or not postal_code.isdigit():
        raise DomainError("Informe um CEP com oito dígitos.", 422, "INVALID_CEP")
    try:
        response = httpx.get(f"https://viacep.com.br/ws/{postal_code}/json/", timeout=6)
        response.raise_for_status()
        data = response.json()
        if data.get("erro"):
            raise DomainError("CEP não encontrado. Preencha o endereço manualmente.", 404, "CEP_NOT_FOUND")
        return {"neighborhood": data.get("bairro", ""), "city": data.get("localidade", ""), "state": data.get("uf", "")}
    except (httpx.HTTPError, ValueError):
        raise DomainError("Não foi possível consultar o CEP. Você pode preencher manualmente.", 503, "CEP_UNAVAILABLE")


def public_vacancy(row):
    allowed = {
        "responsibilities",
        "requirements",
        "desirable",
        "education",
        "experience",
        "benefits",
        "workload",
        "shift",
        "level",
        "position",
        "affirmative",
        "accessibility",
        "questions",
        "notice_id",
    }
    details = {key: value for key, value in row.details.items() if key in allowed}
    if not row.details.get("hide_salary", True):
        details["salary"] = row.details.get("salary")
        details["salary_range"] = row.details.get("salary_range")
    return {
        key: value
        for key, value in serialize(row).items()
        if key
        in {
            "id",
            "code",
            "slug",
            "title",
            "quantity",
            "description",
            "city",
            "state",
            "modality",
            "contract_type",
            "deadline",
            "published_at",
            "audience",
        }
    } | {"details": details}


def published(internal=False):
    return select(Vacancy).where(
        Vacancy.status == "PUBLISHED",
        Vacancy.confidential.is_(False),
        Vacancy.deadline > utcnow(),
        Vacancy.audience.in_(["INTERNAL", "BOTH"] if internal else ["EXTERNAL", "BOTH"]),
    )


@router.get("/public/branding")
def branding(db: Db):
    row = db.scalar(
        select(ConfigRecord)
        .where(ConfigRecord.kind == "branding", ConfigRecord.active.is_(True))
        .order_by(ConfigRecord.updated_at.desc())
        .limit(1)
    )
    return (
        row.data
        if row
        else {
            "platform_name": "Porto Aurora Talentos",
            "organization_name": "Porto Aurora",
            "description": "",
            "timezone": "America/Belem",
            "brand_color": "#145c67",
        }
    )


@router.get("/public/privacy")
def notices(db: Db):
    return {
        "items": [
            serialize(row, {"created_by"})
            for row in db.scalars(
                select(ConfigRecord)
                .where(ConfigRecord.kind == "privacy-notices", ConfigRecord.active.is_(True))
                .order_by(ConfigRecord.created_at.desc())
                .limit(100)
            )
        ]
    }


@router.get("/public/vacancies")
def vacancies(
    db: Db,
    q: str = "",
    city: str = "",
    state: str = "",
    modality: str = "",
    contract_type: str = "",
    level: str = "",
    shift: str = "",
    position: str = "",
    affirmative: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    query = published().where(
        or_(Vacancy.title.ilike("%" + q + "%"), Vacancy.description.ilike("%" + q + "%"))
    )
    for name, value in {
        "city": city,
        "state": state,
        "modality": modality,
        "contract_type": contract_type,
    }.items():
        if value:
            query = query.where(getattr(Vacancy, name) == value)
    for name, value in {
        "level": level,
        "shift": shift,
        "position": position,
        "affirmative": affirmative,
    }.items():
        if value:
            query = query.where(Vacancy.details[name].astext == value)
    return page(
        db, query.order_by(Vacancy.published_at.desc()), page_number, page_size, public_vacancy
    )


@router.get("/public/vacancies/{slug}")
def vacancy(slug: str, db: Db):
    row = db.scalar(published().where(Vacancy.slug == slug))
    if not row:
        raise DomainError("Vaga não encontrada ou encerrada.", 404)
    stages = db.scalars(
        select(PipelineStage)
        .where(PipelineStage.vacancy_id == row.id)
        .order_by(PipelineStage.position)
    )
    return public_vacancy(row) | {
        "stages": [{"name": stage.name, "position": stage.position} for stage in stages]
    }


def internal_vacancy_listing(db, q, city, modality, page_number):
    query = published(True).where(or_(
        Vacancy.title.ilike("%" + q + "%"), Vacancy.description.ilike("%" + q + "%")
    ))
    for name, value in {"city": city, "modality": modality}.items():
        if value:
            query = query.where(getattr(Vacancy, name) == value)
    return page(
        db,
        query.order_by(Vacancy.published_at.desc()),
        page_number,
        25,
        public_vacancy,
    )


@router.get("/public/internal-vacancies")
def visible_internal_vacancies(
    db: Db, q: str = "", city: str = "", modality: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    return internal_vacancy_listing(db, q, city, modality, page_number)


@router.get("/internal/vacancies")
def internal_vacancies(
    db: Db, actor: Current, q: str = "", city: str = "", modality: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
):
    actor.require("internal.view")
    return internal_vacancy_listing(db, q, city, modality, page_number)


def vacancy_html(slug: str, db):
    row = db.scalar(published().where(Vacancy.slug == slug))
    if not row:
        raise DomainError("Vaga não encontrada ou encerrada.", 404)
    # Social crawlers receive escaped record-specific metadata; client then loads the same route.
    import httpx

    try:
        response = httpx.get("http://frontend:80/index.html", timeout=5)
        response.raise_for_status()
        html = response.text
    except httpx.HTTPError as exc:
        raise DomainError("Portal temporariamente indisponível.", 503) from exc
    title = escape(row.title + " | Porto Aurora Talentos")
    description = escape(row.description[:220], quote=True)
    canonical = escape(settings().public_url + "/carreiras/vagas/" + row.slug, quote=True)
    html = html.replace("<title>Porto Aurora Talentos</title>", "<title>" + title + "</title>")
    tags = f'<meta property="og:title" content="{title}"/><meta property="og:description" content="{description}"/><meta property="og:type" content="website"/><meta property="og:url" content="{canonical}"/><link rel="canonical" href="{canonical}"/>'
    return HTMLResponse(html.replace("</head>", tags + "</head>"))


@router.get("/internal/vacancies/{slug}")
def internal_vacancy(slug: str, db: Db, actor: Current):
    actor.require("internal.view")
    row = db.scalar(published(True).where(Vacancy.slug == slug))
    if not row:
        raise DomainError("Vaga não encontrada ou encerrada.", 404)
    stages = db.scalars(
        select(PipelineStage)
        .where(PipelineStage.vacancy_id == row.id)
        .order_by(PipelineStage.position)
    )
    return public_vacancy(row) | {
        "stages": [{"name": stage.name, "position": stage.position} for stage in stages]
    }


@router.get("/public/features")
def public_features(db: Db):
    return {
        "quick_application": smtp_runtime(db).enabled,
        "ldap": settings().ldap_enabled,
        "test_email": getattr(smtp_runtime(db), "test_mode", False),
    }
