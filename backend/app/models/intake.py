from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Data, Entity, Id, Name, Time, fk


class QuickApplication(Entity):
    __tablename__ = "quick_applications"
    vacancy_id: Mapped[Id] = fk("vacancies", index=True)
    notice_id: Mapped[Id] = fk("config_records")
    name: Mapped[Name]
    email: Mapped[str] = mapped_column(String(320), index=True)
    phone: Mapped[str] = mapped_column(String(30), default="")
    answers: Mapped[Data]
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[Time]
    confirmed_at: Mapped[Time | None]


class ImportBatch(Entity):
    __tablename__ = "import_batches"
    created_by: Mapped[Id] = fk("users")
    sha256: Mapped[str] = mapped_column(String(64))
    rows: Mapped[Data]
    status: Mapped[str] = mapped_column(default="PREVIEW")
    confirmed_at: Mapped[Time | None]
