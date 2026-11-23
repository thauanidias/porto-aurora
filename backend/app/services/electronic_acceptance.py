"""Evidence of affirmative acceptance, independent of recruitment-stage release."""
import hashlib
import hmac
import json

from sqlalchemy import select
from app.core.config import settings
from app.models import Candidate, Consent, ConsentReceipt


def acceptance_signature(record: dict) -> str:
    serialized = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hmac.new(settings().encryption_key.get_secret_value().encode(), serialized, hashlib.sha256).hexdigest()


def has_registration_acceptance(db, user) -> bool:
    linked = select(Consent.notice_snapshot["receipt_id"].astext).join(Candidate, Consent.candidate_id == Candidate.id).where(
        Candidate.user_id == user.id, Consent.granted.is_(True))
    return db.scalar(select(ConsentReceipt.id).where(
        ConsentReceipt.context == "CADASTRO", ConsentReceipt.document_code == "FORM-PPO-RH-002.09",
        (ConsentReceipt.user_id == user.id) | ConsentReceipt.id.in_(linked)).limit(1)) is not None
