from sqlalchemy import Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Entity, Id, Body, fk

class CandidateFeedback(Entity):
    __tablename__ = "candidate_feedback"
    candidate_id: Mapped[Id] = fk("candidates", index=True)
    application_id: Mapped[Id] = fk("applications", index=True)
    message: Mapped[Body]
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (CheckConstraint("rating IS NULL OR rating BETWEEN 1 AND 5", name="candidate_feedback_rating_valid"),)
