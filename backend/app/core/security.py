import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    if len(password) != 6 and not 12 <= len(password) <= 128:
        raise DomainError("A senha deve conter de 12 a 128 caracteres")
    return hasher.hash(password)


def hash_verified_network_password(password: str) -> str:
    """Hash an AD-verified secret without imposing the portal's password policy."""
    if not 1 <= len(password) <= 128:
        raise DomainError("Senha de rede inválida.", 422)
    return hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        return hasher.verify(hashed or DUMMY_HASH, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def access_token(user_id: str, session_id: str) -> str:
    now = utcnow()
    return jwt.encode(
        {
            "sub": user_id,
            "sid": session_id,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=settings().access_minutes),
            "iss": "tgpm-talentos",
            "aud": "tgpm-talentos",
        },
        settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience="tgpm-talentos",
            issuer="tgpm-talentos",
            options={"require": ["exp", "iat", "sub", "sid", "type"]},
        )
        if payload["type"] != "access":
            raise jwt.InvalidTokenError()
        return payload
    except jwt.InvalidTokenError as exc:
        raise DomainError("Sua sessão expirou. Entre novamente.", 401, "UNAUTHENTICATED") from exc


def encrypt(value: str) -> str:
    return (
        Fernet(settings().encryption_key.get_secret_value().encode())
        .encrypt(value.encode())
        .decode()
    )


def decrypt(value: str) -> str:
    return (
        Fernet(settings().encryption_key.get_secret_value().encode())
        .decrypt(value.encode())
        .decode()
    )
