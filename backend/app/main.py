import ipaddress
import json
import logging
import socket
import time
from functools import lru_cache
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import ValidationError
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError
from starlette.exceptions import HTTPException

from app.api import (
    activity_links,
    admin,
    analytics,
    applications,
    assessments,
    auth,
    candidates,
    documents,
    forms,
    insights,
    intake,
    interviews,
    invitations,
    offers,
    operations,
    privacy,
    process_workflow,
    public,
    test_candidates,
    vacancies,
)
from app.core.config import settings
from app.core.db import engine
from app.core.errors import DomainError
from app.core.permissions import Current, Db

cfg = settings()
app = FastAPI(
    title="Porto Aurora Talentos",
    version="0.1.0",
    docs_url="/api/docs" if cfg.environment != "production" else None,
    openapi_url="/api/openapi.json" if cfg.environment != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
redis = Redis.from_url(
    cfg.redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True
)
requests_count = Counter("tgpm_requests_total", "API requests", ["method", "route", "status"])
latency = Histogram("tgpm_request_duration_seconds", "API request latency", ["route"])
logger = logging.getLogger("tgpm.api")


def error_response(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


@app.exception_handler(DomainError)
async def domain_error(request: Request, exc: DomainError):
    return error_response(request, exc.status, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
@app.exception_handler(ValidationError)
async def validation_error(request: Request, exc):
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return error_response(request, 422, "VALIDATION_ERROR", "Revise os campos informados.", details)


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc):
    return error_response(
        request,
        409,
        "INTEGRITY_CONFLICT",
        "O registro já existe ou possui vínculos que impedem esta ação.",
    )


@app.exception_handler(StaleDataError)
async def stale_error(request: Request, exc):
    return error_response(
        request,
        409,
        "VERSION_CONFLICT",
        "Este registro foi alterado por outra pessoa. Atualize a página.",
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc):
    return error_response(
        request,
        exc.status_code,
        "HTTP_ERROR",
        "Recurso não encontrado."
        if exc.status_code == 404
        else "Não foi possível concluir a solicitação.",
    )


@lru_cache(maxsize=2)
def trusted_proxy_addresses(time_bucket: int) -> set[str]:
    addresses: set[str] = set()
    for host in cfg.trusted_proxy_hosts.split(","):
        try:
            addresses.update(str(item[4][0]) for item in socket.getaddrinfo(host.strip(), None))
        except OSError:
            continue
    return addresses


@app.middleware("http")
async def observability(request: Request, call_next):
    peer = request.client.host if request.client else ""
    if request.headers.get("x-real-ip") and peer in trusted_proxy_addresses(
        int(time.monotonic() // 60)
    ):
        try:
            address = str(ipaddress.ip_address(request.headers["x-real-ip"]))
            request.scope["client"] = (address, 0)
        except ValueError:
            pass
    request.state.request_id = str(uuid4())
    started = time.monotonic()
    path = request.url.path
    if path.startswith("/api/v1/"):
        client = request.client.host if request.client else "unknown"
        authentication = request.method == "POST" and path.rsplit("/", 1)[-1] in {
            "login",
            "register",
            "request-link",
            "confirm",
        }
        key = (
            "limit:"
            + client
            + ":"
            + ("auth" if authentication else "upload" if path.endswith("/documents") else "api")
        )
        try:
            with redis.pipeline() as pipeline:
                pipeline.incr(key)
                pipeline.expire(key, 60, nx=True)
                count, _ = pipeline.execute()
            limit = 80 if authentication else 600
            if count > limit:
                return error_response(
                    request, 429, "RATE_LIMIT", "Muitas tentativas. Aguarde um minuto."
                )
        except Exception:
            if "/auth/" in path or request.method != "GET":
                return error_response(
                    request,
                    503,
                    "DEPENDENCY_UNAVAILABLE",
                    "Serviço temporariamente indisponível. Tente novamente.",
                )
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "unhandled_error",
                    "request_id": request.state.request_id,
                    "error_type": type(exc).__name__,
                }
            )
        )
        response = error_response(
            request,
            500,
            "INTERNAL_ERROR",
            "Não foi possível concluir a operação. Informe o código de atendimento ao suporte.",
        )
    route = getattr(request.scope.get("route"), "path", "unmatched")
    duration = time.monotonic() - started
    requests_count.labels(request.method, route, str(response.status_code)).inc()
    latency.labels(route).observe(duration)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store" if "/api/" in path else "no-cache"
    logger.info(
        json.dumps(
            {
                "service": "backend",
                "request_id": request.state.request_id,
                "route": route,
                "status": response.status_code,
                "duration": round(duration, 4),
            }
        )
    )
    return response


for module in (
    process_workflow,
    activity_links,
    test_candidates,
    intake,
    insights,
    forms,
    auth,
    admin,
    public,
    vacancies,
    candidates,
    applications,
    assessments,
    interviews,
    invitations,
    offers,
    documents,
    privacy,
    operations,
    analytics,
):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/liveness")
@app.get("/health")
def health():
    return {"status": "ok", "service": "Porto Aurora Talentos"}


@app.get("/readiness")
def readiness():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(text("SELECT version_num FROM alembic_version"))
        redis.ping()
        return {"status": "ready", "database": "ok", "redis": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/api/v1/metrics")
def metrics(actor: Current):
    actor.require("system.manage")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/carreiras/vagas/{slug}")
def job_html(slug: str, db: Db):
    return public.vacancy_html(slug, db)
