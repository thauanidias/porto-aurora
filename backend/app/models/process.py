from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Body, Entity, Id, Items, Time, fk


class StageReview(Entity):
    __tablename__ = "stage_reviews"
    application_id: Mapped[Id] = fk("applications", index=True)
    stage_id: Mapped[Id] = fk("pipeline_stages")
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[Body]
    reviewed_by: Mapped[Id] = fk("users")
    __table_args__ = (CheckConstraint("status IN ('APPROVED', 'REJECTED', 'PENDING')", name="stage_review_status_valid"),)


class ProcessForm(Entity):
    __tablename__ = "process_forms"
    application_id: Mapped[Id] = fk("applications", unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[Time]
    sent_at: Mapped[Time]
    submitted_at: Mapped[Time | None]
    status: Mapped[str] = mapped_column(String(20), default="SENT")
    questions: Mapped[Items]
    encrypted_data: Mapped[Body]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (CheckConstraint("status IN ('SENT', 'PENDING', 'COMPLETED')", name="process_form_status_valid"),)
