"""Enroll consenting talent profiles using explicit professional criteria only."""
from copy import deepcopy

from sqlalchemy import select

from app.core.db import utcnow
from app.domain.scoring import calculate
from app.models import (
    Application,
    Candidate,
    Document,
    PipelineStage,
    RolePermission,
    ScoringVersion,
    StageHistory,
    User,
    UserRole,
)
from app.services.events import event


def internal_users():
    return select(UserRole.user_id).join(
        RolePermission, RolePermission.role_id == UserRole.role_id
    ).where(RolePermission.permission == "internal.view")


def unsuccessful_candidates():
    return select(Application.candidate_id).where(Application.status == "REJECTED")


def compatible_profile(criteria, facts):
    # Manual-only models and future test/interview results cannot establish a match.
    professional = [item for item in criteria if not item.get("not_applicable")
                    and item.get("field") not in {"test_score", "evaluation_score"}]
    if not professional:
        return False
    result = calculate(criteria, facts)
    return all(item["met"] for item in result["items"]
               if item["applicable"] and item["field"] not in {"test_score", "evaluation_score"})


def enroll_talents(db, actor, vacancy):
    from app.services.recruitment import calculate_application

    if (vacancy.status != "PUBLISHED" or vacancy.confidential
            or not vacancy.deadline or vacancy.deadline <= utcnow()):
        return 0
    # Serialize publication/republication so enrollment is idempotent.
    db.flush()
    from app.models import Vacancy
    db.scalar(select(Vacancy).where(Vacancy.id == vacancy.id).with_for_update())
    model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == vacancy.id)
                      .order_by(ScoringVersion.number.desc()).limit(1))
    from app.services.process_workflow import initial_application_stage
    stage = initial_application_stage(db, vacancy.id)
    if not model or not stage:
        return 0
    employees = set(db.scalars(internal_users()))
    candidates = db.scalars(select(Candidate).join(User, Candidate.user_id == User.id).where(
        Candidate.anonymized_at.is_(None), Candidate.merged_into_id.is_(None),
        Candidate.talent_consent_until > utcnow(), User.active.is_(True),
        User.email_verified.is_(True), User.kind == "CANDIDATO",
        Candidate.id.in_(unsuccessful_candidates()),
        Candidate.id.not_in(select(Application.candidate_id).where(Application.vacancy_id == vacancy.id)),
    )).all()
    count = 0
    for candidate in candidates:
        internal = candidate.user_id in employees
        if vacancy.audience != "BOTH" and vacancy.audience != ("INTERNAL" if internal else "EXTERNAL"):
            continue
        if not compatible_profile(model.criteria, candidate.profile.get("facts", {})):
            continue
        cv_id = db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
            Document.type_name == "CURRICULO", Document.status != "REJECTED",
            Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"])
        ).order_by(Document.created_at.desc(), Document.revision.desc()).limit(1))
        application = Application(candidate_id=candidate.id, vacancy_id=vacancy.id,
            stage_id=stage.id, status="ACTIVE", answers={},
            profile_snapshot=deepcopy(candidate.profile), source="BANCO_TALENTOS",
            recruitment_type="INTERNAL" if internal else "EXTERNAL", cv_id=cv_id,
            stage_entered_at=utcnow())
        db.add(application)
        db.flush()
        db.add(StageHistory(application_id=application.id, stage_id=stage.id,
            entered_at=utcnow(), changed_by=actor.user.id,
            reason="Inscrição automática por compatibilidade com o perfil do banco de talentos."))
        calculate_application(db, actor, application, model)
        event(db, actor, "application.created", application, vacancy.id)
        event(db, actor, "talent.auto_enrolled", application, vacancy.id)
        count += 1
    return count
