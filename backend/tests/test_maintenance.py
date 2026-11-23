from datetime import timedelta

from test_governance import application_fixture
from test_integration import call

from app.core.db import utcnow
from app.models import TestAttempt as Attempt
from app.services.maintenance import expire_records


def test_autosave_expiry_and_unanswered_false_are_not_correct(client, db, actors):
    vacancy, notice, candidate, profile, application = application_fixture(client, actors)
    admin = actors["admin"]["headers"]
    test = call(
        client,
        "post",
        "/tests",
        admin,
        {
            "name": "Teste com expiração",
            "duration_minutes": 1,
            "questions": [
                {
                    "key": "answered",
                    "text": "Questão respondida",
                    "kind": "BOOLEAN",
                    "correct": True,
                },
                {
                    "key": "unanswered",
                    "text": "Questão sem resposta",
                    "kind": "BOOLEAN",
                    "correct": False,
                },
            ],
        },
        201,
    )
    assignment = call(
        client,
        "post",
        "/tests/" + test["id"] + "/assign",
        admin,
        {
            "application_id": application["id"],
            "opens_at": (utcnow() - timedelta(minutes=10)).isoformat(),
            "due_at": (utcnow() + timedelta(days=1)).isoformat(),
        },
        201,
    )
    attempt = call(client, "post", "/test-assignments/" + assignment["id"] + "/start", candidate)
    saved = call(
        client,
        "put",
        "/test-attempts/" + attempt["id"] + "/answers",
        candidate,
        {"version": attempt["version"], "answers": {"answered": True}},
    )
    assert saved["version"] > attempt["version"]
    row = db.get(Attempt, attempt["id"])
    row.started_at = utcnow() - timedelta(minutes=2)
    db.commit()
    assert expire_records(db) == 1
    db.flush()
    assert row.status == "GRADED" and float(row.score) == 50
    assert row.grading["unanswered"]["score"] == 0
    assert expire_records(db) == 0
