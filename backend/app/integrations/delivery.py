import hashlib
import hmac
import json
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote, urlparse

import httpx

from app.core.config import settings
from app.core.errors import DomainError
from app.core.security import encrypt
from app.services.email_template import add_branded_html
from app.services.smtp_config import smtp_record, smtp_runtime


def smtp_access_token(cfg, db):
    refresh_token = getattr(cfg, "refresh_token", None) or ""
    if not refresh_token and not all((cfg.tenant_id, cfg.client_id, cfg.client_secret)) and getattr(cfg, "access_token", None):
        return cfg.access_token
    data = {"client_id": cfg.client_id, "client_secret": cfg.client_secret,
            "scope": "https://outlook.office365.com/.default", "grant_type": "client_credentials"}
    if refresh_token:
        data.update({"grant_type": "refresh_token", "refresh_token": refresh_token,
                     "scope": "https://outlook.office.com/SMTP.Send offline_access"})
        if not cfg.client_secret:
            data.pop("client_secret")
    try:
        response = httpx.post(f"https://login.microsoftonline.com/{cfg.tenant_id}/oauth2/v2.0/token", data=data, timeout=20)
        response.raise_for_status()
        tokens = response.json()
        token = tokens["access_token"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise DomainError("Não foi possível obter o token OAuth2. Confira os dados da aplicação e a autorização no Microsoft 365.", 502, "SMTP_OAUTH_FAILED") from exc
    if tokens.get("refresh_token") and db is not None:
        row = smtp_record(db)
        if row:
            row.data = {**row.data, "encrypted_refresh_token": encrypt(tokens["refresh_token"])}
    return token


def send_email(payload: dict, key: str, db=None):
    cfg = smtp_runtime(db)
    if not cfg.enabled:
        raise DomainError("SMTP_DISABLED", 503)
    mode = "test" if getattr(cfg, "test_mode", False) else "real"
    if payload.get("delivery_mode", mode) != mode:
        raise DomainError("EMAIL_MODE_CHANGED_DISABLED", 503)
    message = EmailMessage()
    message["From"] = cfg.sender
    message["To"] = payload["recipient"]
    message["Subject"] = payload["subject"]
    message["Message-ID"] = "<" + hashlib.sha256(key.encode()).hexdigest() + "@tgpm-talentos>"
    message.set_content(payload["body"])
    add_branded_html(message, payload["subject"], payload["body"], template=payload.get("template", "default"))
    context = ssl.create_default_context()
    if not getattr(cfg, "validate_tls", True):
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    implicit = cfg.port == 465
    connection = smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=20, context=context) if implicit else smtplib.SMTP(cfg.host, cfg.port, timeout=20)
    with connection as server:
        if cfg.starttls and not implicit:
            server.starttls(context=context)
            server.ehlo()
        elif not implicit and settings().environment == "production":
            raise DomainError("SMTP_TLS_REQUIRED", 503)
        if cfg.auth_mode == "oauth2":
            access_token = smtp_access_token(cfg, db)
            def oauth_response(challenge: bytes | None = None) -> str:
                return f"user={getattr(cfg, 'username', '') or cfg.sender}\x01auth=Bearer {access_token}\x01\x01"

            server.auth("XOAUTH2", oauth_response)
        elif cfg.username:
            server.login(cfg.username, cfg.password)
        server.send_message(message)


def validate_webhook_url(url: str):
    parsed = urlparse(url)
    allowed = {
        host.strip().lower() for host in settings().webhook_allowed_hosts.split(",") if host.strip()
    }
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed
        or parsed.username
        or parsed.password
    ):
        raise DomainError("O webhook exige HTTPS e host autorizado em WEBHOOK_ALLOWED_HOSTS.")


def send_webhook(url: str, secret: str, payload: dict, event_id: str):
    validate_webhook_url(url)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.post(
            url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Porto-Aurora-Event-ID": event_id,
                "X-Porto-Aurora-Signature": "sha256=" + signature,
            },
        )
        response.raise_for_status()


def graph_event(payload: dict):
    cfg = settings()
    if not cfg.graph_enabled:
        raise DomainError("GRAPH_DISABLED", 503)
    tenant = quote(cfg.graph_tenant_id, safe="")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "client_id": cfg.graph_client_id,
                "client_secret": cfg.graph_client_secret.get_secret_value(),
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        user = quote(cfg.graph_user_id, safe="")
        result = client.post(
            f"https://graph.microsoft.com/v1.0/users/{user}/calendar/events",
            json=payload,
            headers={"Authorization": "Bearer " + token},
        )
        result.raise_for_status()
        return result.json()["id"]
