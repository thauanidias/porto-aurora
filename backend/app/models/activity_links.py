from datetime import datetime
from sqlalchemy import CheckConstraint, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Active, Body, Entity, Id, Name, fk


class CandidateActivityLink(Entity):
    __tablename__ = "candidate_activity_links"
    application_id: Mapped[Id] = fk("applications", index=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[Name]
    description: Mapped[Body]
    url: Mapped[str] = mapped_column(String(2048))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[Active]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (CheckConstraint("kind IN ('INTERVIEW', 'TEST')", name="activity_link_kind_valid"),)
