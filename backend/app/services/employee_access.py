import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta

from app.core.config import settings
from app.core.db import utcnow
from app.core.errors import DomainError
from app.services.events import email
from app.services.smtp_config import smtp_runtime


def corporate_email(address: str) -> str:
    address = address.strip().lower()
    if address.rsplit("@", 1)[-1] != "portoaurora.example":
        raise DomainError("Use seu e-mail corporativo @portoaurora.example.")
    return address


def network_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,179}", value):
        raise DomainError("Informe somente seu usuário de rede, sem domínio ou e-mail. Exemplo: nome.sobrenome.")
    return value


def code_digest(request_id: str, code: str) -> str:
    return hmac.new(settings().jwt_secret.get_secret_value().encode(),
                    ("employee-registration:" + request_id + ":" + code).encode(), hashlib.sha256).hexdigest()


def send_registration_code(db, row):
    if not smtp_runtime(db).enabled:
        raise DomainError("O envio de e-mail não está configurado. Contate o RH para concluir o cadastro.", 503, "EMAIL_DISABLED")
    if row.email_confirmed_at:
        raise DomainError("E-mail já confirmado. Entre com seu usuário de rede.", 409)
    now = utcnow()
    if row.email_code_sent_at and now < row.email_code_sent_at + timedelta(seconds=60):
        raise DomainError("Aguarde 60 segundos entre os envios do código.", 429)
    code = f"{secrets.randbelow(1_000_000):06d}"
    row.email_code_hash = code_digest(row.id, code)
    row.email_code_expires_at = now + timedelta(minutes=10)
    row.email_code_sent_at = now
    row.email_code_attempts = 0
    email(db, row.email, "Seu código de cadastro — Porto Aurora Talentos",
          f"Seu código de confirmação é: {code}\n\nEle é válido por 10 minutos e só pode ser usado uma vez. "
          "Informe o código na tela de cadastro de colaborador.\n\n"
          "Se você não solicitou este cadastro, ignore esta mensagem. Não compartilhe o código.",
          "employee-registration:" + row.id + ":" + secrets.token_urlsafe(16))
    return {"registration_id": row.id, "verification_required": True, "expires_in": 600, "resend_after": 60,
            "message": "Código enviado para seu e-mail. Confira sua caixa de entrada e o spam."}


def confirm_registration_code(db, row, code: str):
    if row.email_confirmed_at or not row.email_code_hash:
        raise DomainError("Código inválido ou já utilizado.", 400)
    if not row.email_code_expires_at or row.email_code_expires_at <= utcnow():
        raise DomainError("Código expirado. Solicite um novo código.", 400)
    if row.email_code_attempts >= 5:
        raise DomainError("Limite de tentativas atingido. Solicite um novo código.", 429)
    if not secrets.compare_digest(row.email_code_hash, code_digest(row.id, code)):
        row.email_code_attempts += 1
        # Preserve the attempt count even though the request returns an error.
        db.commit()
        raise DomainError("Código incorreto. Confira o e-mail e tente novamente.", 400)
    row.email_confirmed_at = utcnow()
    row.email_code_hash = None
    row.email_code_expires_at = None
    from app.core.security import encrypt

    token = encrypt(json.dumps({"registration_id": row.id, "purpose": "employee-completion",
                                "expires_at": (utcnow() + timedelta(minutes=30)).timestamp()}))
    return {"message": "E-mail confirmado. Continue seu cadastro.", "completion_token": token}
