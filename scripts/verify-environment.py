"""Read-only operational verification without printing connection strings or secrets."""

import json
from pathlib import Path

from app.core.config import settings
from app.core.db import engine
from app.main import app
from sqlalchemy import text

cfg = settings()
with engine.connect() as connection:
    counts = {
        table: connection.scalar(text("SELECT count(*) FROM " + table))
        for table in (
            "users",
            "candidates",
            "vacancies",
            "applications",
            "offers",
            "documents",
        )
    }
    version = connection.scalar(text("SELECT version_num FROM alembic_version"))
result = {
    "application_version": app.version,
    "database_name": engine.url.database,
    "business_counts": counts,
    "migration": version,
    "environment": cfg.environment,
    "integrations": {
        "smtp": cfg.smtp_enabled,
        "ldap": cfg.ldap_enabled,
        "graph": cfg.graph_enabled,
        "antimalware": cfg.clamav_enabled,
    },
    "tables": len(__import__("app.core.db", fromlist=["Base"]).Base.metadata.tables),
}
print(json.dumps(result, ensure_ascii=False))
destination = Path("/docs/ambiente-verificado.json")
if destination.parent.is_dir():
    destination.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
