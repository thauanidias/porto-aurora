from types import SimpleNamespace

import pytest

from app.core.errors import DomainError
from app.services.curriculum_matching import Evidence, Findings, summarize_findings


def rules():
    return [{"key": "skills", "name": "Competências técnicas", "field": "skills", "weight": 60,
             "expected": ["Python"], "mandatory": True},
            {"key": "education", "name": "Formação", "field": "education_level", "weight": 40,
             "expected": 4}]


def test_ai_evidence_must_be_literal_and_missing_information_is_not_a_failure():
    result = summarize_findings(rules(), Findings(items=[
        Evidence(key="skills", status="MET", evidence="Python"),
        Evidence(key="education", status="NOT_MET", evidence="Formação não encontrada"),
    ]), "Experiência com Python")
    assert result["percentage"] == 60
    assert result["coverage"] == 60
    assert result["status"] == "PENDING"
    assert result["items"][1]["status"] == "UNKNOWN"
    assert result["items"][1]["evidence"] == ""
    assert result["mandatory_pending"] == []


def test_no_verified_information_produces_no_score_or_knockout():
    result = summarize_findings(rules(), Findings(items=[]), "Currículo sem dados profissionais")
    assert result["percentage"] is None
    assert result["mandatory_pending"] == ["Competências técnicas"]
    assert "knockout" not in result


def test_duplicate_ai_criteria_are_rejected_and_extra_fields_cannot_affect_score():
    item = Evidence(key="skills", status="MET", evidence="Python")
    with pytest.raises(DomainError):
        summarize_findings(rules(), Findings(items=[item, item]), "Python")
    result = summarize_findings(rules(), Findings(items=[
        Evidence(key="age", status="MET", evidence="25 anos")]), "25 anos")
    assert result["percentage"] is None
    assert all(item["key"] != "age" for item in result["items"])


def test_analysis_route_preserves_decision_and_records_history(client, db, actors, monkeypatch):
    from test_integration import call, register_candidate, setup_vacancy
    from app.models import Application, ApplicationScore
    from sqlalchemy import select

    vacancy, notice, _, _ = setup_vacancy(client, actors)
    owner, candidate, _ = register_candidate(client, notice)
    application = call(client, "post", "/applications", owner,
        {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    admin = actors["admin"]["headers"]
    path = "/applications/" + application["id"] + "/curriculum-analysis"
    assert client.post("/api/v1" + path, headers=owner, json={}).status_code == 403
    row = db.get(Application, application["id"])
    previous = row.status, row.stage_id
    monkeypatch.setattr("app.services.curriculum_matching.analyze_curriculum", lambda *args: {
        "percentage": 60, "status": "PENDING", "document_id": "test-file", "items": [], "engine": "test"})
    result = call(client, "post", path, admin, {})
    assert result["percentage"] == 60
    db.refresh(row)
    assert (row.status, row.stage_id) == previous
    records = db.scalars(select(ApplicationScore).where(ApplicationScore.application_id == row.id)).all()
    assert any(score.breakdown.get("curriculum_analysis", {}).get("percentage") == 60 for score in records)
    history = call(client, "get", path + "/history", admin)
    assert history["items"][0]["analysis"]["percentage"] == 60
    assert client.get("/api/v1" + path + "/history", headers=owner).status_code == 403
    from app.services.recruitment import calculate_application
    from app.core.permissions import Actor
    from app.models import User
    score = calculate_application(db, Actor(db.get(User, actors["admin"]["id"]), set(), "", "", ""), row)
    assert score.breakdown["curriculum_analysis"]["percentage"] == 60
    call(client, "post", "/applications/" + row.id + "/stage-reviews", admin,
         {"status": "APPROVED", "reason": "Evidências conferidas pelo RH", "version": row.version}, 201)
    listing = call(client, "get", "/applications?vacancy_id=" + vacancy["id"], admin)
    assert listing["items"][0]["screening_review"]["status"] == "APPROVED"
    own_listing = call(client, "get", "/applications?vacancy_id=" + vacancy["id"], owner)
    assert "screening_review" not in own_listing["items"][0]


def test_suggested_criteria_require_professional_fields_and_literal_vacancy_evidence(monkeypatch):
    import json
    from app.services import curriculum_matching as matching
    config = SimpleNamespace(resume_ai_enabled=True, resume_ai_url="http://resume-ai:11434", resume_ai_model="test")
    monkeypatch.setattr(matching, "settings", lambda: config)
    criterion = {"key": "python", "name": "Python", "field": "skills", "kind": "MULTI_CHOICE", "weight": 100,
                 "expected": ["Python"], "justification": "Python obrigatório", "mandatory": True}

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            return SimpleNamespace(raise_for_status=lambda: None,
                json=lambda: {"message": {"content": json.dumps({"criteria": [criterion]})}})

    monkeypatch.setattr(matching.httpx, "Client", FakeClient)
    vacancy = SimpleNamespace(description="Python obrigatório para a função.")
    assert matching.suggest_vacancy_criteria(vacancy)["criteria"][0]["field"] == "skills"
    vacancy.description = "Atividades de desenvolvimento de software."
    vacancy.details = {"requirements": "Python obrigatório para a função."}
    assert matching.suggest_vacancy_criteria(vacancy)["criteria"][0]["justification"] == "Python obrigatório"
    criterion["justification"] = "Exigência inventada"
    with pytest.raises(DomainError):
        matching.suggest_vacancy_criteria(vacancy)


def test_curriculum_without_linked_document_is_not_scored(monkeypatch):
    from app.services import curriculum_matching as matching
    config = SimpleNamespace(resume_ai_enabled=True, resume_ai_url="http://resume-ai:11434")
    monkeypatch.setattr(matching, "settings", lambda: config)
    with pytest.raises(DomainError, match="Nenhum currículo vinculado"):
        matching.analyze_curriculum(None, SimpleNamespace(cv_id=None), None, None)
