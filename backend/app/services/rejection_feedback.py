from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Outbox
from app.services.events import audit, email
from app.services.smtp_config import smtp_runtime


def feedback_template(vacancy, candidate=None):
    name = " ".join((getattr(candidate, "name", "") or "").split())
    greeting = f"Olá, {name}!" if name else "Olá!"
    return {
        "subject": ("Resultado da sua candidatura — " + vacancy.title)[:180],
        "body": greeting + "\n\nAgradecemos seu interesse na vaga de " + vacancy.title
        + " e sua participação no processo seletivo.\n\n"
        "Após a análise desta etapa, informamos que sua candidatura não avançará nesta seleção.\n\n"
        "Agradecemos o tempo dedicado e convidamos você a acompanhar as próximas oportunidades do Porto Aurora. "
        "Cada processo considera os requisitos específicos da vaga, e você poderá se candidatar novamente às oportunidades de seu interesse.\n\n"
        "Atenciosamente,\nEquipe de Recursos Humanos\nPorto Aurora",
    }


def feedback_entry(db, application):
    return db.scalar(select(Outbox).where(Outbox.dedup_key == "rejection-feedback:" + application.id))


def queue_feedback(db, actor, application, candidate, vacancy, subject="", body="", *, allow_disabled=False):
    actor.require("message.send")
    if application.status != "REJECTED":
        raise DomainError("O retorno por e-mail é exclusivo para candidaturas não selecionadas.", 409)
    existing = feedback_entry(db, application)
    if existing:
        return existing
    if candidate.anonymized_at or candidate.merged_into_id:
        raise DomainError("O perfil não está disponível para comunicação.", 409)
    if not smtp_runtime(db).enabled and not allow_disabled:
        raise DomainError("Configure e habilite o envio de e-mails antes de enviar o retorno.", 409)
    template = feedback_template(vacancy, candidate)
    email(db, candidate.email, subject.strip() or template["subject"],
          body.strip() or template["body"], "rejection-feedback:" + application.id)
    audit(db, actor, "application.rejection_feedback_queued", application, vacancy_id=vacancy.id)
    return feedback_entry(db, application)


def reject_remaining(db, actor, vacancy):
    from app.core.db import utcnow
    from app.models import Application, Candidate, StageHistory
    from app.services.events import event

    remaining = db.scalars(select(Application).where(
        Application.vacancy_id == vacancy.id,
        Application.status.in_(["ACTIVE", "RESERVE"]),
    ).order_by(Application.id).with_for_update()).all()
    if remaining:
        actor.require("message.send")
    now = utcnow()
    for application in remaining:
        application.status = "REJECTED"
        application.closed_at = now
        application.closure_reason = "Quantidade de pessoas aprovadas da vaga preenchida pelo RH."
        for history in db.scalars(select(StageHistory).where(
            StageHistory.application_id == application.id, StageHistory.left_at.is_(None),
        )):
            history.left_at = now
        candidate = db.get(Candidate, application.candidate_id)
        if candidate and not candidate.anonymized_at and not candidate.merged_into_id:
            queue_feedback(db, actor, application, candidate, vacancy, allow_disabled=True)
        event(db, actor, "application.decision", application, vacancy.id)
    return len(remaining)
