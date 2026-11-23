from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from test_candidate_journey import journey_owner  # noqa: F401
from test_integration import call

from app.core.db import utcnow
from app.models import Application, Candidate, ScoringVersion, User


def test_rediscovery_uses_profile_facts_and_preserves_consent_and_decisions(client, db, journey_owner, actors):  # noqa: F811
    _, job, admin, _ = journey_owner
    model = db.scalar(select(ScoringVersion).where(ScoringVersion.vacancy_id == job["id"]))
    criteria = [{"key": "experience", "name": "Experiencia", "field": "experience_years",
                       "kind": "NUMBER_MIN", "weight": 100, "expected": 2,
                       "justification": "Experiencia profissional"}]
    db.add(ScoringVersion(vacancy_id=job["id"], number=model.number + 1,
                          criteria=criteria, composition={"OBJECTIVE": 100}, bands=[],
                          reason="Rediscovery test", created_by=actors["admin"]["id"]))
    people = []
    for years, days in [(2, 30), (1, 30), (None, 30), (2, -1)]:
        email = uuid4().hex + "@example.invalid"
        user = User(name="Perfil ficticio", email=email, kind="CANDIDATO")
        db.add(user)
        db.flush()
        person = Candidate(user_id=user.id, name=user.name, email=email,
                           profile={"experience_years": years},
                           talent_consent_until=utcnow() + timedelta(days=days))
        db.add(person)
        people.append(person)
    db.commit()
    before = list(db.scalars(select(Application.id)))
    result = call(client, "get", "/vacancies/" + job["id"] + "/rediscover", admin)
    rows = {row["id"]: row for row in result["items"]}
    assert rows[people[0].id]["compatibility"]["percentage"] == 100
    assert rows[people[1].id]["compatibility"]["percentage"] == 50
    assert rows[people[0].id]["compatibility_rank"] < rows[people[1].id]["compatibility_rank"]
    assert rows[people[2].id]["compatibility"]["percentage"] is None
    assert rows[people[2].id]["compatibility_rank"] is None
    assert people[3].id not in rows
    assert list(db.scalars(select(Application.id))) == before
    call(client, "get", "/vacancies/" + job["id"] + "/rediscover", actors["outsider"]["headers"], expected=403)
