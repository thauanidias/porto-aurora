from copy import deepcopy
from datetime import date

import pytest
from pydantic import ValidationError

from app.core.errors import DomainError
from app.core.security import hash_password, verify_password
from app.domain.assessment import grade
from app.domain.rules import health, matches, transition
from app.domain.scoring import calculate
from app.schemas.candidates import Experience, Profile, professional_facts


def criterion(**changes):
    return {
        "key": "experience",
        "name": "Experiência",
        "field": "experience_years",
        "kind": "NUMBER_MIN",
        "weight": 100,
        "expected": 4,
        "justification": "Exigência da função",
        **changes,
    }


@pytest.mark.parametrize("years,expected", [(0, 0), (2, 50), (4, 100), (8, 100), (-2, 0)])
def test_score_bounds(years, expected):
    assert calculate([criterion()], {"experience_years": years})["total"] == expected


def test_weighting_and_reproducibility():
    criteria = [
        criterion(weight=25),
        criterion(key="skill", field="skills", kind="MULTI_CHOICE", expected=["A", "B"], weight=75),
    ]
    facts = {"experience_years": 4, "skills": ["A"]}
    result = calculate(criteria, facts)
    assert result["total"] == 62.5
    assert sum(item["contribution"] for item in result["items"]) == 62.5
    assert result == calculate(deepcopy(criteria), deepcopy(facts))


def test_not_applicable_and_missing():
    result = calculate(
        [criterion(weight=50), criterion(key="other", weight=50, not_applicable=True)], {}
    )
    assert result["total"] == 0
    assert result["applicable_weight"] == 50
    assert calculate([criterion(not_applicable=True)], {})["total"] is None


def test_knockout_does_not_change_score():
    result = calculate([criterion(knockout=True)], {"experience_years": 2})
    assert result["knockout"] is True
    assert result["total"] == 50


def test_required_minimum_is_not_met_by_partial_score():
    result = calculate([criterion(mandatory=True)], {"experience_years": 2})
    assert result["total"] == 50
    assert result["unmet_required_criteria"]
    assert result["status"] == "NÃO ATENDE REQUISITO OBRIGATÓRIO"
    assert result["items"][0]["evidence_status"] == "PARTIAL"


def test_spelling_normalization_does_not_invent_skills_or_inflate_duplicates():
    rules = [criterion(field="skills", kind="MULTI_CHOICE", expected=["Gestão de equipes", "Redes"])]
    result = calculate(rules, {"skills": ["  GESTAO DE EQUIPES  ", "Gestão de equipes", "Windows"]})
    assert result["total"] == 50
    assert result["items"][0]["missing_choices"] == ["Redes"]


def test_missing_evidence_is_explicit_and_stays_in_denominator():
    result = calculate([criterion()], {})
    assert result["total"] == 0
    assert result["evidence_coverage"] == 0
    assert result["missing_criteria"]
    assert result["status"] == "PENDENTE DE INFORMAÇÕES"


@pytest.mark.parametrize("field", ["race", "gender", "age", "pcd", "religion", "name", "city"])
def test_sensitive_fields_rejected(field):
    with pytest.raises(ValidationError):
        calculate([criterion(field=field)], {field: "value"})


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "hello"])
def test_non_finite_values_rejected(value):
    with pytest.raises(DomainError):
        calculate([criterion()], {"experience_years": value})


def test_weights_must_sum_to_100():
    with pytest.raises(DomainError):
        calculate([criterion(weight=99)], {})


def test_arbitrary_formula_rejected():
    with pytest.raises(ValidationError):
        calculate([criterion(kind="CUSTOM_FORMULA", expected="__import__('os')")], {})


def test_objective_and_manual_grading():
    questions = [
        {
            "key": "one",
            "text": "Escolha a alternativa correta",
            "kind": "SINGLE",
            "options": ["A", "B"],
            "correct": "A",
            "weight": 1,
        },
        {"key": "two", "text": "Descreva uma solução", "kind": "TEXT", "weight": 3},
    ]
    result = grade(questions, {"one": "A", "two": "Resposta"})
    assert result["score"] is None and result["status"] == "PENDING_REVIEW"
    result = grade(
        questions,
        {"one": "A", "two": "Resposta"},
        {"two": {"score": 50, "comment": "Atende parcialmente"}},
    )
    assert result["score"] == 62.5


def test_boolean_not_equal_to_integer():
    result = grade(
        [{"key": "q", "text": "Verdadeiro ou falso", "kind": "BOOLEAN", "correct": True}], {"q": 1}
    )
    assert result["score"] == 0


def test_status_transition_enforced():
    transition("DRAFT", "PENDING_APPROVAL")
    with pytest.raises(DomainError):
        transition("DRAFT", "PUBLISHED")


def test_sla_and_filter_rules():
    assert health(100, 80, 5)["status"] == "CRÍTICO"
    assert health(20, 80, 5)["status"] == "SAUDÁVEL"
    assert matches(
        {
            "and": [
                {"field": "state", "op": "eq", "value": "PA"},
                {"field": "experience_years", "op": "gte", "value": 2},
            ]
        },
        {"state": "PA", "experience_years": 3},
    )
    with pytest.raises(DomainError):
        matches({"field": "gender", "op": "eq", "value": "X"}, {})


def test_overlapping_experience_is_not_double_counted():
    experience = Experience(
        company="Empresa", position="Analista", start=date(2020, 1, 1), end=date(2022, 1, 1)
    )
    profile = Profile(experiences=[experience, experience])
    assert professional_facts(profile)["experience_years"] == 2


def test_password_is_argon2_and_verifies():
    hashed = hash_password("Testing-passphrase-42")
    assert hashed.startswith("$argon2id$")
    assert verify_password("Testing-passphrase-42", hashed)
    assert not verify_password("incorrect", hashed)
