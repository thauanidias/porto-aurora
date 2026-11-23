from datetime import datetime, timezone
from uuid import uuid4

from test_candidate_journey import journey_owner  # noqa: F401
from test_integration import call

from app.models import AuditLog


def test_audit_readable_names_local_date_filters_and_access(client, db, journey_owner, actors):  # noqa: F811
    _, job, admin, _ = journey_owner
    target = uuid4().hex
    for hour in [2, 4]:
        db.add(AuditLog(action="candidate.accessed", entity="candidates", entity_id=target,
                        user_id=actors["admin"]["id"], vacancy_id=job["id"], before={}, after={},
                        created_at=datetime(2026, 11, 4, hour, tzinfo=timezone.utc)))
    db.commit()
    result = call(client, "get", "/audit?q=" + target + "&date_from=2026-11-04&date_to=2026-11-04", admin)
    assert result["total"] == 1
    assert result["items"][0]["user_name"] == "Admin de Teste"
    assert result["items"][0]["vacancy_title"] == job["title"]
    assert result["items"][0]["entity_id"] == target
    assert call(client, "get", "/audit?q=" + target, admin)["total"] == 2
    assert call(client, "get", "/audit?q=" + target + "&action=document.", admin)["total"] == 0
    call(client, "get", "/audit?date_from=2026-11-05&date_to=2026-11-04", admin, expected=422)
    call(client, "get", "/audit", actors["outsider"]["headers"], expected=403)
    assert call(client, "get", "/audit?q=" + target, actors["auditor"]["headers"])["total"] == 0
