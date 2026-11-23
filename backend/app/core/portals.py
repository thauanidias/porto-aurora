from urllib.parse import urlsplit

from fastapi import Request
from sqlalchemy import select

from app.core.config import settings
from app.core.errors import DomainError
from app.models import RolePermission, UserRole


def user_area(db, user):
    if user.kind != "INTERNAL":
        return "CANDIDATO"
    permissions = set(db.scalars(
        select(RolePermission.permission)
        .join(UserRole, RolePermission.role_id == UserRole.role_id)
        .where(UserRole.user_id == user.id)
    ))
    return "GESTOR" if "request.create" in permissions and not (
        {"vacancy.create", "request.approve"} & permissions
    ) else "RH"


def request_area(request: Request):
    cfg = settings()
    if not cfg.rh_url or not cfg.manager_url:
        return None
    areas = {urlsplit(url).hostname: area for area, url in (
        ("CANDIDATO", cfg.public_url), ("RH", cfg.rh_url), ("GESTOR", cfg.manager_url)
    )}
    area = areas.get(request.url.hostname)
    if not area:
        raise DomainError("Endereço de acesso não autorizado.", 403, "WRONG_ACCESS_HOST")
    return area


def require_portal(request: Request, db, user):
    area = request_area(request)
    if area and area != user_area(db, user):
        raise DomainError("Utilize o endereço de acesso do seu perfil.", 403, "WRONG_ACCESS_AREA")


def user_portal_url(db, user, fallback):
    cfg = settings()
    area = user_area(db, user)
    return {"RH": cfg.rh_url, "GESTOR": cfg.manager_url}.get(area) or fallback
