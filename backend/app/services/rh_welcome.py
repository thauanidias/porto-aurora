"""Queue the RH welcome only once per user, including previously queued welcomes."""
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.config import settings
from app.models import Outbox, User
from app.core.db import utcnow
from app.services.events import email
from app.services.smtp_config import smtp_runtime


def welcome_message(name: str, portal_url: str) -> dict:
    first_name = name.strip().split()[0] if name.strip() else "equipe RH"
    subject = f"Que bom ter você aqui, {first_name}! — Porto Aurora Talentos"
    body = (
        f"Olá, {first_name}!\n\n"
        "Que alegria receber você no Porto Aurora Talentos! Estamos felizes por ter você com a gente.\n\n"
        "Cada processo seletivo conecta pessoas e oportunidades. "
        "Seu olhar faz a diferença em cada currículo, conversa e nova contratação.\n\n"
        "Desejo um dia leve, cheio de boas conexões, descobertas e conquistas. "
        "Vamos construir novas oportunidades juntos?\n\n"
        "Seu espaço está pronto para acompanhar vagas, conhecer candidatos e organizar os próximos passos.\n\n"
    )
    if portal_url:
        body += "Acesse seu painel: " + portal_url.rstrip("/") + "/app/vagas\n\n"
    body += "Com carinho,\nEquipe Porto Aurora Talentos\nPorto Aurora"
    return {"subject": subject, "body": body}


def queue_welcome(db, user, session_id: str) -> bool:
    # Serialize simultaneous logins and persist the decision independently of outbox retention.
    db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    marker = "rh_welcome_queued_at"
    if user.preferences.get(marker):
        return False
    key = "rh-welcome:user:" + user.id
    previous = db.scalar(select(Outbox.id).where(
        (Outbox.dedup_key == key) |
        (Outbox.dedup_key.like("rh-welcome:%") &
         (Outbox.payload["recipient"].astext == user.email))
    ).limit(1))
    if previous:
        user.preferences = {**user.preferences, marker: utcnow().isoformat()}
        return False
    cfg = smtp_runtime(db)
    if not cfg.enabled:
        return False
    # Never email a localhost link to colleagues using another computer.
    origin = settings().rh_url or cfg.public_url
    parsed = urlsplit(origin)
    public_origin = origin if parsed.scheme in {"http", "https"} and parsed.hostname not in {None, "localhost", "127.0.0.1", "::1"} else ""
    content = welcome_message(user.name, public_origin)
    email(db, user.email, content["subject"], content["body"], key, template="rh-welcome")
    user.preferences = {**user.preferences, marker: utcnow().isoformat()}
    db.flush()
    return True
