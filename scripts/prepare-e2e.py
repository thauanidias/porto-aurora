"""Create a test-only administrator; write credentials to an ignored local file."""

import json
import os
import secrets
from pathlib import Path

from app.core.config import settings
from sqlalchemy import select
from sqlalchemy.engine import make_url

cfg = settings()
os.environ["DATABASE_URL"] = (
    make_url(cfg.database_url)
    .set(database="tgpm_test")
    .render_as_string(hide_password=False)
)
os.environ["ENVIRONMENT"] = "test"
settings.cache_clear()
from app.bootstrap import seed_permissions
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Role, User, UserRole

email = "admin.e2e@example.com"
password = secrets.token_urlsafe(24)
with SessionLocal.begin() as db:
    if db.bind.url.database != "tgpm_test":
        raise RuntimeError("E2E is restricted to tgpm_test")
    seed_permissions(db)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            name="Administrador E2E", email=email, kind="INTERNAL", email_verified=True
        )
        db.add(user)
    user.password_hash = hash_password(password)
    db.flush()
    role = db.scalar(select(Role).where(Role.name == "SUPER_ADMIN"))
    if not db.get(UserRole, (user.id, role.id)):
        db.add(UserRole(user_id=user.id, role_id=role.id))
Path("/e2e/.e2e-credentials.json").write_text(
    json.dumps({"email": email, "password": password, "id": user.id}), encoding="utf-8"
)
print("Administrador E2E preparado exclusivamente no banco de teste.")
