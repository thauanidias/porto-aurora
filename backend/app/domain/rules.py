from typing import Any

from app.core.errors import DomainError

FILTER_FIELDS = {
    "city",
    "state",
    "source",
    "experience_years",
    "education_level",
    "certifications",
    "skills",
    "availability",
    "shift",
}


def matches(rule: dict[str, Any], facts: dict[str, Any], depth: int = 0) -> bool:
    if depth > 5:
        raise DomainError("Filtro excede profundidade máxima")
    if not rule:
        return True
    if "and" in rule or "or" in rule:
        key = "and" if "and" in rule else "or"
        children = rule[key]
        if not isinstance(children, list) or not 1 <= len(children) <= 20:
            raise DomainError("Filtro deve possuir entre 1 e 20 condições")
        results = [matches(child, facts, depth + 1) for child in children]
        return all(results) if key == "and" else any(results)
    field, op, value = rule.get("field"), rule.get("op"), rule.get("value")
    if field not in FILTER_FIELDS | {
        "org_unit_id",
        "quantity",
        "position",
        "request_type",
        "stage_id",
        "test_score",
        "event_status",
        "status",
    }:
        raise DomainError("Campo de filtro não autorizado")
    actual = facts.get(field)
    if op == "eq":
        return actual == value
    if op == "in":
        return actual in value if isinstance(value, list) else False
    if op == "contains":
        return value in actual if isinstance(actual, (str, list)) else False
    if op in {"gte", "lte"}:
        try:
            return (
                float(str(actual)) >= float(str(value))
                if op == "gte"
                else float(str(actual)) <= float(str(value))
            )
        except (ValueError, TypeError):
            return False
    raise DomainError("Operador de filtro inválido")


VACANCY_TRANSITIONS = {
    "DRAFT": {"PENDING_APPROVAL", "CANCELED"},
    "PENDING_APPROVAL": {"APPROVED", "DRAFT", "CANCELED"},
    "APPROVED": {"PUBLISHED", "CANCELED"},
    "PUBLISHED": {"PAUSED", "CLOSED", "CANCELED"},
    "PAUSED": {"PUBLISHED", "CLOSED", "CANCELED"},
    "CLOSED": {"DRAFT", "ARCHIVED"},
    "CANCELED": {"ARCHIVED"},
    "ARCHIVED": set(),
}


def transition(current: str, target: str) -> None:
    if target not in VACANCY_TRANSITIONS.get(current, set()):
        raise DomainError("Mudança de status não permitida", 409, "INVALID_TRANSITION")


def health(elapsed_hours: float, sla_hours: int, candidate_count: int) -> dict[str, Any]:
    ratio = elapsed_hours / max(1, sla_hours)
    reasons = []
    if ratio >= 1:
        reasons.append("Prazo do processo excedido")
    elif ratio >= 0.75:
        reasons.append("Prazo do processo próximo do limite")
    if candidate_count == 0:
        reasons.append("Nenhuma candidatura recebida")
    return {
        "status": "CRÍTICO" if ratio >= 1 else "ATENÇÃO" if reasons else "SAUDÁVEL",
        "reasons": reasons,
    }
