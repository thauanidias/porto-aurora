import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Request, Response
from pydantic import EmailStr, Field
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import Actor, Current, Db
from app.core.portals import request_area, require_portal, user_area, user_portal_url
from app.core.security import access_token, digest, hash_password, verify_password
from app.models import (
    AuthSession,
    AuthToken,
    Candidate,
    ConfigRecord,
    Consent,
    ConsentReceipt,
    EmployeeAccessRequest,
    ManagerAccessRequest,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.repositories.common import serialize
from app.schemas.auth import (
    EmailRequest,
    Login,
    PasswordChange,
    Register,
    StrictModel,
    TokenRequest,
)
from app.services.events import audit, email, notify
from app.services.smtp_config import smtp_runtime

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class ManagerRegistration(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    department: str = Field(min_length=2, max_length=180)


class EmployeeRegistration(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    department: str = Field(default="", max_length=180)
    network_username: str = Field(default="", max_length=180)


@router.post("/register-employee", status_code=201)
def register_employee(body: EmployeeRegistration, db: Db):
    from app.services.employee_access import (
        network_username,
        send_registration_code,
    )

    address = str(body.email).strip().lower()
    username = network_username(body.network_username) if body.network_username else "pending-" + secrets.token_hex(16)
    if len(body.name.strip()) < 3:
        raise DomainError("Informe seu nome completo.")
    existing = db.scalar(
        select(EmployeeAccessRequest).where(or_(
            EmployeeAccessRequest.email == address,
            EmployeeAccessRequest.network_username == username,
        )).with_for_update()
    )
    if db.scalar(select(User.id).where(User.email == address)):
        raise DomainError("Já existe uma conta ou solicitação para estes dados. Entre em contato com o RH.", 409)
    if existing:
        if existing.email != address or (body.network_username and existing.network_username != username) or existing.status != "PENDING":
            raise DomainError("Já existe uma conta ou solicitação para estes dados. Entre em contato com o RH.", 409)
        if existing.email_confirmed_at and not existing.network_username.startswith("pending-"):
            raise DomainError("Seu e-mail já está confirmado. Entre com seu usuário de rede.", 409)
        if existing.email_code_sent_at and utcnow() < existing.email_code_sent_at + timedelta(seconds=60):
            return {"registration_id": existing.id, "verification_required": True, "expires_in": 600,
                    "resend_after": max(1, 60 - int((utcnow() - existing.email_code_sent_at).total_seconds())),
                    "message": "Confira o código enviado para seu e-mail."}
        existing.email_confirmed_at = None
        return send_registration_code(db, existing)
    row = EmployeeAccessRequest(name=body.name.strip(), email=address,
                                network_username=username, department=body.department.strip())
    db.add(row)
    db.flush()
    return send_registration_code(db, row)


class EmployeeCodeRequest(StrictModel):
    registration_id: str = Field(min_length=36, max_length=36)


class EmployeeCodeConfirmation(EmployeeCodeRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


@router.post("/employee-email-code/resend")
def resend_employee_code(body: EmployeeCodeRequest, db: Db):
    from app.services.employee_access import send_registration_code

    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.id == body.registration_id).with_for_update())
    if not row or row.status != "PENDING":
        raise DomainError("Cadastro não encontrado ou já concluído.", 404)
    return send_registration_code(db, row)


@router.post("/employee-email-code/confirm")
def confirm_employee_code(body: EmployeeCodeConfirmation, db: Db):
    from app.services.employee_access import confirm_registration_code

    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.id == body.registration_id).with_for_update())
    if not row or row.status != "PENDING":
        raise DomainError("Cadastro não encontrado ou já concluído.", 404)
    return confirm_registration_code(db, row, body.code)


class EmployeeCompletion(StrictModel):
    completion_token: str = Field(max_length=2048)
    password: str = Field(min_length=6, max_length=6)


@router.post("/employee-registration/complete")
def complete_employee_registration(body: EmployeeCompletion, db: Db):
    import json

    from app.core.security import decrypt

    try:
        proof = json.loads(decrypt(body.completion_token))
        if proof.get("purpose") != "employee-completion" or proof["expires_at"] <= utcnow().timestamp():
            raise ValueError()
        registration_id = proof["registration_id"]
    except Exception as exc:
        raise DomainError("Confirmação inválida ou expirada. Confirme seu e-mail novamente.", 400) from exc
    row = db.scalar(select(EmployeeAccessRequest).where(EmployeeAccessRequest.id == registration_id).with_for_update())
    if not row or not row.email_confirmed_at or row.status != "PENDING" or not row.network_username.startswith("pending-"):
        raise DomainError("Cadastro não disponível para conclusão.", 409)
    if db.scalar(select(User.id).where(User.email == row.email)):
        raise DomainError("Já existe uma conta para este e-mail. Contate o RH.", 409)
    role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
    if not role:
        raise DomainError("Perfil de colaborador não configurado. Contate o RH.", 503)
    user = User(name=row.name, email=row.email, kind="CANDIDATO", auth_source="LOCAL",
                active=True, email_verified=True, password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.add(Candidate(user_id=user.id, name=user.name, email=user.email))
    row.user_id, row.status = user.id, "VERIFIED"
    return {"message": "Cadastro concluído. Entre com o e-mail cadastrado e sua senha."}


@router.post("/register-manager", status_code=201)
def register_manager(body: ManagerRegistration, db: Db):
    from app.services.manager_access import require_corporate_manager_email

    address = str(body.email).lower()
    require_corporate_manager_email(address)
    if not body.name.strip() or not body.department.strip():
        raise DomainError("Informe nome e setor.")
    if db.scalar(select(User.id).where(User.email == address)) or db.scalar(
        select(ManagerAccessRequest.id).where(ManagerAccessRequest.email == address)
    ):
        raise DomainError("Já existe uma conta ou solicitação para este e-mail. Entre em contato com o RH.", 409)
    row = ManagerAccessRequest(name=body.name.strip(), email=address,
                               department=body.department.strip())
    db.add(row)
    db.flush()
    reviewers = db.scalars(select(User.id).join(UserRole).join(RolePermission,
        RolePermission.role_id == UserRole.role_id).where(
        RolePermission.permission == "user.manage", User.active.is_(True), User.kind == "INTERNAL"
    ).distinct())
    for reviewer in reviewers:
        notify(db, reviewer, "Novo pedido de acesso de gestor", row.name + " solicitou acesso ao setor " + row.department,
               "MANAGER_ACCESS", "/app/acessos-gestores")
    return {"message": "Pedido enviado ao RH. Após a aprovação, você receberá por e-mail o link para criar sua senha."}


def session_response(db, user, request, response, directory_auth=None):
    require_portal(request, db, user)
    if (
        settings().email_verification_required
        and user.kind == "CANDIDATO"
        and not user.email_verified
    ):
        raise DomainError("Confirme seu e-mail antes de entrar.", 403, "EMAIL_NOT_VERIFIED")
    raw = secrets.token_urlsafe(48)
    now = utcnow()
    session = AuthSession(
        user_id=user.id,
        token_hash=digest(raw),
        expires_at=now + timedelta(days=settings().refresh_days),
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:300],
        directory_auth=directory_auth or {},
    )
    db.add(session)
    user.first_login = user.first_login or now
    user.last_login = now
    db.flush()
    from app.services.directory_access import require_directory_session
    require_directory_session(db, user, session)
    if directory_auth and user_area(db, user) == "RH":
        from app.services.rh_welcome import queue_welcome
        queue_welcome(db, user, session.id)
    set_cookie(response, raw)
    return {
        "access_token": access_token(user.id, session.id),
        "token_type": "bearer",
        "user": serialize(user),
        "expires_in": settings().access_minutes * 60,
    }


def set_cookie(response, value):
    response.set_cookie(
        "tgpm_refresh",
        value,
        httponly=True,
        secure=settings().environment == "production",
        samesite="strict",
        path="/api/v1/auth",
        max_age=settings().refresh_days * 86400,
    )


def issue_link(db, user, purpose, return_to=None):
    smtp = smtp_runtime(db)
    raw = secrets.token_urlsafe(48)
    db.add(
        AuthToken(
            user_id=user.id,
            token_hash=digest(raw),
            purpose=purpose,
            expires_at=utcnow() + timedelta(minutes=30),
        )
    )
    path = "/confirmar#token=" + raw + "&purpose=" + purpose
    if return_to:
        path += "&next=" + quote(return_to, safe="")
    if smtp.enabled:
        email(
            db,
            user.email,
            "Confirme seu e-mail e crie sua senha no Porto Aurora Talentos"
            if purpose == "SETUP"
            else "Confirme seu e-mail no Porto Aurora Talentos"
            if purpose == "VERIFY"
            else "Acesso ao Porto Aurora Talentos",
            (
                "Para confirmar seu e-mail e criar sua senha, use este link em até 30 minutos: "
                if purpose == "SETUP"
                else "Use este link em até 30 minutos: "
            )
            + user_portal_url(db, user, smtp.public_url).rstrip("/") + path,
            "auth:" + digest(raw),
        )
    return path


@router.post("/register", status_code=201)
def register(body: Register, db: Db, request: Request, response: Response):
    smtp = smtp_runtime(db)
    if not smtp.enabled and settings().environment == "production":
        raise DomainError("O cadastro por e-mail está temporariamente indisponível.", 503)
    notice = db.get(ConfigRecord, body.notice_id) if body.notice_id else None
    receipt = db.get(ConsentReceipt, body.receipt_id) if body.receipt_id else None
    if body.receipt_id and (
        not receipt
        or receipt.email != str(body.email)
        or receipt.name != body.name.strip()
        or receipt.context != "CADASTRO"
        or receipt.document_code != "FORM-PPO-RH-002.09"
    ):
        raise DomainError("Aceite o termo com o mesmo nome e e-mail do cadastro.")
    if not body.defer_consent_to_profile and (not body.consent or (
        not receipt and (not notice or notice.kind != "privacy-notices" or not notice.active)
    )):
        raise DomainError("Leia e aceite o aviso de privacidade vigente.")
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise DomainError(
            "Não foi possível cadastrar este e-mail. Tente entrar ou recuperar o acesso.", 409
        )
    user = User(
        name=body.name,
        email=str(body.email),
        password_hash=None,
        kind="CANDIDATO",
    )
    db.add(user)
    db.flush()
    candidate = Candidate(user_id=user.id, name=body.name, email=str(body.email))
    db.add(candidate)
    db.flush()
    role = db.scalar(select(Role).where(Role.name == "CANDIDATO"))
    if role:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    if not body.defer_consent_to_profile:
        db.add(
            Consent(
                candidate_id=candidate.id,
                notice_id=notice.id if notice else None,
                notice_version=notice.version if notice else 9,
                notice_snapshot=(
                    {
                        "text": "\n".join(receipt.document_snapshot["paragraphs"]),
                        "document_code": receipt.document_code,
                        "receipt_protocol": receipt.protocol,
                        "receipt_id": receipt.id,
                    }
                    if receipt
                    else notice.data if notice else {}
                ),
                purpose="RECRUITMENT",
                granted=True,
                ip=request.client.host if request.client else "",
            )
        )
    setup_path = issue_link(db, user, "SETUP", body.return_to)
    return {
        "verification_required": True,
        "email_delivery_enabled": smtp.enabled,
        "test_setup_url": setup_path if not smtp.enabled else None,
        "message": "Cadastro recebido. Abra o link enviado por e-mail para confirmar seu endereço e criar sua senha."
        if smtp.enabled
        else "Cadastro recebido. Use o link de teste abaixo para criar sua senha. O e-mail ainda não está ativo.",
    }


@router.post("/login")
def login(body: Login, db: Db, request: Request, response: Response):
    directory_proof = None
    if settings().ldap_rh_only and body.source == "LDAP" and body.area in (None, "RH"):
        from app.integrations.ldap import authenticate_directory
        from app.services.directory_access import provision_rh
        if settings().ldap_rh_access_mode == "saved":
            from app.services.directory_access import saved_rh_login
            user, directory_proof = saved_rh_login(db, body.email, body.password, revalidate_password=body.revalidate_network_password)
        else:
            identity = authenticate_directory(body.email, body.password)
            if identity is None:
                raise DomainError("Usuário de rede ou senha inválidos.", 401, "INVALID_CREDENTIALS")
            user = provision_rh(db, identity)
            directory_proof = {**identity, "verified_at": utcnow().isoformat()}
        result = session_response(db, user, request, response, directory_auth=directory_proof)
        actor = Actor(user, set(), "", request.client.host if request.client else "", request.state.request_id)
        audit(db, actor, "auth.directory_login", user, after={"authorization": "saved_account" if settings().ldap_rh_access_mode == "saved" else "directory", "department": directory_proof.get("department", ""), "credential_source": directory_proof.get("credential_source", "directory")})
        return result
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    employee = None
    if body.source == "LDAP":
        employee = db.scalar(select(EmployeeAccessRequest).where(
            or_(EmployeeAccessRequest.network_username == body.email.strip().lower(),
                EmployeeAccessRequest.email == body.email.strip().lower()),
            EmployeeAccessRequest.status.in_(["PENDING", "VERIFIED"]),
        ).with_for_update())
        if employee and employee.user_id:
            user = db.get(User, employee.user_id)
    valid = False
    if body.source == "LDAP":
        from app.integrations.ldap import authenticate

        if employee:
            if employee.network_username.startswith("pending-"):
                raise DomainError("Confirme seu e-mail e conclua o cadastro antes de entrar.", 403)
            if not employee.email_confirmed_at:
                raise DomainError("Confirme o código enviado ao seu e-mail antes de entrar.", 403, "EMPLOYEE_EMAIL_NOT_VERIFIED")
            if not employee.user_id or (user and user.active and user.auth_source == "LDAP"):
                valid = authenticate(employee.network_username, body.password, expected_email=employee.email)
            if valid and not employee.user_id:
                role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
                if not role:
                    raise DomainError("Perfil de colaborador não configurado. Contate o RH.", 503)
                if db.scalar(select(User.id).where(User.email == employee.email)):
                    raise DomainError("Já existe uma conta para este e-mail. Contate o RH.", 409)
                user = User(name=employee.name, email=employee.email, kind="CANDIDATO",
                            auth_source="LDAP", active=True, email_verified=True, password_hash=None)
                db.add(user)
                db.flush()
                db.add(UserRole(user_id=user.id, role_id=role.id))
                db.add(Candidate(user_id=user.id, name=user.name, email=user.email))
                employee.user_id, employee.status = user.id, "VERIFIED"
        else:
            valid = bool(user and user.active and user.kind == "INTERNAL" and user.auth_source == "LDAP"
                         and authenticate(body.email, body.password))
    elif body.source == "LOCAL":
        valid = bool(user and user.auth_source == "LOCAL" and verify_password(body.password, user.password_hash))
    if not user or not valid or not user.active:
        # Record failures without storing supplied e-mail or password.
        if user:
            actor = Actor(
                user,
                set(),
                "",
                request.client.host if request.client else "",
                request.state.request_id,
            )
            audit(db, actor, "auth.failed", user)
            db.commit()
        raise DomainError("E-mail ou senha inválidos.", 401, "INVALID_CREDENTIALS")
    if body.area:
        area = user_area(db, user)
        is_super_admin = bool(db.scalar(select(UserRole.user_id).join(
            Role, Role.id == UserRole.role_id
        ).where(UserRole.user_id == user.id, Role.name == "SUPER_ADMIN")))
        if body.area != area and not is_super_admin:
            raise DomainError("Sua conta não tem acesso a esta área. Utilize a entrada do seu perfil.",
                              403, "WRONG_ACCESS_AREA")
    if employee:
        user.email_verified = True
    result = session_response(db, user, request, response)
    actor = Actor(
        user, set(), "", request.client.host if request.client else "", request.state.request_id
    )
    audit(db, actor, "auth.login", user)
    return result


@router.post("/refresh")
def refresh(db: Db, request: Request, response: Response):
    origin = request.headers.get("origin")
    if origin and origin not in settings().cors_origins.split(","):
        raise DomainError("Origem não autorizada.", 403)
    raw = request.cookies.get("tgpm_refresh", "")
    hashed = digest(raw)
    session = db.scalar(
        select(AuthSession)
        .where(or_(AuthSession.token_hash == hashed, AuthSession.previous_hash == hashed))
        .with_for_update()
    )
    if not session or session.revoked_at or session.expires_at <= utcnow():
        raise DomainError("Entre novamente.", 401)
    if session.previous_hash == hashed:
        session.revoked_at = utcnow()
        db.commit()
        raise DomainError("Sessão encerrada por reutilização de token.", 401)
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise DomainError("Entre novamente.", 401)
    from app.services.directory_access import require_directory_session
    require_directory_session(db, user, session)
    if (
        settings().email_verification_required
        and user.kind == "CANDIDATO"
        and not user.email_verified
    ):
        raise DomainError("Confirme seu e-mail antes de entrar.", 403, "EMAIL_NOT_VERIFIED")
    require_portal(request, db, user)
    fresh = secrets.token_urlsafe(48)
    session.previous_hash = session.token_hash
    session.token_hash = digest(fresh)
    set_cookie(response, fresh)
    return {
        "access_token": access_token(user.id, session.id),
        "user": serialize(user),
        "token_type": "bearer",
    }


@router.get("/me")
def me(actor: Current):
    return {"user": serialize(actor.user), "permissions": sorted(actor.permissions)}


@router.post("/logout")
def logout(actor: Current, db: Db, response: Response):
    session = db.get(AuthSession, actor.session_id)
    if session is None:
        raise DomainError("Sessão não encontrada.", 404)
    session.revoked_at = utcnow()
    response.delete_cookie("tgpm_refresh", path="/api/v1/auth")
    return {"message": "Sessão encerrada."}


@router.get("/sessions")
def sessions(actor: Current, db: Db):
    rows = db.scalars(
        select(AuthSession)
        .where(AuthSession.user_id == actor.user.id)
        .order_by(AuthSession.created_at.desc())
        .limit(100)
    )
    return {"items": [serialize(row) | {"current": row.id == actor.session_id} for row in rows]}


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: str, actor: Current, db: Db):
    row = db.get(AuthSession, session_id)
    if not row or (row.user_id != actor.user.id and "user.manage" not in actor.permissions):
        raise DomainError("Sessão não encontrada.", 404)
    row.revoked_at = utcnow()
    audit(db, actor, "session.revoked", row)
    return {"message": "Sessão encerrada."}


@router.post("/request-link")
def request_link(body: EmailRequest, db: Db, request: Request):
    if body.purpose not in {"RESET", "VERIFY", "MAGIC"}:
        raise DomainError("Finalidade inválida.")
    if not smtp_runtime(db).enabled:
        raise DomainError(
            "O acesso por e-mail não está disponível. Contate o RH.", 503, "EMAIL_DISABLED"
        )
    user = db.scalar(
        select(User).where(User.email == str(body.email).lower(), User.active.is_(True))
    )
    area = request_area(request)
    if user and user.auth_source == "LOCAL" and (area == user_area(db, user) if area else user.kind == "CANDIDATO"):
        purpose = "SETUP" if body.purpose == "VERIFY" and not user.password_hash else body.purpose
        issue_link(db, user, purpose, body.return_to)
    return {"message": "Se houver cadastro, você receberá as instruções de acesso."}


@router.post("/consume-link")
def consume_link(body: TokenRequest, db: Db, request: Request, response: Response):
    token = db.scalar(
        select(AuthToken).where(AuthToken.token_hash == digest(body.token)).with_for_update()
    )
    if not token or token.used_at or token.expires_at <= utcnow():
        raise DomainError("Link inválido ou expirado.", 400)
    user = db.get(User, token.user_id)
    if not user or not user.active:
        raise DomainError("Link inválido ou expirado.", 400)
    if user.auth_source == "LDAP":
        raise DomainError("Utilize seu usuário e sua senha de rede (AD).", 403)
    if token.purpose in {"RESET", "SETUP"}:
        if not body.password:
            raise DomainError("Informe a nova senha.")
        user.password_hash = hash_password(body.password)
        for session in db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
            )
        ):
            session.revoked_at = utcnow()
    user.email_verified = True
    token.used_at = utcnow()
    return session_response(db, user, request, response)


@router.post("/password")
def change_password(body: PasswordChange, actor: Current, db: Db):
    if actor.user.auth_source == "LDAP":
        raise DomainError("A senha de rede deve ser alterada pelos canais da TI.", 403)
    if not verify_password(body.current_password, actor.user.password_hash):
        raise DomainError("Senha atual incorreta.", 400)
    actor.user.password_hash = hash_password(body.new_password)
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id == actor.user.id)):
        session.revoked_at = utcnow()
    audit(db, actor, "password.changed", actor.user)
    return {"message": "Senha alterada. Entre novamente."}
