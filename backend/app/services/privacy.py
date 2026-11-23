from uuid import uuid4

from sqlalchemy import select

from app.core.db import utcnow
from app.models import (
    Application,
    CandidateFeedback,
    AuthSession,
    AuthToken,
    Document,
    Message,
    ProcessForm,
    SensitiveData,
    StageReview,
    User,
)
from app.services.events import audit


def anonymize(db, actor, candidate, reason):
    user = db.get(User, candidate.user_id)
    anonymous_email = uuid4().hex + "@anon.invalid"
    user.name, user.email, user.password_hash, user.active = (
        "Titular anonimizado",
        anonymous_email,
        None,
        False,
    )
    candidate.name = "Titular anonimizado"
    candidate.email = anonymous_email
    candidate.phone = candidate.city = candidate.state = candidate.social_name = ""
    candidate.profile = {}
    candidate.anonymized_at = utcnow()
    candidate.talent_consent_until = None
    for session in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)):
        session.revoked_at = utcnow()
        session.ip = session.user_agent = ""
    for token in db.scalars(select(AuthToken).where(AuthToken.user_id == user.id)):
        token.used_at = utcnow()
    for application in db.scalars(
        select(Application).where(Application.candidate_id == candidate.id)
    ):
        application.profile_snapshot = {}
        application.answers = {}
        for form in db.scalars(select(ProcessForm).where(ProcessForm.application_id == application.id)):
            form.encrypted_data = ""
            form.expires_at = utcnow()
        for review in db.scalars(select(StageReview).where(StageReview.application_id == application.id)):
            review.reason = "[Conteúdo anonimizado]"
        if application.status not in {"HIRED", "REJECTED", "WITHDRAWN"}:
            application.status = "WITHDRAWN"
            application.closed_at = utcnow()
        for message in db.scalars(select(Message).where(Message.application_id == application.id)):
            message.body = "[Conteúdo anonimizado]"
    for feedback in db.scalars(select(CandidateFeedback).where(CandidateFeedback.candidate_id == candidate.id)):
        feedback.message = "[Conteúdo anonimizado]"
        feedback.rating = None
    for sensitive in db.scalars(
        select(SensitiveData).where(SensitiveData.candidate_id == candidate.id)
    ):
        db.delete(sensitive)
    # Physical files are queued for deletion only after database commit.
    from app.models import Outbox

    for document in db.scalars(select(Document).where(
        Document.candidate_id == candidate.id, Document.scan_status != "DELETED"
    )):
        db.add(
            Outbox(
                kind="DELETE_FILE",
                dedup_key="delete:" + document.id,
                payload={"storage_key": document.storage_key},
            )
        )
        document.filename = "anonimizado"
        document.status = "ANONYMIZED"
        document.scan_status = "DELETED"
    audit(db, actor, "candidate.anonymized", candidate, after={"reason": reason})
