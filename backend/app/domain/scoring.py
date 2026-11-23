"""Pure deterministic scoring; only allowlisted professional facts and formulas."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.errors import DomainError

ALLOWED_FIELDS = {
    "experience_years",
    "education_level",
    "certifications",
    "skills",
    "languages",
    "availability",
    "shift",
    "travel",
    "relocation",
    "test_score",
    "evaluation_score",
}


def number(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise DomainError("Valor numérico inválido") from exc


class Criterion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    name: str = Field(min_length=2, max_length=180)
    field: str
    category: str = "OBJECTIVE"
    kind: Literal[
        "BOOLEAN",
        "NUMBER_MIN",
        "NUMBER_RANGE",
        "SINGLE_CHOICE",
        "MULTI_CHOICE",
        "LEVEL",
        "EXACT",
        "CUSTOM_FORMULA",
    ]
    weight: float = Field(ge=0, le=100, allow_inf_nan=False)
    expected: Any
    mandatory: bool = False
    knockout: bool = False
    justification: str = Field(min_length=3, max_length=2000)
    not_applicable: bool = False

    @model_validator(mode="after")
    def validate_rule(self):
        if self.field not in ALLOWED_FIELDS:
            raise ValueError(
                "Campo não autorizado para aderência; atributos sensíveis são proibidos"
            )
        if self.kind in {"NUMBER_MIN", "LEVEL"} and number(self.expected) <= 0:
            raise ValueError("Valor esperado deve ser positivo")
        if self.kind == "NUMBER_RANGE":
            if not isinstance(self.expected, list) or len(self.expected) != 2:
                raise ValueError("Informe limite mínimo e máximo")
            if number(self.expected[0]) < 0 or number(self.expected[1]) < number(self.expected[0]):
                raise ValueError("Intervalo inválido")
        if self.kind == "MULTI_CHOICE" and (
            not isinstance(self.expected, list) or not self.expected
        ):
            raise ValueError("Informe escolhas esperadas")
        if self.kind == "BOOLEAN" and not isinstance(self.expected, bool):
            raise ValueError("Informe verdadeiro ou falso")
        if self.kind == "CUSTOM_FORMULA" and self.expected not in {"CAPPED_PERCENT", "BINARY_PASS"}:
            raise ValueError("Fórmula não aprovada")
        return self


def validate_criteria(criteria: list[dict[str, Any]]) -> list[Criterion]:
    parsed = [Criterion.model_validate(item) for item in criteria]
    if not parsed or len(parsed) > 100:
        raise DomainError("Informe entre 1 e 100 critérios")
    if len({item.key for item in parsed}) != len(parsed):
        raise DomainError("Identificadores devem ser únicos")
    if sum(number(item.weight) for item in parsed) != Decimal(100):
        raise DomainError("A soma dos pesos deve ser exatamente 100%")
    return parsed


def normalized(rule: Criterion, value: Any) -> Decimal:
    if value is None:
        return Decimal(0)
    expected = rule.expected
    match rule.kind:
        case "BOOLEAN":
            result = Decimal(100 if type(value) is bool and value == expected else 0)
        case "EXACT" | "SINGLE_CHOICE":
            result = Decimal(100 if comparable(value) == comparable(expected) else 0)
        case "NUMBER_MIN" | "LEVEL":
            result = number(value) / number(expected) * 100
        case "NUMBER_RANGE":
            low, high = map(number, expected)
            result = Decimal(100 if low <= number(value) <= high else 0)
        case "MULTI_CHOICE":
            values = {comparable(item) for item in value} if isinstance(value, list) else set()
            wanted = {comparable(item) for item in expected}
            result = Decimal(len(values & wanted)) / Decimal(len(wanted)) * 100
        case "CUSTOM_FORMULA":
            result = (
                number(value)
                if expected == "CAPPED_PERCENT"
                else Decimal(100 if value is True else 0)
            )
    return min(Decimal(100), max(Decimal(0), result))


def comparable(value):
    """Ignore spelling case, accents and whitespace, without inventing synonyms."""
    if not isinstance(value, str):
        return value
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)).casefold().split())


def calculate(criteria: list[dict[str, Any]], facts: dict[str, Any]) -> dict[str, Any]:
    rules = validate_criteria(criteria)
    weights = sum(number(rule.weight) for rule in rules if not rule.not_applicable)
    items = []
    weighted = Decimal(0)
    knockout = False
    missing = []
    unmet = []
    for rule in rules:
        value = facts.get(rule.field)
        grade = normalized(rule, value) if not rule.not_applicable else Decimal(0)
        contribution = (
            number(rule.weight) * grade / weights
            if weights and not rule.not_applicable
            else Decimal(0)
        )
        weighted += contribution
        failed = not rule.not_applicable and grade < 100
        unknown = value is None
        if not rule.not_applicable and unknown:
            missing.append(rule.name)
        if failed and (rule.mandatory or rule.knockout):
            unmet.append(rule.name)
        knockout = knockout or (rule.knockout and failed)
        items.append(
            {
                "key": rule.key,
                "name": rule.name,
                "field": rule.field,
                "kind": rule.kind,
                "expected": rule.expected,
                "value": value,
                "weight": rule.weight,
                "normalized": float(grade.quantize(Decimal(".0001"), ROUND_HALF_UP)),
                "contribution": float(contribution.quantize(Decimal(".0001"), ROUND_HALF_UP)),
                "mandatory": rule.mandatory,
                "knockout": rule.knockout,
                "met": not failed,
                "applicable": not rule.not_applicable,
                "justification": rule.justification,
                "evidence_status": "NOT_APPLICABLE" if rule.not_applicable else "MISSING" if unknown else "MET" if grade == 100 else "PARTIAL" if grade > 0 else "NOT_MET",
                "missing_choices": [item for item in rule.expected if comparable(item) not in {comparable(v) for v in value}] if rule.kind == "MULTI_CHOICE" and isinstance(value, list) else [],
            }
        )
    return {
        "total": float(weighted.quantize(Decimal(".01"), ROUND_HALF_UP)) if weights else None,
        "applicable_weight": float(weights),
        "knockout": knockout,
        "missing_criteria": missing,
        "unmet_required_criteria": unmet,
        "evidence_coverage": float((sum(number(item["weight"]) for item in items if item["applicable"] and item["value"] is not None) / weights * 100).quantize(Decimal(".01"), ROUND_HALF_UP)) if weights else 0,
        "basis": "Dados profissionais declarados no perfil da candidatura; não equivale à comprovação das informações nem à probabilidade de contratação.",
        "items": items,
        "formula": "Σ(peso × nota normalizada) / Σ(pesos aplicáveis)",
        "status": "NÃO ATENDE REQUISITO OBRIGATÓRIO"
        if knockout or unmet
        else "PENDENTE DE INFORMAÇÕES"
        if missing
        else "CALCULADO"
        if weights
        else "SEM CRITÉRIOS APLICÁVEIS",
    }
