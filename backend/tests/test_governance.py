from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.core.db import utcnow
from app.core.security import digest
from app.models import Candidate, Evaluation, QuickApplication, Vacancy


def application_fixture(client, actors):
    vacancy, notice, workflow, model = setup_vacancy(client, actors)
    candidate, profile, email = register_candidate(client, notice)
    application = call(
        client,
        "post",
        "/applications",
        candidate,
        {
            "vacancy_id": vacancy["id"],
            "notice_id": notice["id"],
            "consent": True,
            "answers": {"interest": "Interesse profissional"},
        },
        201,
    )
    return vacancy, notice, candidate, profile, application


def test_blind_identity_and_candidate_consensus_denied(client, db, actors):
    vacancy, notice, candidate, profile, application = application_fixture(client, actors)
    row = db.get(Vacancy, vacancy["id"])
    row.blind = True
    db.commit()
    admin = actors["admin"]["headers"]
    result = call(client, "get", "/applications/" + application["id"], admin)
    assert result["candidate"]["blind"] is True
    assert not {"profile_snapshot", "answers", "cv_id", "utm"} & result.keys()
    call(
        client, "get", "/applications/" + application["id"] + "/consensus", candidate, expected=403
    )
    for suffix in ["?q=Pessoa", "?city=Belém", "?state=PA"]:
        assert call(client, "get", "/candidates" + suffix, admin)["total"] == 0
    assert call(client, "get", "/documents?candidate_id=" + profile["id"], admin)["items"] == []


def test_independence_covers_score_and_comparison(client, db, actors):
    vacancy, notice, candidate, profile, application = application_fixture(client, actors)
    admin = actors["admin"]["headers"]
    for key, score in [("admin", 90), ("interviewer", None)]:
        row = Evaluation(
            application_id=application["id"],
            evaluator_id=actors[key]["id"],
            category="RH",
            criteria=[],
            answers={},
            independent=True,
            score=score,
            submitted_at=utcnow() if score else None,
        )
        db.add(row)
    db.commit()
    result = call(client, "get", "/applications/" + application["id"], admin)
    assert all(score["total"] is None and score["sealed"] for score in result["scores"])
    comparison = call(
        client, "get", "/vacancies/" + vacancy["id"] + "/compare?ids=" + application["id"], admin
    )
    assert comparison["items"][0]["total"] is None
    assert comparison["items"][0]["consensus"]["sealed"]
    assert call(client, "get", "/analytics/calibration", admin)["items"] == []
    call(
        client,
        "get",
        "/vacancies/" + vacancy["id"] + "/compare?ids=" + application["id"],
        actors["outsider"]["headers"],
        expected=404,
    )


@pytest.mark.parametrize(
    "raw", [b"", b"name,email\nWrong,invalid\n", b"unexpected,email\nName,test@example.com\n"]
)
def test_import_rejects_invalid_atomically(client, db, actors, raw):
    admin = actors["admin"]["headers"]
    before = len(list(db.scalars(select(Candidate))))
    result = client.post(
        "/api/v1/imports/candidates/preview",
        headers=admin,
        files={"file": ("input.csv", raw, "text/csv")},
    )
    assert result.status_code in {201, 400, 422}
    if result.status_code == 201:
        assert not result.json()["can_confirm"]
        call(
            client,
            "post",
            "/imports/candidates/" + result.json()["id"] + "/confirm",
            admin,
            expected=409,
        )
    assert len(list(db.scalars(select(Candidate)))) == before


def test_import_confirmation_idempotent(client, db, actors):
    admin = actors["admin"]["headers"]
    address = uuid4().hex + "@example.com"
    raw = ("name;email;city;state\nPessoa Importada;" + address + ";Belém;PA\n").encode()
    result = client.post(
        "/api/v1/imports/candidates/preview",
        headers=admin,
        files={"file": ("input.csv", raw, "text/csv")},
    )
    assert result.status_code == 201, result.text
    assert result.json()["can_confirm"]
    call(
        client,
        "post",
        "/imports/candidates/" + result.json()["id"] + "/confirm",
        actors["manager"]["headers"],
        expected=403,
    )
    for _ in range(2):
        assert (
            call(client, "post", "/imports/candidates/" + result.json()["id"] + "/confirm", admin)[
                "count"
            ]
            == 1
        )
    candidate = db.scalar(select(Candidate).where(Candidate.email == address))
    assert candidate.talent_consent_until is None


def test_quick_confirmation_single_use_and_disabled_connector(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    data = {
        "vacancy_id": vacancy["id"],
        "notice_id": notice["id"],
        "name": "Pessoa Link",
        "email": uuid4().hex + "@example.com",
        "consent": True,
        "answers": {"interest": "Interesse profissional"},
    }
    call(client, "post", "/public/quick-apply", {}, data, expected=403)
    token = uuid4().hex * 2
    row = QuickApplication(
        vacancy_id=vacancy["id"],
        notice_id=notice["id"],
        name=data["name"],
        email=data["email"],
        answers=data["answers"],
        token_hash=digest(token),
        expires_at=utcnow() + timedelta(minutes=10),
    )
    db.add(row)
    db.commit()
    # Legacy quick links cannot bypass the saved-profile enrollment requirements.
    result = call(client, "post", "/auth/consume-quick", {}, {"token": token}, expected=422)
    assert result["code"] == "PROFILE_INCOMPLETE"
    assert db.get(QuickApplication, row.id).confirmed_at is None


def test_note_visibility_history_and_search_scope(client, db, actors):
    vacancy, notice, candidate, profile, application = application_fixture(client, actors)
    from test_integration import release_test_stage
    release_test_stage(client, application["id"])
    admin = actors["admin"]["headers"]
    note = call(
        client,
        "post",
        "/applications/" + application["id"] + "/messages",
        admin,
        {
            "subject": "Nota de processo",
            "body": "Evidência profissional observada",
            "visibility": "PRIVATE",
        },
        201,
    )
    note = call(
        client,
        "put",
        "/messages/" + note["id"],
        admin,
        {
            "version": note["version"],
            "body": "Evidência profissional revisada",
            "reason": "Correção de anotação",
        },
    )
    assert len(call(client, "get", "/messages/" + note["id"] + "/history", admin)["items"]) == 1
    assert (
        call(client, "get", "/applications/" + application["id"] + "/messages", candidate)["items"]
        == []
    )
    call(client, "get", "/messages/" + note["id"] + "/history", candidate, expected=403)
    assert call(client, "get", "/search?q=Analista", actors["outsider"]["headers"])["items"] == []
    assert call(client, "get", "/search?q=Analista", admin)["items"]
