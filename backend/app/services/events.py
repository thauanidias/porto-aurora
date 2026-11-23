from contextvars import ContextVar
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.permissions import Actor
from app.models import AuditLog, Notification, Outbox, User

event_depth: ContextVar[int] = ContextVar("event_depth", default=0)


def audit(
    db: Session,
    actor: Actor,
    action: str,
    entity,
    before: dict | None = None,
    after: dict | None = None,
    vacancy_id: str | None = None,
):
    db.flush()
    # Keep personal content out of audit snapshots; versions and changed fields are traceable.
    db.add(
        AuditLog(
            user_id=actor.user.id,
            action=action,
            entity=entity.__tablename__,
            entity_id=entity.id,
            vacancy_id=vacancy_id,
            before=before or {},
            after=after or {"version": getattr(entity, "version", 1)},
            ip=actor.ip,
            request_id=actor.request_id,
        )
    )


def event(db: Session, actor: Actor, name: str, entity, vacancy_id: str | None = None):
    db.flush()
    event_id = str(uuid4())
    audit(db, actor, name, entity, vacancy_id=vacancy_id)
    db.add(
        Outbox(
            kind="EVENT",
            dedup_key=event_id,
            payload={
                "event": name,
                "entity": entity.__tablename__,
                "id": entity.id,
                "vacancy_id": vacancy_id,
                "actor_id": actor.user.id,
                "event_id": event_id,
                "automation_depth": event_depth.get(),
            },
        )
    )


def notify(db: Session, user_id: str, title: str, body: str, category: str, link: str = ""):
    db.add(Notification(user_id=user_id, title=title, body=body, category=category, link=link))
    from app.services.smtp_config import smtp_runtime

    cfg = smtp_runtime(db)
    user = db.get(User, user_id)
    if cfg.enabled and getattr(cfg, "notifications_enabled", True) and user and user.active and (user.preferences or {}).get("email_notifications", True):
        text = body
        if link and link.startswith("/") and not link.startswith("//"):
            text += "\n\nAcesse: " + cfg.public_url.rstrip("/") + link
        email(db, user.email, title + " — Porto Aurora Talentos", text, "notification:" + str(uuid4()))


def email(db: Session, recipient: str, subject: str, body: str, key: str, *, template: str | None = None):
    from app.services.smtp_config import smtp_runtime

    cfg = smtp_runtime(db)
    db.add(
        Outbox(
            kind="EMAIL",
            dedup_key=key,
            payload={"recipient": recipient, "subject": subject, "body": body, "delivery_mode": "test" if getattr(cfg, "test_mode", False) else "real", **({"template": template} if template else {})},
        )
    )
