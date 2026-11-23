"""Per-user conversation read cursors; never count private notes or one's own messages."""
from datetime import datetime, timezone
from sqlalchemy import func, or_, select
from app.core.permissions import is_manager, vacancy_scope
from app.models import Application, Candidate, Message, User, Vacancy
from app.services.candidate_journey import application_permissions


def unread_messages(db, actor):
    query = select(Application)
    if actor.user.kind == "CANDIDATO":
        query = query.join(Candidate, Application.candidate_id == Candidate.id).where(Candidate.user_id == actor.user.id)
    elif "candidate.view" in actor.permissions and not is_manager(actor):
        query = query.join(Vacancy, Application.vacancy_id == Vacancy.id).where(vacancy_scope(actor))
    else:
        return 0
    records = db.scalars(query).all()
    cursors = actor.user.preferences.get("conversation_reads", {})
    conditions = []
    for application in records:
        if actor.user.kind == "CANDIDATO" and not application_permissions(db, application)["permissions"]["messages"]:
            continue
        try:
            cutoff = datetime.fromisoformat(cursors[application.id])
            if cutoff.tzinfo is None: raise ValueError()
        except (KeyError, ValueError, TypeError):
            cutoff = datetime(1970, 1, 1, tzinfo=timezone.utc)
        conditions.append((Message.application_id == application.id) & (Message.created_at > cutoff))
    if not conditions:
        return 0
    return db.scalar(select(func.count()).select_from(Message).where(
        Message.visibility == "CANDIDATE", Message.sender_id != actor.user.id, or_(*conditions)))


def mark_conversation_read(db, actor, application, message):
    db.scalar(select(User).where(User.id == actor.user.id).with_for_update().execution_options(populate_existing=True))
    cursors = dict(actor.user.preferences.get("conversation_reads", {}))
    previous = cursors.get(application.id)
    try:
        if previous and datetime.fromisoformat(previous) >= message.created_at:
            return
    except (TypeError, ValueError):
        pass
    cursors[application.id] = message.created_at.isoformat()
    actor.user.preferences = {**actor.user.preferences, "conversation_reads": cursors}
