from typing import Any, Literal

from pydantic import Field, model_validator

from app.core.errors import DomainError
from app.schemas.auth import StrictModel


class Question(StrictModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$")
    text: str = Field(min_length=3, max_length=10000)
    kind: Literal["SINGLE", "BOOLEAN", "MULTIPLE", "NUMBER", "TEXT", "ESSAY", "PRACTICAL", "UPLOAD"]
    options: list[str] = Field(default_factory=list, max_length=30)
    correct: Any = None
    tolerance: float = Field(default=0, ge=0, allow_inf_nan=False)
    weight: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    category: str = ""
    difficulty: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_answer(self):
        if self.kind in {"SINGLE", "MULTIPLE"}:
            if len(self.options) < 2:
                raise ValueError("Informe pelo menos duas alternativas")
            answers = self.correct if self.kind == "MULTIPLE" else [self.correct]
            if (
                not isinstance(answers, list)
                or not answers
                or any(answer not in self.options for answer in answers)
            ):
                raise ValueError("Gabarito deve corresponder às alternativas")
        if self.kind == "BOOLEAN" and not isinstance(self.correct, bool):
            raise ValueError("Informe gabarito verdadeiro ou falso")
        if self.kind == "NUMBER":
            from app.domain.scoring import number

            number(self.correct)
        return self


def grade(questions: list[dict], answers: dict, manual: dict | None = None):
    from app.domain.scoring import number

    manual = manual or {}
    items: dict[str, dict[str, Any]] = {}
    weighted = 0.0
    weights = 0.0
    pending = False
    for raw in questions:
        question = Question.model_validate(raw)
        value = answers.get(question.key)
        score = 0.0
        comment = ""
        if question.kind in {"TEXT", "ESSAY", "PRACTICAL", "UPLOAD"}:
            entry = manual.get(question.key)
            if entry is None:
                pending = True
                items[question.key] = {"pending": True}
                continue
            score = float(number(entry["score"]))
            comment = str(entry.get("comment", ""))
            if not 0 <= score <= 100 or len(comment) < 3:
                raise DomainError("Correção humana exige nota de 0 a 100 e comentário.")
        elif question.kind == "MULTIPLE":
            score = (
                100.0 if isinstance(value, list) and set(value) == set(question.correct) else 0.0
            )
        elif question.kind == "NUMBER":
            try:
                score = (
                    100.0
                    if abs(number(value) - number(question.correct)) <= number(question.tolerance)
                    else 0.0
                )
            except DomainError:
                score = 0.0
        elif question.kind == "BOOLEAN":
            score = 100.0 if type(value) is bool and value == question.correct else 0.0
        else:
            score = 100.0 if value == question.correct else 0.0
        weighted += score * question.weight
        weights += question.weight
        items[question.key] = {"score": score, "weight": question.weight, "comment": comment}
    return {
        "items": items,
        "score": round(weighted / weights, 2) if weights and not pending else None,
        "status": "PENDING_REVIEW" if pending else "GRADED",
    }
