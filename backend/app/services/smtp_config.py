from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decrypt
from app.models import ConfigRecord

SMTP_CONFIG_KIND = "smtp-settings"


@dataclass(frozen=True)
class SmtpRuntimeConfig:
    enabled: bool
    host: str
    port: int
    sender: str
    starttls: bool
    auth_mode: str
    username: str
    password: str
    tenant_id: str
    client_id: str
    client_secret: str
    public_url: str
    validate_tls: bool = True
    refresh_token: str = ""
    access_token: str = ""
    test_mode: bool = False
    notifications_enabled: bool = True


def smtp_record(db: Session) -> ConfigRecord | None:
    return db.scalar(select(ConfigRecord).where(ConfigRecord.kind == SMTP_CONFIG_KIND))


def smtp_runtime(db: Session | None = None) -> SmtpRuntimeConfig:
    cfg = settings()
    row = smtp_record(db) if db is not None else None
    if cfg.test_email_enabled and not (row and row.data.get("replace_local_mode")):
        return SmtpRuntimeConfig(
            enabled=True, host="mailpit", port=1025,
            sender="talentos@portoaurora.example", starttls=False, auth_mode="basic",
            username="", password="", tenant_id="", client_id="", client_secret="",
            public_url=cfg.public_url,
            test_mode=True,
        )
    if row:
        data = row.data
        return SmtpRuntimeConfig(
            enabled=bool(data.get("enabled")),
            host=str(data.get("host", "smtp.office365.com")),
            port=int(data.get("port", 587)),
            sender=str(data.get("sender", "")),
            starttls=bool(data.get("starttls", True)),
            auth_mode=str(data.get("auth_mode", "oauth2")),
            username=str(data.get("username", "")),
            password=decrypt(data["encrypted_password"]) if data.get("encrypted_password") else "",
            tenant_id=str(data.get("tenant_id", "")),
            client_id=str(data.get("client_id", "")),
            client_secret=decrypt(data["encrypted_secret"])
            if data.get("encrypted_secret")
            else "",
            public_url=str(data.get("public_url", "")),
            validate_tls=bool(data.get("validate_tls", True)),
            refresh_token=decrypt(data["encrypted_refresh_token"]) if data.get("encrypted_refresh_token") else "",
            access_token=decrypt(data["encrypted_access_token"]) if data.get("encrypted_access_token") else "",
            notifications_enabled=bool(data.get("notifications_enabled", True)),
        )
    return SmtpRuntimeConfig(
        enabled=cfg.smtp_enabled,
        host=cfg.smtp_host,
        port=cfg.smtp_port,
        sender=cfg.smtp_from,
        starttls=cfg.smtp_starttls,
        auth_mode=cfg.smtp_auth_mode,
        username=cfg.smtp_user,
        password=cfg.smtp_password.get_secret_value(),
        tenant_id=cfg.smtp_oauth_tenant_id,
        client_id=cfg.smtp_oauth_client_id,
        client_secret=cfg.smtp_oauth_client_secret.get_secret_value(),
        public_url=cfg.public_url,
    )
