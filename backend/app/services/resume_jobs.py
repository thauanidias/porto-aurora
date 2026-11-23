"""Owner-scoped encrypted import jobs; extraction never writes candidate profiles."""
import hashlib
import json
from pathlib import Path
from time import perf_counter

from redis import Redis
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import DomainError
from app.core.security import decrypt, encrypt
from app.models import Candidate, Document
from app.services.resume_ai import (
    Extraction,
    extract_local,
    fast_labeled_suggestions,
    labeled_education,
    labeled_professional,
    validated_suggestions,
)
from app.services.resume_cache import EXTRACTOR_VERSION, read_result, store_result
from app.services.resume_profile import read_resume


def key(owner, document):
    digest = hashlib.sha256(f"{EXTRACTOR_VERSION}:{owner}:{document}:{settings().resume_ai_model}:{settings().resume_ai_enabled}".encode()).hexdigest()
    return "resume-import:" + digest


def read_job(owner, document):
    client = Redis.from_url(settings().redis_url)
    try:
        value = client.get(key(owner, document))
        return json.loads(decrypt(value.decode())) if value else None
    finally:
        client.close()


def write_job(owner, document, data, only_new=False):
    client = Redis.from_url(settings().redis_url)
    try:
        return client.set(key(owner, document), encrypt(json.dumps(data, ensure_ascii=False)), ex=7200, nx=only_new)
    finally:
        client.close()


def owned_document(db, owner, document_id):
    row = db.scalar(select(Document).join(Candidate, Document.candidate_id == Candidate.id).where(
        Document.id == document_id, Candidate.user_id == owner,
        Candidate.anonymized_at.is_(None), Candidate.merged_into_id.is_(None)))
    if not row or row.type_name != "CURRICULO":
        raise DomainError("Currículo não encontrado.", 404)
    if row.scan_status not in {"CLEAN", "NOT_CONFIGURED"} or (settings().environment == "production" and row.scan_status != "CLEAN"):
        raise DomainError("Aguarde a verificação do arquivo antes de importar os dados.", 409)
    return row


def run_import(owner, document_id):
    started = perf_counter()
    def progress(message, **extra):
        write_job(owner, document_id, {"status": "RUNNING", "message": message, **extra})
    with SessionLocal() as db:
        row = owned_document(db, owner, document_id)
        sha = row.sha256
        cached = read_result(owner, sha)
        if cached:
            write_job(owner, document_id, {"status": "COMPLETED", "result": cached, "cached": True})
            return
        root = Path(settings().upload_dir).resolve()
        source = (root / row.storage_key).resolve()
        if not source.is_relative_to(root):
            raise DomainError("Arquivo indisponível.", 409)
        content = source.read_bytes()
        if hashlib.sha256(content).hexdigest() != sha:
            raise DomainError("A integridade do arquivo não pôde ser confirmada. Envie o currículo novamente.", 409)
        mime = row.mime
    progress("Lendo as páginas e reconhecendo texto quando necessário…")
    document = read_resume(content, mime, lambda index, total: progress(
        f"Lendo página {index + 1} de {total}…", pages_read=index, pages=total))
    text = document["text"]
    read_seconds = perf_counter() - started
    if not text.strip():
        raise DomainError("Não foi possível reconhecer texto no currículo, mesmo com OCR. Envie um PDF mais legível.", 422)
    result = fast_labeled_suggestions(text) if settings().resume_ai_enabled else None
    engine = "local-fast" if result else "local-ai" if settings().resume_ai_enabled else "local-rules"
    if settings().resume_ai_enabled and result is None:
        result = extract_local(text, lambda index, total: progress(
            f"Interpretando parte {index + 1} de {total}…", pages=document["pages"], parts=total, part=index + 1))
    elif result is None:
        result = validated_suggestions(Extraction(facts=labeled_education(text) + labeled_professional(text)), text)
    result.update(text=text, engine=engine,
                  pages=document["pages"], ocr_pages=document["ocr_pages"],
                  timings={"read_seconds": round(read_seconds, 3), "total_seconds": round(perf_counter() - started, 3)},
                  message="Leitura concluída. Revise os campos e confirme para salvar seu perfil.")
    # Re-check ownership before publishing a result after a potentially long analysis.
    with SessionLocal() as db:
        owned_document(db, owner, document_id)
    store_result(owner, sha, result)
    write_job(owner, document_id, {"status": "COMPLETED", "result": result, "cached": False})
