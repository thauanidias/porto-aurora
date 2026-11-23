from uuid import uuid4

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, utcnow
from app.models.base import Body, Data, Entity, Id, Name, Time, fk


class ManagerAccessRequest(Entity):
    __tablename__ = "manager_access_requests"
    name: Mapped[Name]
    email: Mapped[str] = mapped_column(String(320), unique=True)
    department: Mapped[Name]
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    user_id: Mapped[Id | None] = fk("users")
    reviewed_by: Mapped[Id | None] = fk("users")
    reason: Mapped[Body]


class EmployeeAccessRequest(Entity):
    __tablename__ = "employee_access_requests"
    name: Mapped[Name]
    email: Mapped[str] = mapped_column(String(320), unique=True)
    network_username: Mapped[str] = mapped_column(String(180), unique=True)
    department: Mapped[Name]
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    user_id: Mapped[Id | None] = fk("users")
    email_confirmed_at: Mapped[Time | None]
    email_code_hash: Mapped[str | None] = mapped_column(String(64))
    email_code_expires_at: Mapped[Time | None]
    email_code_sent_at: Mapped[Time | None]
    email_code_attempts: Mapped[int] = mapped_column(default=0, server_default="0")


class Document(Entity):
    __tablename__ = "documents"
    candidate_id: Mapped[Id | None] = fk("candidates", index=True)
    request_id: Mapped[Id | None] = fk("vacancy_requests")
    application_id: Mapped[Id | None] = fk("applications")
    uploaded_by: Mapped[Id] = fk("users")
    type_name: Mapped[Name]
    filename: Mapped[Name]
    storage_key: Mapped[str] = mapped_column(unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size: Mapped[int]
    mime: Mapped[str]
    revision: Mapped[int]
    status: Mapped[str] = mapped_column(default="PENDING")
    scan_status: Mapped[str]
    comment: Mapped[Body]
    reviewed_by: Mapped[Id | None] = fk("users")


class CandidateDocumentSource(Entity):
    __tablename__ = "candidate_document_sources"
    __table_args__ = (UniqueConstraint("candidate_id", "source_candidate_id"),)
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    source_candidate_id: Mapped[Id] = fk("candidates")
    linked_by: Mapped[Id] = fk("users")
    reason: Mapped[Body]
    documents: Mapped[Data]


class ConsentReceipt(Entity):
    __tablename__ = "consent_receipts"
    protocol: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[Name]
    email: Mapped[str] = mapped_column(String(320), index=True)
    user_id: Mapped[Id | None] = fk("users")
    ip: Mapped[str] = mapped_column(String(45))
    context: Mapped[str] = mapped_column(String(30))
    document_code: Mapped[str] = mapped_column(String(50))
    document_sha256: Mapped[str] = mapped_column(String(64))
    document_snapshot: Mapped[Data]


class Consent(Entity):
    __tablename__ = "consents"
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    notice_id: Mapped[Id | None] = fk("config_records")
    notice_version: Mapped[int]
    notice_snapshot: Mapped[Data]
    purpose: Mapped[str]
    granted: Mapped[bool]
    ip: Mapped[str]


class DataSubjectRequest(Entity):
    __tablename__ = "data_subject_requests"
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    kind: Mapped[str]
    status: Mapped[str] = mapped_column(default="OPEN")
    detail: Mapped[Body]
    response: Mapped[Body]
    handled_by: Mapped[Id | None] = fk("users")


class Outbox(Entity):
    __tablename__ = "outbox"
    kind: Mapped[str] = mapped_column(index=True)
    dedup_key: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[Data]
    status: Mapped[str] = mapped_column(default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[Time] = mapped_column(default=utcnow)
    error: Mapped[str] = mapped_column(default="")


class Webhook(Entity):
    __tablename__ = "webhooks"
    name: Mapped[Name]
    url: Mapped[Body]
    encrypted_secret: Mapped[Body]
    events: Mapped[list[str]] = mapped_column(__import__("sqlalchemy").dialects.postgresql.JSONB)
    enabled: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[Id] = fk("users")


class AutomationExecution(Entity):
    __tablename__ = "automation_executions"
    rule_id: Mapped[Id] = fk("config_records")
    event_id: Mapped[str]
    status: Mapped[str]
    detail: Mapped[Body]
    __table_args__ = (UniqueConstraint("rule_id", "event_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[Id] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[Time] = mapped_column(default=utcnow, index=True)
    user_id: Mapped[Id | None] = fk("users")
    action: Mapped[str] = mapped_column(index=True)
    entity: Mapped[str]
    entity_id: Mapped[str] = mapped_column(index=True)
    vacancy_id: Mapped[Id | None] = fk("vacancies", index=True)
    before: Mapped[Data]
    after: Mapped[Data]
    ip: Mapped[str] = mapped_column(default="")
    request_id: Mapped[str] = mapped_column(default="")
