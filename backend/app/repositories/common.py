from datetime import datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.errors import DomainError


def serialize(entity, exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = (exclude or set()) | {
        "password_hash",
        "token_hash",
        "previous_hash",
        "encrypted_secret",
        "encrypted_data",
    }
    result = {}
    for column in inspect(entity).mapper.column_attrs:
        if column.key not in excluded:
            value = getattr(entity, column.key)
            result[column.key] = (
                value.isoformat()
                if isinstance(value, datetime)
                else float(value)
                if isinstance(value, Decimal)
                else value
            )
    return result


def page(
    db: Session,
    query,
    page_number: int = 1,
    page_size: int = 25,
    serializer=serialize,
    prepare=None,
):
    count = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = db.scalars(query.offset((page_number - 1) * page_size).limit(page_size)).all()
    if prepare:
        prepare(rows)
    return {
        "items": [serializer(row) for row in rows],
        "total": count,
        "page": page_number,
        "page_size": page_size,
    }


def check_version(entity, version: int) -> None:
    if entity.version != version:
        raise DomainError(
            "Este registro foi alterado por outra pessoa. Atualize a página.",
            409,
            "VERSION_CONFLICT",
        )


EntityType = TypeVar("EntityType")


def required(db: Session, model: type[EntityType], entity_id: str) -> EntityType:
    entity = db.get(model, entity_id)
    if entity is None:
        raise DomainError("Registro vinculado não encontrado.", 404, "NOT_FOUND")
    return entity
