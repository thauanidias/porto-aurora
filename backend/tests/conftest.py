import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings

test_url = make_url(settings().database_url).set(database="tgpm_integration_test")
os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
os.environ["ENVIRONMENT"] = "test"
os.environ["TEST_EMAIL_ENABLED"] = "false"
os.environ["CLAMAV_ENABLED"] = "false"
settings.cache_clear()

from app.bootstrap import seed_permissions  # noqa: E402
from app.core.db import engine, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app, redis  # noqa: E402
from app.models import OrgUnit, Role, User, UserRole  # noqa: E402

TEST_PASSWORD = "Test-only-Long-Password-42"


@pytest.fixture(autouse=True)
def isolated_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "upload_dir", str(tmp_path / "uploads"))


@pytest.fixture
def db():
    assert engine.url.database == "tgpm_integration_test"
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        try:
            seed_permissions(session)
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db):
    def override():
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

    app.dependency_overrides[get_db] = override
    # Only the isolated test-client limiter is reset; operational session keys are preserved.
    redis.delete("limit:testclient:auth", "limit:testclient:api", "limit:testclient:upload")
    with TestClient(app) as client:
        client.test_db = db
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def actors(db, client):
    org = OrgUnit(name="Estrutura de teste", code="TEST-" + uuid4().hex[:8], kind="SECTOR")
    other_org = OrgUnit(name="Outra estrutura", code="OTHER-" + uuid4().hex[:8], kind="SECTOR")
    db.add_all([org, other_org])
    db.flush()
    result = {"org": org.id, "other_org": other_org.id}
    for key, role in [
        ("admin", "SUPER_ADMIN"),
        ("manager", "GESTOR"),
        ("outsider", "GESTOR"),
        ("interviewer", "ENTREVISTADOR"),
        ("auditor", "AUDITOR"),
    ]:
        user = User(
            email=key + "-" + uuid4().hex[:8] + "@example.com",
            name=key.title() + " de Teste",
            kind="INTERNAL",
            email_verified=True,
            password_hash=hash_password(TEST_PASSWORD),
            org_unit_id=other_org.id if key == "outsider" else org.id if key == "manager" else None,
        )
        db.add(user)
        db.flush()
        role_row = db.scalar(select(Role).where(Role.name == role))
        db.add(UserRole(user_id=user.id, role_id=role_row.id))
        db.commit()
        response = client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        result[key] = {
            "id": user.id,
            "email": user.email,
            "headers": {"Authorization": "Bearer " + response.json()["access_token"]},
        }
    return result
