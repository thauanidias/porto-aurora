from datetime import datetime
from typing import Annotated, Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.db import Base, utcnow

Id = Annotated[str, mapped_column(String(36))]
Name = Annotated[str, mapped_column(String(180))]
Body = Annotated[str, mapped_column(Text, default="")]
Data = Annotated[dict[str, Any], mapped_column(JSONB, default=dict)]
Items = Annotated[list[dict[str, Any]], mapped_column(JSONB, default=list)]
Time = Annotated[datetime, mapped_column(DateTime(timezone=True))]
Active = Annotated[bool, mapped_column(Boolean, default=True)]


def fk(target: str, **kwargs):
    return mapped_column(ForeignKey(target + ".id"), **kwargs)


class Entity(Base):
    __abstract__ = True
    id: Mapped[Id] = mapped_column(primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[Time] = mapped_column(default=utcnow)
    updated_at: Mapped[Time] = mapped_column(default=utcnow, onupdate=utcnow)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    @declared_attr.directive
    def __mapper_args__(cls):
        return {"version_id_col": cls.version}
