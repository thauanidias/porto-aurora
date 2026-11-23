"""Prepare independent integration and browser databases with production migrations."""

import os

from alembic import command
from alembic.config import Config
from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(settings().database_url)
engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
for name in ("tgpm_test", "tgpm_integration_test"):
    with engine.connect() as connection:
        if not connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": name}
        ):
            connection.execute(text("CREATE DATABASE " + name))
    os.environ["DATABASE_URL"] = url.set(database=name).render_as_string(
        hide_password=False
    )
    os.environ["ENVIRONMENT"] = "test"
    settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
engine.dispose()
print("Bancos de integração e navegador prontos; banco operacional preservado.")
