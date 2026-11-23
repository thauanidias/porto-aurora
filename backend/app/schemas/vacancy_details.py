from typing import Literal

from pydantic import Field

from app.schemas.auth import StrictModel


class ApplicationQuestion(StrictModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$", title="Identificador")
    label: str = Field(min_length=3, title="Pergunta")
    kind: Literal["TEXT", "BOOLEAN", "NUMBER", "SINGLE", "MULTIPLE"] = "TEXT"
    required: bool = True
    options: list[str] = Field(default_factory=list, title="Alternativas")


class VacancyDetails(StrictModel):
    structured_workflow: bool = Field(default=False, exclude=True, json_schema_extra={"readOnly": True})
    responsibilities: str = Field(default="", title="Responsabilidades")
    requirements: str = Field(default="", title="Requisitos obrigatórios")
    desirable: str = Field(default="", title="Requisitos desejáveis")
    education: str = Field(default="", title="Formação")
    experience: str = Field(default="", title="Experiência")
    benefits: str = Field(default="", title="Benefícios")
    workload: str = Field(default="", title="Jornada")
    shift: str = Field(default="", title="Turno")
    level: str = Field(default="", title="Nível")
    position: str = Field(default="", title="Cargo")
    salary: float | None = Field(default=None, ge=0, title="Salário")
    salary_range: str = Field(default="", title="Faixa salarial")
    hide_salary: bool = Field(default=True, title="Ocultar salário no portal")
    affirmative: str = Field(default="", title="Informação de vaga afirmativa")
    accessibility: str = Field(default="", title="Acessibilidade")
    notice_id: str = Field(default="", title="Aviso de privacidade")
    questions: list[ApplicationQuestion] = Field(
        default_factory=list, title="Perguntas da candidatura"
    )
    sla_hours: int = Field(default=720, ge=1, le=87600, title="Prazo do processo (horas)")
    allow_override: bool = Field(default=False, title="Permitir exceções justificadas")
    allow_withdrawal_return: bool = Field(default=False, title="Permitir retorno após desistência")
    featured: bool = Field(default=False, title="Destacar no portal")
