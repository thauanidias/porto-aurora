from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import APIRouter, Query
from pydantic import EmailStr, Field, SecretStr
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import PERMISSIONS, Current, Db
from app.core.security import encrypt, hash_password
from app.domain.rules import matches
from app.models import (
    AuthSession,
    ConfigRecord,
    ConfigRevision,
    ManagerAccessRequest,
    OrgUnit,
    Outbox,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.repositories.common import check_version, page, serialize
from app.schemas.auth import StrictModel
from app.schemas.configuration import SCHEMAS
from app.services.events import audit
from app.services.smtp_config import SMTP_CONFIG_KIND, smtp_record, smtp_runtime

router = APIRouter(tags=["Administração"])


@router.get("/registered-managers")
def registered_managers(db: Db, actor: Current, q: str = "", active: bool | None = None,
                        page_number: Annotated[int, Query(ge=1)] = 1,
                        page_size: Annotated[int, Query(ge=1, le=100)] = 25):
    actor.require("user.manage")
    manager_users = select(UserRole.user_id).join(Role, UserRole.role_id == Role.id).where(Role.name == "GESTOR")
    query = select(User).outerjoin(OrgUnit, User.org_unit_id == OrgUnit.id).where(
        User.id.in_(manager_users), User.kind == "INTERNAL", User.auth_source != "DIRECTORY_REFERENCE",
    )
    if q.strip():
        query = query.where(or_(User.name.ilike("%" + q.strip() + "%"),
                               User.email.ilike("%" + q.strip() + "%"),
                               OrgUnit.name.ilike("%" + q.strip() + "%")))
    if active is not None:
        query = query.where(User.active.is_(active))
    sectors: dict[str, str] = {}

    def prepare(rows):
        sectors.update({org.id: org.name for org in db.scalars(select(OrgUnit).where(
            OrgUnit.id.in_([row.org_unit_id for row in rows if row.org_unit_id]),
        ))})

    return page(db, query.order_by(User.name, User.id), page_number, page_size,
                lambda row: {"id": row.id, "name": row.name, "email": row.email,
                             "org_unit_name": sectors.get(row.org_unit_id, "Setor não informado"),
                             "active": row.active, "version": row.version, "created_at": row.created_at}, prepare=prepare)


@router.get("/manager-access-requests")
def manager_access_requests(db: Db, actor: Current):
    actor.require("user.manage")
    return page(db, select(ManagerAccessRequest).order_by(ManagerAccessRequest.created_at.desc()), 1, 100)


class ManagerAccessDecision(StrictModel):
    version: int
    org_unit_id: str | None = None
    approve: bool = True
    reason: str = Field(default="", max_length=2000)


@router.post("/manager-access-requests/{request_id}/review")
def review_manager_access(request_id: str, body: ManagerAccessDecision, db: Db, actor: Current):
    from app.api.auth import issue_link
    from app.services.manager_access import require_corporate_manager_email

    actor.require("user.manage")
    row = db.scalar(select(ManagerAccessRequest).where(ManagerAccessRequest.id == request_id).with_for_update())
    if not row:
        raise DomainError("Solicitação não encontrada.", 404)
    check_version(row, body.version)
    if row.status != "PENDING":
        raise DomainError("Esta solicitação já foi analisada.", 409)
    if not body.approve:
        if len(body.reason.strip()) < 5:
            raise DomainError("Informe o motivo da recusa.")
        row.status, row.reason, row.reviewed_by = "REJECTED", body.reason, actor.user.id
        audit(db, actor, "manager.access_rejected", row)
        return serialize(row)
    require_corporate_manager_email(row.email)
    org = db.get(OrgUnit, body.org_unit_id) if body.org_unit_id else None
    if not org or not org.active:
        raise DomainError("Selecione o setor do gestor.")
    role = db.scalar(select(Role).where(Role.name == "GESTOR"))
    if not role:
        raise DomainError("Perfil de gestor não configurado.", 409)
    permissions = set(db.scalars(select(RolePermission.permission).where(RolePermission.role_id == role.id)))
    if permissions - actor.permissions:
        raise DomainError("Você não pode atribuir o perfil de gestor.", 403)
    if db.scalar(select(User.id).where(User.email == row.email)):
        raise DomainError("Já existe uma conta para este e-mail.", 409)
    smtp = smtp_runtime(db)
    if not smtp.enabled and settings().environment == "production":
        raise DomainError("Configure o envio de e-mail antes de aprovar o acesso.", 409)
    user = User(name=row.name, email=row.email, kind="INTERNAL", org_unit_id=org.id,
                auth_source="LOCAL", active=True, email_verified=False, password_hash=None)
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    row.user_id, row.reviewed_by, row.status = user.id, actor.user.id, "APPROVED"
    path = issue_link(db, user, "SETUP", "/gestor")
    # Supply a first RH approval flow when the organization has none configured.
    if "config.manage" in actor.permissions and "request.approve" in actor.permissions and not db.scalar(
        select(ConfigRecord.id).where(ConfigRecord.kind == "workflows", ConfigRecord.active.is_(True),
                                      ConfigRecord.data["target"].astext == "REQUEST")
    ):
        workflow = ConfigRecord(kind="workflows", name="Solicitações de vaga — RH " + row.id[:8], active=True, created_by=actor.user.id,
                                data={"target": "REQUEST", "steps": [{"name": "Análise do RH", "approver_id": actor.user.id, "sla_hours": 48}]})
        db.add(workflow)
        db.flush()
        db.add(ConfigRevision(record_id=workflow.id, revision=1, data=workflow.data,
                              reason="Fluxo inicial para solicitações dos gestores", created_by=actor.user.id))
        audit(db, actor, "configuration.created", workflow)
    audit(db, actor, "manager.access_approved", row)
    return serialize(row) | {"test_setup_url": path if not smtp.enabled else None}


class ConfigInput(StrictModel):
    name: str = Field(min_length=2, max_length=180)
    data: dict[str, Any]
    active: bool = True
    version: int | None = None
    reason: str = Field(min_length=5)


def config_permission(actor, kind, write=False):
    if kind == "privacy-notices" or kind == "retention-policies":
        actor.require("privacy.manage" if write else "vacancy.view")
    elif write:
        actor.require("config.manage")
    elif not actor.permissions:
        raise DomainError("Acesso não autorizado.", 403)


@router.get("/configuration/schemas")
def schemas(actor: Current):
    if not actor.permissions:
        raise DomainError("Acesso não autorizado.", 403)
    return {kind: schema.model_json_schema() for kind, schema in SCHEMAS.items()}


@router.get("/configuration/{kind}")
def configurations(
    kind: str,
    db: Db,
    actor: Current,
    q: str = "",
    page_number: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
):
    config_permission(actor, kind)
    if kind not in SCHEMAS:
        raise DomainError("Catálogo não encontrado.", 404)
    return page(
        db,
        select(ConfigRecord)
        .where(ConfigRecord.kind == kind, ConfigRecord.name.ilike("%" + q + "%"))
        .order_by(ConfigRecord.name),
        page_number,
        page_size,
    )


@router.post("/configuration/{kind}", status_code=201)
def create_config(kind: str, body: ConfigInput, db: Db, actor: Current):
    config_permission(actor, kind, True)
    if kind not in SCHEMAS:
        raise DomainError("Catálogo não encontrado.", 404)
    data = SCHEMAS[kind].model_validate(body.data).model_dump()
    if kind == "automations":
        matches(data["conditions"], {})
    record = ConfigRecord(
        kind=kind, name=body.name, data=data, active=body.active, created_by=actor.user.id
    )
    db.add(record)
    db.flush()
    db.add(
        ConfigRevision(
            record_id=record.id, revision=1, data=data, reason=body.reason, created_by=actor.user.id
        )
    )
    audit(db, actor, "configuration.created", record, after={"name": body.name, "data": data})
    return serialize(record)


@router.put("/configuration/{kind}/{record_id}")
def update_config(kind: str, record_id: str, body: ConfigInput, db: Db, actor: Current):
    config_permission(actor, kind, True)
    row = db.get(ConfigRecord, record_id)
    if not row or row.kind != kind or kind not in SCHEMAS:
        raise DomainError("Configuração não encontrada.", 404)
    check_version(row, body.version or 0)
    before = serialize(row)
    row.name = body.name
    row.data = SCHEMAS[kind].model_validate(body.data).model_dump()
    row.active = body.active
    db.flush()
    db.add(
        ConfigRevision(
            record_id=row.id,
            revision=row.version,
            data=row.data,
            reason=body.reason,
            created_by=actor.user.id,
        )
    )
    audit(db, actor, "configuration.updated", row, before, serialize(row))
    return serialize(row)


@router.get("/configuration/{kind}/{record_id}/history")
def config_history(kind: str, record_id: str, db: Db, actor: Current):
    config_permission(actor, kind)
    row = db.get(ConfigRecord, record_id)
    if not row or row.kind != kind:
        raise DomainError("Registro não encontrado.", 404)
    return page(
        db,
        select(ConfigRevision)
        .where(ConfigRevision.record_id == record_id)
        .order_by(ConfigRevision.revision.desc()),
        1,
        100,
    )


class OrgInput(StrictModel):
    name: str = Field(min_length=2, max_length=180)
    code: str = Field(min_length=2, max_length=60)
    kind: str
    parent_id: str | None = None
    active: bool = True
    version: int | None = None


@router.get("/org")
def organizations(db: Db, actor: Current):
    if not actor.permissions:
        raise DomainError("Acesso não autorizado.", 403)
    query = select(OrgUnit)
    manager_only = "request.create" in actor.permissions and not (
        {"org.manage", "vacancy.all", "request.approve"} & actor.permissions
    )
    if manager_only:
        query = query.where(OrgUnit.id == actor.user.org_unit_id, OrgUnit.active.is_(True))
    return page(db, query.order_by(OrgUnit.name), 1, 100)


@router.post("/org", status_code=201)
def create_org(body: OrgInput, db: Db, actor: Current):
    actor.require("org.manage")
    if body.kind not in {
        "ORGANIZATION",
        "COMPANY",
        "ESTABLISHMENT",
        "DIRECTORATE",
        "MANAGEMENT",
        "COORDINATION",
        "SECTOR",
        "COST_CENTER",
        "POSITION",
    }:
        raise DomainError("Tipo de estrutura inválido.")
    if body.parent_id and not db.get(OrgUnit, body.parent_id):
        raise DomainError("Estrutura superior inválida.")
    row = OrgUnit(**body.model_dump(exclude={"version"}))
    db.add(row)
    audit(db, actor, "org.created", row, after=body.model_dump())
    return serialize(row)


@router.put("/org/{org_id}")
def update_org(org_id: str, body: OrgInput, db: Db, actor: Current):
    actor.require("org.manage")
    row = db.get(OrgUnit, org_id)
    if not row:
        raise DomainError("Estrutura não encontrada.", 404)
    check_version(row, body.version or 0)
    parent_id = body.parent_id
    seen = {row.id}
    while parent_id:
        if parent_id in seen:
            raise DomainError("A estrutura não pode formar ciclos.")
        seen.add(parent_id)
        parent = db.get(OrgUnit, parent_id)
        if not parent:
            raise DomainError("Estrutura superior inválida.")
        parent_id = parent.parent_id
    for key, value in body.model_dump(exclude={"version"}).items():
        setattr(row, key, value)
    audit(db, actor, "org.updated", row, after=body.model_dump())
    return serialize(row)


class UserInput(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    password: str | None = Field(default=None, min_length=6, max_length=128)
    auth_source: str = "LOCAL"
    org_unit_id: str | None = None
    roles: list[str] = Field(min_length=1)


@router.get("/users")
def users(db: Db, actor: Current, q: str = "", page_number: Annotated[int, Query(ge=1)] = 1):
    if not actor.permissions:
        raise DomainError("Acesso não autorizado.", 403)
    query = select(User).where(User.kind == "INTERNAL", User.name.ilike("%" + q + "%"))
    return page(
        db,
        query.order_by(User.name),
        page_number,
        100,
        lambda row: {
            "id": row.id,
            "name": row.name,
            "email": row.email if "user.manage" in actor.permissions else "",
            "active": row.active,
            "version": row.version,
            "org_unit_id": row.org_unit_id,
            "roles": list(
                db.scalars(
                    select(Role.name)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == row.id)
                )
            )
            if "user.manage" in actor.permissions
            else [],
        },
    )


@router.get("/managers")
def managers(db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1):
    actor.require("vacancy.view")
    manager_role = select(UserRole.user_id).join(Role, UserRole.role_id == Role.id).where(
        Role.name == "GESTOR"
    )
    query = select(User).where(
        User.kind == "INTERNAL",
        User.active.is_(True),
        or_(
            User.preferences["directory_manager"].as_boolean().is_(True),
            User.id.in_(manager_role),
        ),
    )
    return page(db, query.order_by(User.name), page_number, 100, lambda row: {
        "id": row.id,
        "name": row.name,
    })


@router.get("/recruiters")
def recruiters(db: Db, actor: Current, page_number: Annotated[int, Query(ge=1)] = 1):
    actor.require("vacancy.view")
    query = select(User).where(
        User.kind == "INTERNAL",
        User.active.is_(True),
        User.preferences["directory_recruiter"].as_boolean().is_(True),
    )
    return page(db, query.order_by(User.name), page_number, 100, lambda row: {
        "id": row.id,
        "name": row.name,
    })


@router.post("/users", status_code=201)
def create_user(body: UserInput, db: Db, actor: Current):
    actor.require("user.manage")
    if "GESTOR" in body.roles:
        from app.services.manager_access import require_corporate_manager_email

        require_corporate_manager_email(str(body.email))
        org = db.get(OrgUnit, body.org_unit_id) if body.org_unit_id else None
        if not org or not org.active:
            raise DomainError("Selecione o setor do gestor.")
    roles = list(db.scalars(select(Role).where(Role.name.in_(body.roles))))
    if len(roles) != len(set(body.roles)):
        raise DomainError("Perfil inválido.")
    granted = set(
        db.scalars(
            select(RolePermission.permission).where(
                RolePermission.role_id.in_([role.id for role in roles])
            )
        )
    )
    if granted - actor.permissions:
        raise DomainError("Você não pode atribuir este perfil.", 403)
    if body.auth_source not in {"LOCAL", "LDAP"} or (
        body.auth_source == "LOCAL" and not body.password
    ):
        raise DomainError("Conta local exige senha.")
    row = User(
        name=body.name,
        email=str(body.email).lower(),
        kind="INTERNAL",
        email_verified=True,
        password_hash=hash_password(body.password) if body.password else None,
        auth_source=body.auth_source,
        org_unit_id=body.org_unit_id,
    )
    db.add(row)
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=row.id, role_id=role.id))
    audit(db, actor, "user.created", row, after={"roles": body.roles})
    return serialize(row)


class UserStatus(StrictModel):
    active: bool
    reason: str = Field(min_length=5)
    version: int


@router.put("/users/{user_id}/status")
def user_status(user_id: str, body: UserStatus, db: Db, actor: Current):
    actor.require("user.manage")
    row = db.get(User, user_id)
    if not row or row.id == actor.user.id:
        raise DomainError("Não é possível alterar este usuário.")
    grants = set(
        db.scalars(
            select(RolePermission.permission)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == row.id)
        )
    )
    if grants - actor.permissions:
        raise DomainError("Você não pode alterar este nível de acesso.", 403)
    check_version(row, body.version)
    row.active = body.active
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == row.id, AuthSession.revoked_at.is_(None))
    ):
        session.revoked_at = utcnow()
    audit(
        db, actor, "user.status_changed", row, after={"active": body.active, "reason": body.reason}
    )
    return serialize(row)


@router.get("/roles")
def roles(db: Db, actor: Current):
    actor.require("user.manage")
    return {
        "items": [
            serialize(row)
            | {
                "permissions": list(
                    db.scalars(
                        select(RolePermission.permission).where(RolePermission.role_id == row.id)
                    )
                )
            }
            for row in db.scalars(select(Role).order_by(Role.name))
        ]
    }


class RoleInput(StrictModel):
    name: str = Field(min_length=3, max_length=60)
    permissions: list[str]
    version: int | None = None


@router.post("/roles", status_code=201)
def create_role(body: RoleInput, db: Db, actor: Current):
    actor.require("role.manage")
    if set(body.permissions) - PERMISSIONS:
        raise DomainError("Permissões inválidas.")
    row = Role(name=body.name)
    db.add(row)
    db.flush()
    for permission in set(body.permissions):
        db.add(RolePermission(role_id=row.id, permission=permission))
    audit(db, actor, "role.created", row, after={"permissions": body.permissions})
    return serialize(row)


@router.put("/roles/{role_id}")
def edit_role(role_id: str, body: RoleInput, db: Db, actor: Current):
    actor.require("role.manage")
    row = db.get(Role, role_id)
    if not row or row.name == "SUPER_ADMIN":
        raise DomainError("O perfil de contingência não pode ser alterado.")
    check_version(row, body.version or 0)
    if set(body.permissions) - PERMISSIONS:
        raise DomainError("Permissões inválidas.")
    for grant in db.scalars(select(RolePermission).where(RolePermission.role_id == row.id)):
        db.delete(grant)
    db.flush()
    for permission in set(body.permissions):
        db.add(RolePermission(role_id=row.id, permission=permission))
    row.name = body.name
    row.updated_at = utcnow()
    audit(db, actor, "role.updated", row, after={"permissions": body.permissions})
    return serialize(row)


@router.get("/permissions")
def permissions(db: Db, actor: Current):
    actor.require("role.manage")
    return {
        "items": [
            serialize(row) for row in db.scalars(select(Permission).order_by(Permission.name))
        ]
    }


@router.get("/settings")
def system_settings(db: Db, actor: Current):
    actor.require("config.manage")
    cfg = settings()
    return {
        "environment": cfg.environment,
        "version": "0.1.0",
        "smtp": smtp_runtime(db).enabled,
        "ldap": cfg.ldap_enabled,
        "graph": cfg.graph_enabled,
        "antimalware": cfg.clamav_enabled,
        "public_url": cfg.public_url,
    }


class SmtpSettingsInput(StrictModel):
    enabled: bool = False
    host: str = Field(default="smtp.office365.com", max_length=253)
    port: int = Field(default=587, ge=1, le=65535)
    auth_mode: Literal["basic", "oauth2"] = "oauth2"
    sender: str = Field(default="", max_length=320)
    username: str = Field(default="", max_length=320)
    password: SecretStr = Field(default=SecretStr(""), max_length=4096)
    tenant_id: str = Field(default="", max_length=100)
    client_id: str = Field(default="", max_length=100)
    client_secret: SecretStr = Field(default=SecretStr(""), max_length=4096)
    refresh_token: SecretStr = Field(default=SecretStr(""), max_length=20000)
    access_token: SecretStr = Field(default=SecretStr(""), max_length=20000)
    starttls: bool = True
    validate_tls: bool = True
    notifications_enabled: bool = True
    public_url: str = Field(default="", max_length=500)
    test_recipient: EmailStr | None = None
    version: int | None = None


@router.get("/smtp-settings")
def get_smtp_settings(db: Db, actor: Current):
    actor.require("config.manage")
    row = smtp_record(db)
    smtp = smtp_runtime(db)
    local = smtp.test_mode
    configured = bool(smtp.sender and smtp.host and (smtp.username and smtp.password if smtp.auth_mode == "basic" else
        smtp.access_token or smtp.tenant_id and smtp.client_id and (smtp.client_secret or smtp.refresh_token))) and not local
    return {"enabled": smtp.enabled and not local, "host": "smtp.office365.com" if local else smtp.host,
        "port": 587 if local else smtp.port, "auth_mode": "oauth2" if local else smtp.auth_mode,
        "sender": "" if local else smtp.sender, "username": smtp.username, "tenant_id": smtp.tenant_id,
        "client_id": smtp.client_id, "public_url": smtp.public_url, "starttls": True if local else smtp.starttls,
        "validate_tls": smtp.validate_tls, "notifications_enabled": smtp.notifications_enabled,
        "secret_configured": bool(smtp.client_secret), "password_configured": bool(smtp.password),
        "refresh_token_configured": bool(smtp.refresh_token), "access_token_configured": bool(smtp.access_token),
        "configured": configured, "test_mode": local, "test_recipient": (row.data.get("test_recipient") if row else None) or actor.user.email,
        "last_test_at": row.data.get("last_test_at") if row else None, "version": row.version if row else None}


@router.put("/smtp-settings")
def save_smtp_settings(body: SmtpSettingsInput, db: Db, actor: Current):
    actor.require("config.manage")
    row = smtp_record(db)
    if row:
        check_version(row, body.version or 0)
    elif body.version is not None:
        raise DomainError("A configuração foi alterada. Atualize a página.", 409)
    sender, host = body.sender.strip().lower(), body.host.strip().lower()
    if sender and ("@" not in sender or any(char in sender for char in " \r\n")):
        raise DomainError("Informe um e-mail remetente válido.")
    if host and not all(char.isalnum() or char in ".-" for char in host):
        raise DomainError("Informe somente o nome do servidor SMTP, sem protocolo ou caminho.")
    for value, name in ((body.tenant_id.strip(), "Tenant ID"), (body.client_id.strip(), "Client ID")):
        if value and body.auth_mode == "oauth2":
            try:
                UUID(value)
            except ValueError as exc:
                raise DomainError(f"{name} deve ser um identificador válido.") from exc
    public_url = body.public_url.strip().rstrip("/")
    parsed = urlparse(public_url)
    if public_url and (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment):
        raise DomainError("Informe um endereço público HTTP ou HTTPS válido.")
    data = {"enabled": body.enabled, "host": host, "port": body.port, "auth_mode": body.auth_mode,
        "replace_local_mode": True,
        "sender": sender, "username": body.username.strip(), "tenant_id": body.tenant_id.strip(), "client_id": body.client_id.strip(),
        "public_url": public_url, "starttls": body.starttls, "validate_tls": body.validate_tls,
        "notifications_enabled": body.notifications_enabled, "test_recipient": str(body.test_recipient) if body.test_recipient else actor.user.email}
    for field, storage in [("password", "encrypted_password"), ("client_secret", "encrypted_secret"),
                           ("refresh_token", "encrypted_refresh_token"), ("access_token", "encrypted_access_token")]:
        secret = getattr(body, field).get_secret_value()
        data[storage] = encrypt(secret) if secret else row.data.get(storage, "") if row else ""
    if body.enabled:
        if not all((sender, host, public_url)):
            raise DomainError("Preencha remetente, servidor SMTP e endereço público para ativar.")
        if not body.starttls and body.port != 465:
            raise DomainError("Ative STARTTLS para enviar credenciais ao servidor SMTP. Na porta 465, o TLS é direto.")
        if body.auth_mode == "basic" and not (data["username"] and data["encrypted_password"]):
            raise DomainError("Preencha o usuário SMTP e a senha.")
        if body.auth_mode == "oauth2" and not (data["encrypted_access_token"] or data["tenant_id"] and data["client_id"] and (data["encrypted_secret"] or data["encrypted_refresh_token"])):
            raise DomainError("Preencha os dados OAuth2 da aplicação e o segredo ou refresh token.")
        if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise DomainError("O endereço público não pode apontar para este computador.")
        if settings().environment == "production" and parsed.scheme != "https":
            raise DomainError("O endereço público deve usar HTTPS em produção.")
    if not row and settings().test_email_enabled:
        for pending in db.scalars(select(Outbox).where(Outbox.kind == "EMAIL", Outbox.status.in_(["PENDING", "RETRY"]))):
            pending.payload = {**pending.payload, "delivery_mode": "test"}
    if row:
        row.data, row.active = data, True
    else:
        row = ConfigRecord(kind=SMTP_CONFIG_KIND, name="Canal de e-mail", data=data, active=True, created_by=actor.user.id)
        db.add(row)
    db.flush()
    audit(db, actor, "smtp.settings.updated", row, after={"enabled": body.enabled, "sender": sender, "auth_mode": body.auth_mode})
    return get_smtp_settings(db, actor)


class SmtpTestInput(StrictModel):
    recipient: EmailStr | None = None


@router.post("/smtp-settings/test")
def send_smtp_test(db: Db, actor: Current, body: SmtpTestInput | None = None):
    from app.integrations.delivery import send_email

    actor.require("config.manage")
    smtp = smtp_runtime(db)
    if not smtp.enabled:
        raise DomainError("Ative e salve o canal de e-mail antes de testar.")
    record = smtp_record(db)
    recipient = str(body.recipient) if body and body.recipient else (record.data.get("test_recipient") if record else None) or actor.user.email
    try:
        send_email({"recipient": recipient, "subject": "Teste de envio do Porto Aurora Talentos",
            "body": "Olá!\n\nEste é um teste de comunicação da Porto Aurora Talentos. Estamos conferindo o envio das nossas notificações com a identidade visual da Porto Aurora.\n\nConfira se a logomarca e o conteúdo aparecem corretamente no seu aplicativo de e-mail.", "delivery_mode": "test" if smtp.test_mode else "real"}, "smtp-test:" + str(uuid4()), db=db)
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("O teste de envio falhou. Confira a conexão, a autenticação e as permissões da conta remetente.", 502, "SMTP_TEST_FAILED") from exc
    row = smtp_record(db)
    if row:
        row.data = {**row.data, "last_test_at": utcnow().isoformat()}
        audit(db, actor, "smtp.test.sent", row)
    return {"message": "Servidor SMTP aceitou o e-mail de teste. Confira a caixa de entrada e o spam.", "recipient": recipient}


class AccessUpdate(StrictModel):
    roles: list[str] = Field(min_length=1)
    org_unit_id: str | None = None
    version: int
    reason: str = Field(min_length=10)


@router.put("/users/{user_id}/access")
def update_access(user_id: str, body: AccessUpdate, db: Db, actor: Current):
    actor.require("user.manage")
    row = db.get(User, user_id)
    if not row or row.id == actor.user.id or row.kind != "INTERNAL":
        raise DomainError("Usuário inválido para esta alteração.")
    check_version(row, body.version)
    roles = list(db.scalars(select(Role).where(Role.name.in_(body.roles))))
    if len(roles) != len(set(body.roles)):
        raise DomainError("Perfil inválido.")
    existing = set(
        db.scalars(
            select(RolePermission.permission)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == row.id)
        )
    )
    new = set(
        db.scalars(
            select(RolePermission.permission).where(
                RolePermission.role_id.in_([r.id for r in roles])
            )
        )
    )
    if (existing | new) - actor.permissions:
        raise DomainError("Você não pode conceder ou alterar este nível de acesso.", 403)
    if body.org_unit_id and not db.get(OrgUnit, body.org_unit_id):
        raise DomainError("Estrutura inválida.")
    for grant in db.scalars(select(UserRole).where(UserRole.user_id == row.id)):
        db.delete(grant)
    db.flush()
    for role in roles:
        db.add(UserRole(user_id=row.id, role_id=role.id))
    row.org_unit_id = body.org_unit_id
    row.updated_at = utcnow()
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == row.id, AuthSession.revoked_at.is_(None))
    ):
        session.revoked_at = utcnow()
    audit(
        db,
        actor,
        "user.access_changed",
        row,
        after={"roles": body.roles, "org_unit_id": body.org_unit_id, "reason": body.reason},
    )
    return serialize(row)
