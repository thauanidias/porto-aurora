import test_candidate_journey
from test_candidate_journey import enroll
from test_integration import call

from app.models import Application

journey_owner = test_candidate_journey.journey_owner

def test_vacancy_percentages_and_recalculation(client, db, actors, journey_owner):
    owner, vacancy, admin, _ = journey_owner
    application = enroll(client, owner, vacancy)
    path = "/applications?vacancy_id=" + vacancy["id"]
    assert call(client, "get", path, admin)["items"][0]["compatibility"]["percentage"] is None
    assert "compatibility" not in call(client, "get", path, owner)["items"][0]
    call(client, "post", "/vacancies/" + vacancy["id"] + "/scoring-models", admin, {
        "criteria": [{"key": "experience", "name": "Experiência profissional", "field": "experience_years",
                      "kind": "NUMBER_MIN", "weight": 100, "expected": 4, "justification": "Requisito da vaga"}],
        "composition": {"OBJECTIVE": 100}, "bands": [], "reason": "Compatibilidade profissional para comparação",
    }, 201)
    assert call(client, "get", path, admin)["items"][0]["compatibility"]["status"] == "OUTDATED"
    db.get(Application, application["id"]).profile_snapshot = {"facts": {"experience_years": 2}}
    db.commit()
    recalculate = "/vacancies/" + vacancy["id"] + "/recalculate-compatibility"
    result = call(client, "post", recalculate, admin, {"reason": "Atualizar porcentagens conforme requisitos"})
    assert result["updated"] == 1
    summary = call(client, "get", path, admin)["items"][0]["compatibility"]
    assert summary["percentage"] == 50
    assert summary["status"] == "CALCULATED"
    assert client.post("/api/v1" + recalculate, headers=owner,
                       json={"reason": "Tentativa sem permissão"}).status_code == 403
