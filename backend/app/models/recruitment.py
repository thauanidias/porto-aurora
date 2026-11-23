from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Body, Data, Entity, Id, Items, Name, Time, fk


class VacancyRequest(Entity):
    __tablename__ = "vacancy_requests"
    title: Mapped[Name]
    org_unit_id: Mapped[Id] = fk("org_units", index=True)
    requested_by: Mapped[Id] = fk("users", index=True)
    quantity: Mapped[int]
    status: Mapped[str] = mapped_column(default="DRAFT", index=True)
    details: Mapped[Data]
    workflow_snapshot: Mapped[Items]
    current_step: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint("quantity > 0", name="request_quantity_positive"),)


class Vacancy(Entity):
    __tablename__ = "vacancies"
    request_id: Mapped[Id | None] = fk("vacancy_requests", unique=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    slug: Mapped[str] = mapped_column(String(230), unique=True)
    title: Mapped[Name] = mapped_column(index=True)
    org_unit_id: Mapped[Id] = fk("org_units", index=True)
    recruiter_id: Mapped[Id] = fk("users", index=True)
    manager_id: Mapped[Id] = fk("users")
    quantity: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(default="DRAFT", index=True)
    audience: Mapped[str] = mapped_column(default="EXTERNAL")
    confidential: Mapped[bool] = mapped_column(default=False)
    blind: Mapped[bool] = mapped_column(default=False)
    description: Mapped[Body]
    city: Mapped[str] = mapped_column(default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    modality: Mapped[str] = mapped_column(default="PRESENCIAL")
    contract_type: Mapped[str] = mapped_column(default="CLT")
    deadline: Mapped[Time | None]
    published_at: Mapped[Time | None]
    closed_at: Mapped[Time | None]
    details: Mapped[Data]
    workflow_snapshot: Mapped[Items]
    current_step: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint("quantity > 0", name="vacancy_quantity_positive"),)


class VacancyAssignment(Entity):
    __tablename__ = "vacancy_assignments"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    user_id: Mapped[Id] = fk("users", index=True)
    __table_args__ = (UniqueConstraint("vacancy_id", "user_id"),)


class Approval(Entity):
    __tablename__ = "approvals"
    request_id: Mapped[Id | None] = fk("vacancy_requests", index=True)
    vacancy_id: Mapped[Id | None] = fk("vacancies", index=True)
    offer_id: Mapped[Id | None] = fk("offers", index=True)
    step: Mapped[int]
    approver_id: Mapped[Id] = fk("users")
    delegated_from: Mapped[Id | None] = fk("users")
    decision: Mapped[str]
    comment: Mapped[Body]
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(request_id, vacancy_id, offer_id) = 1", name="approval_one_parent"
        ),
    )


class PipelineStage(Entity):
    __tablename__ = "pipeline_stages"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    name: Mapped[Name]
    position: Mapped[int]
    kind: Mapped[str] = mapped_column(default="SCREENING")
    candidate_phase: Mapped[str | None] = mapped_column(String(20), default=None)
    required: Mapped[bool] = mapped_column(default=False)
    reveal_identity: Mapped[bool] = mapped_column(default=False)
    sla_hours: Mapped[int] = mapped_column(default=72)
    rules: Mapped[Data]
    __table_args__ = (
        UniqueConstraint("vacancy_id", "position"),
        CheckConstraint("sla_hours > 0", name="stage_sla_positive"),
        CheckConstraint("candidate_phase IS NULL OR candidate_phase IN ('REGISTER', 'RECRUITMENT', 'SELECTION', 'FORM', 'INTERVIEW', 'TEST', 'ADMISSION')", name="candidate_phase_valid"),
    )


class Application(Entity):
    __tablename__ = "applications"
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    stage_id: Mapped[Id] = fk("pipeline_stages", index=True)
    status: Mapped[str] = mapped_column(default="ACTIVE", index=True)
    answers: Mapped[Data]
    test_questionnaire: Mapped[Data]
    profile_snapshot: Mapped[Data]
    source: Mapped[str] = mapped_column(default="PORTAL")
    recruitment_type: Mapped[str] = mapped_column(String(20), default="EXTERNAL", server_default="EXTERNAL", index=True)
    utm: Mapped[Data]
    stage_entered_at: Mapped[Time]
    selected_at: Mapped[Time | None]
    closed_at: Mapped[Time | None]
    closure_reason: Mapped[Body]
    cv_id: Mapped[Id | None] = mapped_column(
        ForeignKey("documents.id", name="fk_applications_cv_id", use_alter=True)
    )
    __table_args__ = (
        UniqueConstraint("candidate_id", "vacancy_id"),
        CheckConstraint("recruitment_type IN ('INTERNAL', 'EXTERNAL')", name="application_recruitment_type_valid"),
    )


class StageHistory(Entity):
    __tablename__ = "application_stage_history"
    application_id: Mapped[Id] = fk("applications", index=True)
    stage_id: Mapped[Id] = fk("pipeline_stages")
    entered_at: Mapped[Time]
    left_at: Mapped[Time | None]
    changed_by: Mapped[Id] = fk("users")
    reason: Mapped[Body]


class ScoringVersion(Entity):
    __tablename__ = "scoring_model_versions"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    number: Mapped[int]
    criteria: Mapped[Items]
    composition: Mapped[Data]
    bands: Mapped[Items]
    reason: Mapped[Body]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("vacancy_id", "number"),)


class ApplicationScore(Entity):
    __tablename__ = "application_scores"
    application_id: Mapped[Id] = fk("applications", index=True)
    model_id: Mapped[Id] = fk("scoring_model_versions")
    total: Mapped[float | None] = mapped_column(Numeric(6, 2))
    knockout: Mapped[bool]
    breakdown: Mapped[Data]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (CheckConstraint("total >= 0 AND total <= 100", name="score_bounds"),)


class Offer(Entity):
    __tablename__ = "offers"
    application_id: Mapped[Id] = fk("applications", index=True)
    number: Mapped[int]
    status: Mapped[str] = mapped_column(default="DRAFT")
    terms: Mapped[Data]
    expires_at: Mapped[Time]
    responded_at: Mapped[Time | None]
    response_ip: Mapped[str] = mapped_column(default="")
    response_reason: Mapped[Body]
    workflow_snapshot: Mapped[Items]
    current_step: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("application_id", "number"),)


class ChecklistItem(Entity):
    __tablename__ = "checklist_items"
    application_id: Mapped[Id] = fk("applications", index=True)
    title: Mapped[Name]
    required: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(default="PENDING")
    comment: Mapped[Body]
    reviewed_by: Mapped[Id | None] = fk("users")


class Referral(Entity):
    __tablename__ = "referrals"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    referred_by: Mapped[Id] = fk("users")
    name: Mapped[Name]
    email: Mapped[str]
    comment: Mapped[Body]
    status: Mapped[str] = mapped_column(default="PENDING_CONSENT")
    candidate_id: Mapped[Id | None] = fk("candidates")
    __table_args__ = (UniqueConstraint("vacancy_id", "email"),)
