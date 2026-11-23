"""Round-trip migrations against a disposable, empty PostgreSQL database."""

import os
import re
from uuid import uuid4

from alembic import command
from alembic.config import Config
from app.core.config import settings
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(settings().database_url)
name = "tgpm_migration_" + uuid4().hex[:12]
if not re.fullmatch(r"tgpm_migration_[a-f0-9]{12}", name):
    raise RuntimeError("Invalid isolation name")
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as connection:
    connection.execute(text("CREATE DATABASE " + name))
try:
    os.environ["DATABASE_URL"] = url.set(database=name).render_as_string(
        hide_password=False
    )
    settings.cache_clear()
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    command.check(cfg)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    test = create_engine(settings().database_url)
    with test.connect() as connection:
        counts = [
            connection.scalar(text("SELECT count(*) FROM " + table))
            for table in ["users", "candidates", "vacancies", "applications", "offers"]
        ]
        if any(counts):
            raise RuntimeError("Migrations created business data")
    test.dispose()
    print(
        "Migrations: upgrade, schema check, downgrade and upgrade passed; business database empty."
    )
finally:
    with admin.connect() as connection:
        connection.execute(text("DROP DATABASE " + name + " WITH (FORCE)"))
    admin.dispose()
