"""Application authorization from read-only AD attributes, never directory writes."""
from datetime import datetime, timedelta
from uuid import UUID

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.portals import user_area
from app.core.security import hash_verified_network_password, verify_password
from app.models import AuthSession, Role, User, UserRole


def directory_allowed(identity: dict) -> bool:
    cfg = settings()
    try:
        directory_id = str(UUID(identity.get("directory_id", "")))
    except (ValueError, TypeError, AttributeError):
        return False
    exceptions = {item.strip().lower() for item in cfg.ldap_rh_exception_ids.split(",") if item.strip()}
    departments = {item.strip().casefold() for item in cfg.ldap_rh_departments.split(",") if item.strip()}
    return directory_id in exceptions or identity.get("department", "").strip().casefold() in departments


def provision_rh(db, identity: dict):
    if not directory_allowed(identity):
        raise DomainError("O painel do RH é reservado às pessoas autorizadas de Recursos Humanos no AD.", 403, "RH_DIRECTORY_REQUIRED")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(identity.get("email", ""))).lower()
    except ValidationError as exc:
        raise DomainError("Sua conta no AD precisa ter um e-mail corporativo válido. Contate a TI.", 403) from exc
    if not identity.get("name", "").strip():
        raise DomainError("Sua conta no AD precisa ter um nome cadastrado. Contate a TI.", 403)
    directory_id = str(UUID(identity["directory_id"]))
    user = db.scalar(select(User).where(User.preferences["directory_id"].astext == directory_id).with_for_update())
    if user is None:
        user = db.scalar(select(User).where(User.email == email).with_for_update())
    if user:
        if not user.active or user.kind != "INTERNAL":
            raise DomainError("Sua conta está indisponível para acesso ao RH. Contate o administrador.", 403)
        if user.preferences.get("directory_id") not in (None, directory_id):
            raise DomainError("O vínculo de sua conta com o AD precisa ser conferido pela TI.", 403)
        if db.scalar(select(User.id).where(User.email == email, User.id != user.id)):
            raise DomainError("O e-mail corporativo já possui outro vínculo. Contate a TI.", 409)
        user.email = email
    else:
        user = User(name=identity["name"], email=email, kind="INTERNAL", active=True)
        db.add(user)
    preserve_hash = user.auth_source == "LDAP" and settings().ldap_rh_store_password and user.preferences.get("rh_password_enrolled_at")
    user.name, user.auth_source, user.email_verified = identity["name"], "LDAP", True
    if not preserve_hash:
        user.password_hash = None
    user.preferences = {**(user.preferences or {}), "directory_id": directory_id,
                        "network_username": identity["account"], "directory_department": identity["department"]}
    db.flush()
    role = db.scalar(select(Role).where(Role.name == settings().ldap_rh_role))
    if role is None:
        raise DomainError("O perfil de acesso do RH ainda não foi configurado.", 503)
    if not db.scalar(select(UserRole.user_id).where(UserRole.user_id == user.id, UserRole.role_id == role.id)):
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.flush()
    return user


def require_directory_session(db, user, session):
    """Enforce the policy on API calls and refresh, including old local sessions."""
    cfg = settings()
    if not cfg.ldap_rh_only or user_area(db, user) != "RH":
        return
    proof = session.directory_auth or {}
    if cfg.ldap_rh_access_mode == "saved":
        if (not saved_rh_authorized(db, user) or not proof.get("verified_at")
                or proof.get("directory_id") != user.preferences.get("directory_id")):
            raise DomainError("Entre com seu usuário e senha de rede para acessar o RH.", 401, "DIRECTORY_LOGIN_REQUIRED")
        return
    try:
        verified = datetime.fromisoformat(proof.get("verified_at", ""))
        valid_time = verified.tzinfo is not None and timedelta(0) <= utcnow() - verified <= timedelta(minutes=cfg.ldap_rh_session_minutes)
    except (ValueError, TypeError):
        valid_time = False
    if (user.auth_source != "LDAP" or not directory_allowed(proof) or not valid_time
            or proof.get("directory_id") != user.preferences.get("directory_id")):
        raise DomainError("Entre com seu usuário e senha de rede para acessar o RH.", 401, "DIRECTORY_LOGIN_REQUIRED")


def saved_rh_authorized(db, user) -> bool:
    if (not user.active or user.kind != "INTERNAL" or user.auth_source != "LDAP"
            or not user.preferences.get("network_username")):
        return False
    try:
        UUID(user.preferences.get("directory_id", ""))
    except (ValueError, TypeError, AttributeError):
        return False
    return bool(db.scalar(select(UserRole.user_id).join(Role, UserRole.role_id == Role.id).where(
        UserRole.user_id == user.id, Role.name.in_(["SUPER_ADMIN", "RH_ADMIN", "RECRUTADOR", "ANALISTA_RH"]))))


def saved_rh_login(db, username: str, password: str, *, revalidate_password: bool = False):
    from app.integrations.ldap import authenticate_saved_account, corporate_account
    account, _ = corporate_account(username)
    user = db.scalar(select(User).where(User.preferences["network_username"].astext == account))
    if not user or not saved_rh_authorized(db, user):
        raise DomainError("Sua conta não está liberada para o painel do RH. Contate o administrador.", 403, "RH_ACCOUNT_NOT_ENABLED")
    store = settings().ldap_rh_store_password
    enrolled = store and user.password_hash and user.preferences.get("rh_password_enrolled_at")
    if enrolled and not revalidate_password:
        if not verify_password(password, user.password_hash):
            raise DomainError("Usuário ou senha de acesso inválidos.", 401, "INVALID_CREDENTIALS")
        credential_source = "stored_hash"
    else:
        if not authenticate_saved_account(account, password, user.preferences["directory_id"]):
            raise DomainError("Usuário de rede ou senha inválidos.", 401, "INVALID_CREDENTIALS")
        credential_source = "directory"
        if store:
            user.password_hash = hash_verified_network_password(password)
            user.preferences = {**user.preferences, "rh_password_enrolled_at": utcnow().isoformat()}
            if revalidate_password:
                for session in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
                    session.revoked_at = utcnow()
            db.flush()
    return user, {"directory_id": user.preferences["directory_id"], "account": account,
                  "department": user.preferences.get("directory_department", ""),
                  "mode": "saved", "credential_source": credential_source, "verified_at": utcnow().isoformat()}
