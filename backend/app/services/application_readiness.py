"""Mandatory profile and resume checks shared by enrollment and its preview."""
import re

from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Document


def profile_missing(candidate):
    if not candidate:
        return ["Dados básicos", "Formação", "Competências", "Turno disponível"]
    missing = []
    for field, label in (("name", "Nome"), ("phone", "Telefone"), ("city", "Cidade"), ("state", "Estado"), ("country", "País")):
        value = str(getattr(candidate, field, "") or "").strip()
        if not value or (field == "phone" and len(re.sub(r"\D", "", value)) < 10) or (field in {"state", "country"} and len(value) != 2):
            missing.append(label)
    profile = candidate.profile or {}
    if not any(isinstance(item, dict) and (str(item.get("course") or "").strip() or item.get("degree"))
               for item in profile.get("education", [])):
        missing.append("Formação")
    if not any(str(skill).strip() for skill in profile.get("skills", [])):
        missing.append("Competências")
    if not str(profile.get("shift", "")).strip():
        missing.append("Turno disponível")
    return missing


def application_readiness(db, candidate):
    missing = profile_missing(candidate)
    cv_id = db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
        Document.type_name == "CURRICULO", Document.status != "REJECTED",
        Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"])
    ).order_by(Document.created_at.desc(), Document.revision.desc()).limit(1)) if candidate else None
    if not cv_id:
        missing.append("Currículo anexado e validado")
    return {"ready": not missing, "missing": missing, "cv_id": cv_id}


def require_application_ready(db, candidate):
    result = application_readiness(db, candidate)
    if not result["ready"]:
        raise DomainError("Antes de se candidatar, complete e salve Meu perfil: " + ", ".join(result["missing"]) + ".", 422, "PROFILE_INCOMPLETE")
    return result
