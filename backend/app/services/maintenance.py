from datetime import timedelta

from sqlalchemy import select

from app.core.db import utcnow
from app.core.permissions import PERMISSIONS, Actor
from app.domain.assessment import grade
from app.models import (
    Application,
    Candidate,
    ConfigRecord,
    DataSubjectRequest,
    Offer,
    Outbox,
    TestAssignment,
    TestAttempt,
    User,
    Vacancy,
)
from app.models.intake import ImportBatch, QuickApplication
from app.services.events import event
from app.services.privacy import anonymize
from app.services.recruitment import calculate_application


def expire_records(db):
    now = utcnow()
    count = 0
    for attempt in db.scalars(
        select(TestAttempt).where(TestAttempt.status == "STARTED").with_for_update(skip_locked=True)
    ):
        assignment = db.get(TestAssignment, attempt.assignment_id)
        limit = min(
            assignment.due_at,
            attempt.started_at + timedelta(minutes=assignment.snapshot["duration_minutes"]),
        )
        if now <= limit:
            continue
        application = db.get(Application, assignment.application_id)
        candidate = db.get(Candidate, application.candidate_id)
        user = db.get(User, candidate.user_id)
        actor = Actor(user, set(), "", "", "expiry:" + attempt.id)
        result = grade(assignment.snapshot["questions"], attempt.answers)
        attempt.grading = result["items"]
        attempt.score = result["score"]
        attempt.status = result["status"]
        attempt.submitted_at = limit
        event(db, actor, "test.expired", attempt, application.vacancy_id)
        if attempt.status == "GRADED":
            calculate_application(db, actor, application)
        count += 1
    for offer in db.scalars(
        select(Offer)
        .where(
            Offer.status.in_(["DRAFT", "PENDING_APPROVAL", "APPROVED", "SENT"]),
            Offer.expires_at < now,
        )
        .with_for_update(skip_locked=True)
    ):
        offer.status = "EXPIRED"
        application = db.get(Application, offer.application_id)
        user = db.get(User, offer.created_by)
        event(
            db,
            Actor(user, set(), "", "", "expiry:" + offer.id),
            "offer.expired",
            offer,
            application.vacancy_id,
        )
        count += 1
    for quick in db.scalars(
        select(QuickApplication).where(QuickApplication.expires_at < now - timedelta(days=1))
    ):
        db.delete(quick)
    for batch in db.scalars(
        select(ImportBatch).where(ImportBatch.updated_at < now - timedelta(days=7))
    ):
        batch.rows = {"valid": [], "errors": []}
        batch.status = "PURGED"
    for email in db.scalars(
        select(Outbox).where(
            Outbox.kind == "EMAIL",
            Outbox.status.in_(["SENT", "DEAD", "DISABLED"]),
            Outbox.updated_at < now - timedelta(days=30),
        )
    ):
        email.payload = {}
        email.status = "PURGED"
    return count


def apply_retention(db):
    now = utcnow()
    count = 0
    policies = db.scalars(
        select(ConfigRecord).where(
            ConfigRecord.kind == "retention-policies", ConfigRecord.active.is_(True)
        )
    )
    for policy in policies:
        threshold = now - timedelta(days=policy.data["months"] * 365.2425 / 12)
        user = db.get(User, policy.created_by)
        if not user or not user.active:
            continue
        actor = Actor(user, set(PERMISSIONS), "", "", "retention:" + policy.id)
        for candidate in db.scalars(
            select(Candidate).where(
                Candidate.anonymized_at.is_(None), Candidate.merged_into_id.is_(None)
            )
        ):
            applications = list(
                db.scalars(select(Application).where(Application.candidate_id == candidate.id))
            )
            if any(
                a.status in {"ACTIVE", "SELECTED", "PRE_ADMISSION", "RESERVE"} for a in applications
            ):
                continue
            if candidate.talent_consent_until and candidate.talent_consent_until > now:
                continue
            target = policy.data["target"]
            relevant = [a for a in applications if (a.status == "HIRED") == (target == "ADMISSION")]
            if target == "TALENT":
                expired = (candidate.talent_consent_until or candidate.updated_at) < threshold
            else:
                expired = bool(relevant) and all(
                    a.closed_at and a.closed_at < threshold for a in relevant
                )
            # Never let a shorter policy erase data covered by another live process.
            if not expired or any(a.closed_at and a.closed_at >= threshold for a in applications):
                continue
            if policy.data["action"] == "ANONYMIZE":
                anonymize(
                    db,
                    actor,
                    candidate,
                    "Política de retenção " + policy.id + " versão " + str(policy.version),
                )
                count += 1
            elif not db.scalar(
                select(DataSubjectRequest.id).where(
                    DataSubjectRequest.candidate_id == candidate.id,
                    DataSubjectRequest.status.in_(["OPEN", "IN_REVIEW"]),
                )
            ):
                db.add(
                    DataSubjectRequest(
                        candidate_id=candidate.id,
                        kind="RETENTION_REVIEW",
                        detail="Revisão de retenção: " + policy.name,
                    )
                )
                count += 1
    return count


def emit_sla_events(db):
    now = utcnow()
    count = 0
    for vacancy in db.scalars(
        select(Vacancy)
        .where(Vacancy.status.in_(["PUBLISHED", "PAUSED"]), Vacancy.published_at.is_not(None))
        .with_for_update(skip_locked=True)
    ):
        sla_hours = vacancy.details.get("sla_hours", 720)
        if (now - vacancy.published_at).total_seconds() < sla_hours * 3600 * 0.75:
            continue
        key = "sla:" + vacancy.id + ":" + vacancy.published_at.isoformat()
        if db.scalar(select(Outbox.id).where(Outbox.dedup_key == key)):
            continue
        db.add(
            Outbox(
                kind="EVENT",
                dedup_key=key,
                payload={
                    "event": "vacancy.sla_near",
                    "entity": "vacancies",
                    "id": vacancy.id,
                    "vacancy_id": vacancy.id,
                    "event_id": key,
                    "automation_depth": 0,
                },
            )
        )
        count += 1
    return count
