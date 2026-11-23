from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.compatibility import compatibility_summary


def model():
    return SimpleNamespace(id="model", number=2, criteria=[{"not_applicable": False}])


def score(**changes):
    return SimpleNamespace(**({"model_id": "model", "total": 75, "knockout": False,
        "created_at": datetime.now(timezone.utc),
        "breakdown": {"items": [{"name": "Experiência", "applicable": True, "value": 3}],
                      "pending_components": []}} | changes))


def test_percentage_uses_recorded_score_and_detects_missing_evidence():
    assert compatibility_summary(score(), model())["percentage"] == 75
    assert compatibility_summary(score(), model())["status"] == "CALCULATED"
    missing = score(breakdown={"items": [{"name": "Experiência", "applicable": True, "value": None}]})
    assert compatibility_summary(missing, model())["status"] == "PENDING"
    assert compatibility_summary(missing, model())["missing_criteria"] == ["Experiência"]


def test_no_percentage_without_valid_model_or_with_sealed_evaluations():
    assert compatibility_summary(score(), model(), True) == {"percentage": None, "status": "SEALED", "items": []}
    assert compatibility_summary(score(model_id="old"), model())["percentage"] is None
    assert compatibility_summary(None, model())["status"] == "OUTDATED"
    assert compatibility_summary(score(), None)["percentage"] is None
    manual = model()
    manual.criteria = [{"not_applicable": True}]
    assert compatibility_summary(score(total=0), manual)["status"] == "NOT_CONFIGURED"


def test_pending_components_and_knockout_are_explicit():
    summary = compatibility_summary(score(knockout=True, breakdown={"items": [], "pending_components": ["RH"]}), model())
    assert summary["status"] == "PENDING"
    assert summary["knockout"] is True
    assert summary["pending_components"] == ["RH"]
