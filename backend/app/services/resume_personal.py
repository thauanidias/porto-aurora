import json

from sqlalchemy import select

from app.core.errors import DomainError
from app.core.security import decrypt, encrypt
from app.models import Candidate, SensitiveData
from app.schemas.resume_import import ResumePersonal
from app.services.candidate_journey import require_candidate_section
from app.services.events import audit


def own_personal(db, actor, lock=False):
    require_candidate_section(db, actor, "basic_profile")
    query = select(Candidate).where(Candidate.user_id == actor.user.id)
    candidate = db.scalar(query.with_for_update() if lock else query)
    if not candidate or candidate.anonymized_at or candidate.merged_into_id:
        raise DomainError("Salve seus dados básicos antes de confirmar a importação.", 409)
    row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate.id))
    stored = json.loads(decrypt(row.encrypted_data)) if row and row.encrypted_data else {}
    record = stored.get("resume_personal", {})
    return candidate, row, stored, record


def personal_response(record):
    return {"data": record.get("data", ResumePersonal().model_dump(mode="json")),
            "version": record.get("version", 0)}


def save_personal(db, actor, data, version):
    candidate, row, stored, previous = own_personal(db, actor, lock=True)
    if previous.get("version", 0) != version:
        raise DomainError("Seus dados pessoais foram atualizados em outra sessão. Reabra a revisão.", 409)
    record = {"data": data.model_dump(mode="json"), "version": version + 1}
    stored["resume_personal"] = record
    if not row:
        row = SensitiveData(candidate_id=candidate.id, purpose="Dados pessoais confirmados pelo titular no perfil")
        db.add(row)
    row.encrypted_data = encrypt(json.dumps(stored, ensure_ascii=False))
    audit(db, actor, "candidate.resume_personal_saved", candidate, after={"version": record["version"]})
    return personal_response(record)
