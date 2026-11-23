from sqlalchemy import CheckConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import Active, Body, Data, Entity, Id, Name, Time, fk


class User(Entity):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[Name]
    password_hash: Mapped[Body | None]
    kind: Mapped[str] = mapped_column(String(20), default="CANDIDATO")
    active: Mapped[Active]
    email_verified: Mapped[bool] = mapped_column(default=False)
    auth_source: Mapped[str] = mapped_column(default="LOCAL")
    first_login: Mapped[Time | None]
    last_login: Mapped[Time | None]
    org_unit_id: Mapped[Id | None] = fk("org_units")
    preferences: Mapped[Data]
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_normalized"),)


class Role(Entity):
    __tablename__ = "roles"
    name: Mapped[Name] = mapped_column(unique=True)


class Permission(Base):
    __tablename__ = "permissions"
    name: Mapped[str] = mapped_column(String(90), primary_key=True)
    description: Mapped[Name]


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[Id] = fk("roles", primary_key=True)
    permission: Mapped[str] = mapped_column(
        __import__("sqlalchemy").ForeignKey("permissions.name"), primary_key=True
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[Id] = fk("users", primary_key=True)
    role_id: Mapped[Id] = fk("roles", primary_key=True)


class AuthSession(Entity):
    __tablename__ = "auth_sessions"
    user_id: Mapped[Id] = fk("users", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    expires_at: Mapped[Time]
    revoked_at: Mapped[Time | None]
    ip: Mapped[str] = mapped_column(default="")
    user_agent: Mapped[str] = mapped_column(default="")
    directory_auth: Mapped[Data] = mapped_column(server_default=text("'{}'::jsonb"))


class AuthToken(Entity):
    __tablename__ = "auth_tokens"
    user_id: Mapped[Id] = fk("users", index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    purpose: Mapped[str]
    expires_at: Mapped[Time]
    used_at: Mapped[Time | None]


class OrgUnit(Entity):
    __tablename__ = "org_units"
    name: Mapped[Name]
    code: Mapped[str] = mapped_column(String(60), unique=True)
    kind: Mapped[str]
    parent_id: Mapped[Id | None] = fk("org_units", index=True)
    active: Mapped[Active]


class ConfigRecord(Entity):
    __tablename__ = "config_records"
    kind: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[Name]
    data: Mapped[Data]
    active: Mapped[Active]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("kind", "name"),)


class ConfigRevision(Entity):
    __tablename__ = "config_revisions"
    record_id: Mapped[Id] = fk("config_records", index=True)
    revision: Mapped[int]
    data: Mapped[Data]
    reason: Mapped[Body]
    created_by: Mapped[Id] = fk("users")
    __table_args__ = (UniqueConstraint("record_id", "revision"),)


class Candidate(Entity):
    admission_documents_approved: Mapped[bool] = mapped_column(default=False, server_default="false")
    __table_args__ = (
        Index(
            "candidate_search_idx",
            text(
                "to_tsvector('portuguese'::regconfig, (((name::text || ' '::text) || city::text) || ' '::text) || profile::text)"
            ),
            postgresql_using="gin",
        ),
    )
    __tablename__ = "candidates"
    user_id: Mapped[Id] = fk("users", unique=True)
    name: Mapped[Name]
    social_name: Mapped[str] = mapped_column(default="")
    email: Mapped[str] = mapped_column(String(320), unique=True)
    phone: Mapped[str] = mapped_column(String(30), default="", index=True)
    city: Mapped[str] = mapped_column(default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    country: Mapped[str] = mapped_column(String(2), default="BR")
    profile: Mapped[Data]
    source: Mapped[str] = mapped_column(default="PORTAL")
    talent_consent_until: Mapped[Time | None]
    anonymized_at: Mapped[Time | None]
    merged_into_id: Mapped[Id | None] = fk("candidates")


class SensitiveData(Entity):
    __tablename__ = "candidate_sensitive"
    candidate_id: Mapped[Id] = fk("candidates", unique=True)
    encrypted_data: Mapped[Body]
    purpose: Mapped[Body]
