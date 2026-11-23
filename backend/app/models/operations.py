from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Active, Body, Data, Entity, Id, Items, Name, Time, fk


class Assessment(Entity):
    __tablename__ = "assessments"
    name: Mapped[Name]
    duration_minutes: Mapped[int] = mapped_column(default=60)
    attempts_allowed: Mapped[int] = mapped_column(default=1)
    pass_score: Mapped[float] = mapped_column(Numeric(6, 2), default=60)
    shuffle: Mapped[bool] = mapped_column(default=False)
    questions: Mapped[Items]
    created_by: Mapped[Id] = fk("users")
    active: Mapped[Active]


class TestAssignment(Entity):
    __tablename__ = "test_assignments"
    application_id: Mapped[Id] = fk("applications", index=True)
    assessment_id: Mapped[Id] = fk("assessments")
    snapshot: Mapped[Data]
    opens_at: Mapped[Time]
    due_at: Mapped[Time]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("application_id", "assessment_id"),)


class TestAttempt(Entity):
    __tablename__ = "test_attempts"
    assignment_id: Mapped[Id] = fk("test_assignments", index=True)
    number: Mapped[int]
    started_at: Mapped[Time]
    submitted_at: Mapped[Time | None]
    answers: Mapped[Data]
    grading: Mapped[Data]
    score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    status: Mapped[str] = mapped_column(default="STARTED")
    graded_by: Mapped[Id | None] = fk("users")
    __table_args__ = (UniqueConstraint("assignment_id", "number"),)


class Interview(Entity):
    __tablename__ = "interviews"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    title: Mapped[Name]
    kind: Mapped[str]
    starts_at: Mapped[Time] = mapped_column(index=True)
    ends_at: Mapped[Time]
    capacity: Mapped[int] = mapped_column(default=1)
    location: Mapped[Body]
    status: Mapped[str] = mapped_column(default="SCHEDULED")
    template: Mapped[Data]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (
        CheckConstraint("ends_at > starts_at AND capacity > 0", name="interview_valid"),
    )


class InterviewParticipant(Entity):
    __tablename__ = "interview_participants"
    interview_id: Mapped[Id] = fk("interviews", index=True)
    user_id: Mapped[Id] = fk("users", index=True)
    application_id: Mapped[Id | None] = fk("applications")
    __table_args__ = (UniqueConstraint("interview_id", "user_id"),)


class Evaluation(Entity):
    __tablename__ = "evaluations"
    application_id: Mapped[Id] = fk("applications", index=True)
    interview_id: Mapped[Id | None] = fk("interviews")
    evaluator_id: Mapped[Id] = fk("users", index=True)
    category: Mapped[str] = mapped_column(default="RH")
    criteria: Mapped[Items]
    answers: Mapped[Data]
    independent: Mapped[bool] = mapped_column(default=True)
    submitted_at: Mapped[Time | None]
    score: Mapped[float | None] = mapped_column(Numeric(6, 2))
    recommendation: Mapped[str] = mapped_column(default="")
    __table_args__ = (UniqueConstraint("application_id", "evaluator_id", "category"),)


class TalentPool(Entity):
    __tablename__ = "talent_pools"
    name: Mapped[Name] = mapped_column(unique=True)
    description: Mapped[Body]
    filters: Mapped[Data]
    created_by: Mapped[Id] = fk("users")


class TalentPoolMember(Entity):
    __tablename__ = "talent_pool_members"
    pool_id: Mapped[Id] = fk("talent_pools", index=True)
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    added_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("pool_id", "candidate_id"),)


class CandidateLabel(Entity):
    __tablename__ = "candidate_labels"
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    user_id: Mapped[Id] = fk("users")
    label: Mapped[Name]
    kind: Mapped[str] = mapped_column(default="TAG")
    __table_args__ = (UniqueConstraint("candidate_id", "user_id", "kind", "label"),)


class Task(Entity):
    __tablename__ = "tasks"
    title: Mapped[Name]
    assigned_to: Mapped[Id] = fk("users", index=True)
    created_by: Mapped[Id] = fk("users")
    vacancy_id: Mapped[Id | None] = fk("vacancies", index=True)
    application_id: Mapped[Id | None] = fk("applications")
    due_at: Mapped[Time] = mapped_column(index=True)
    priority: Mapped[str] = mapped_column(default="NORMAL")
    status: Mapped[str] = mapped_column(default="OPEN")
    description: Mapped[Body]


class Notification(Entity):
    __tablename__ = "notifications"
    user_id: Mapped[Id] = fk("users", index=True)
    title: Mapped[Name]
    body: Mapped[Body]
    category: Mapped[str]
    link: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="UNREAD")


class Message(Entity):
    __tablename__ = "messages"
    application_id: Mapped[Id] = fk("applications", index=True)
    sender_id: Mapped[Id] = fk("users")
    subject: Mapped[Name]
    body: Mapped[Body]
    visibility: Mapped[str] = mapped_column(default="CANDIDATE")


class VacancyMessage(Entity):
    __tablename__ = "vacancy_messages"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    sender_id: Mapped[Id] = fk("users")
    body: Mapped[Body]


class SurveyResponse(Entity):
    __tablename__ = "survey_responses"
    candidate_id: Mapped[Id] = fk("candidates")
    survey_id: Mapped[Id] = fk("config_records")
    answers: Mapped[Data]
    __table_args__ = (UniqueConstraint("candidate_id", "survey_id"),)
