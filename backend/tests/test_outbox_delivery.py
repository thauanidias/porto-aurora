from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.core.db import utcnow
from app.models import Outbox
from app.tasks import worker


def test_drain_prioritizes_ready_email_and_preserves_scheduled_retry(db, monkeypatch):
    now = utcnow()
    event = Outbox(kind="EVENT", dedup_key=str(uuid4()), payload={},
                   created_at=now - timedelta(minutes=1), available_at=now)
    email = Outbox(kind="EMAIL", dedup_key=str(uuid4()), payload={}, available_at=now)
    retry = Outbox(kind="EMAIL", dedup_key=str(uuid4()), payload={}, status="RETRY",
                   attempts=1, available_at=now + timedelta(minutes=5))
    db.add_all([event, email, retry])
    db.flush()
    delivered = []
    monkeypatch.setattr(worker, "SessionLocal", SimpleNamespace(begin=lambda: nullcontext(db)))
    monkeypatch.setattr(worker, "send_email", lambda *args, **kwargs: delivered.append("EMAIL"))
    monkeypatch.setattr(worker, "process_event", lambda *args: delivered.append("EVENT"))

    assert worker.drain() == 2
    assert delivered == ["EMAIL", "EVENT"]
    assert email.status == event.status == "SENT"
    assert retry.status == "RETRY"
    assert retry.attempts == 1
