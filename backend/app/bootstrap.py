import getpass
import os

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.permissions import PERMISSIONS, ROLES
from app.core.security import hash_password
from app.models import Permission, Role, RolePermission, User, UserRole


def seed_permissions(db):
    for permission in sorted(PERMISSIONS):
        if not db.get(Permission, permission):
            db.add(Permission(name=permission, description=permission))
    db.flush()
    for name, permissions in ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if not role:
            role = Role(name=name)
            db.add(role)
            db.flush()
            for permission in permissions:
                db.add(RolePermission(role_id=role.id, permission=permission))
    db.flush()


def main():
    email = (
        (os.environ.get("BOOTSTRAP_EMAIL") or input("E-mail do administrador: ")).strip().lower()
    )
    name = os.environ.get("BOOTSTRAP_NAME") or input("Nome do administrador: ")
    password = os.environ.get("BOOTSTRAP_PASSWORD") or getpass.getpass(
        "Senha (mínimo 12 caracteres): "
    )
    from pydantic import EmailStr, TypeAdapter

    email = str(TypeAdapter(EmailStr).validate_python(email))
    with SessionLocal.begin() as db:
        seed_permissions(db)
        if db.scalar(select(User.id).where(User.email == email)):
            raise SystemExit("Usuário já existe; nenhuma senha foi alterada.")
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            kind="INTERNAL",
            email_verified=True,
        )
        db.add(user)
        db.flush()
        role = db.scalar(select(Role).where(Role.name == "SUPER_ADMIN"))
        if role is None:
            raise RuntimeError("Perfil de contingência ausente")
        db.add(UserRole(user_id=user.id, role_id=role.id))
    print("Administrador criado.")


if __name__ == "__main__":
    main()
