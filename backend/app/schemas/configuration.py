from typing import Any, Literal

from pydantic import Field, model_validator

from app.domain.scoring import Criterion, validate_criteria
from app.schemas.auth import StrictModel
from app.schemas.recruitment import StageInput
from app.schemas.vacancy_details import VacancyDetails


class WorkflowStep(StrictModel):
    name: str = Field(min_length=2, title="Etapa")
    approver_id: str = Field(title="Aprovador")
    delegate_id: str | None = Field(default=None, title="Substituto")
    sla_hours: int = Field(default=48, ge=1, le=8760, title="Prazo em horas")
    conditions: dict[str, Any] = Field(default_factory=dict, title="Condições")


class Workflow(StrictModel):
    target: Literal["REQUEST", "VACANCY", "OFFER"] = "VACANCY"
    steps: list[WorkflowStep] = Field(min_length=1, max_length=20, title="Etapas")


class PrivacyNotice(StrictModel):
    text: str = Field(min_length=30, max_length=50000, title="Texto do aviso")
    purpose: str = Field(min_length=3, title="Finalidade")
    contact: str = Field(min_length=3, title="Contato de privacidade")
    talent_months: int = Field(
        default=12, ge=1, le=120, title="Validade do consentimento para banco de talentos (meses)"
    )


class NamedCatalog(StrictModel):
    description: str = Field(default="", title="Descrição")


class PipelineTemplate(StrictModel):
    stages: list[StageInput] = Field(min_length=1, max_length=40, title="Etapas")


class VacancyTemplate(StrictModel):
    description: str = Field(min_length=30, title="Descrição da oportunidade")
    details: VacancyDetails
    stages: list[StageInput] = Field(min_length=1, max_length=40, title="Etapas")
    criteria: list[Criterion] = Field(min_length=1, max_length=50, title="Critérios")

    @model_validator(mode="after")
    def valid_model(self):
        validate_criteria([c.model_dump() for c in self.criteria])
        if len({s.position for s in self.stages}) != len(self.stages):
            raise ValueError("Posições de etapas devem ser únicas")
        return self


class MessageTemplate(StrictModel):
    subject: str = Field(min_length=2, title="Assunto")
    body: str = Field(min_length=5, title="Mensagem")


class Retention(StrictModel):
    target: Literal["TALENT", "CLOSED_APPLICATION", "ADMISSION"]
    months: int = Field(ge=1, le=1200, title="Prazo em meses")
    action: Literal["REVIEW", "ANONYMIZE"] = "REVIEW"


class Brand(StrictModel):
    platform_name: str = Field(default="Porto Aurora Talentos", title="Nome da plataforma")
    organization_name: str = Field(
        default="Porto Aurora", title="Organização"
    )
    description: str = Field(default="", title="Apresentação institucional")
    contact: str = Field(default="", title="Contato")
    brand_color: str = Field(
        default="#145c67", pattern=r"^#[0-9a-fA-F]{6}$", title="Cor institucional"
    )
    timezone: str = Field(default="America/Belem", title="Fuso horário")
    logo_url: str = Field(default="", title="Logo (caminho local público)")
    favicon_url: str = Field(default="", title="Favicon (caminho local público)")
    hero_url: str = Field(default="", title="Imagem institucional (caminho local público)")

    @model_validator(mode="after")
    def safe_assets(self):
        from zoneinfo import ZoneInfo

        ZoneInfo(self.timezone)
        for value in (self.logo_url, self.hero_url, self.favicon_url):
            if value and (
                not value.startswith("/assets/") or ".." in value or value.startswith("//")
            ):
                raise ValueError("Utilize um asset local em /assets/")
        return self


class ScorecardCriterion(StrictModel):
    key: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,60}$", title="Identificador")
    name: str = Field(min_length=2, title="Critério")
    min_value: int = Field(default=1, ge=0, title="Nota mínima")
    max_value: int = Field(default=5, le=100, title="Nota máxima")
    weight: float = Field(default=1, gt=0, le=100, title="Peso")
    extreme_comment: bool = Field(default=True, title="Exigir comentário nas notas extremas")

    @model_validator(mode="after")
    def valid_scale(self):
        if self.max_value <= self.min_value:
            raise ValueError("Nota máxima deve ser maior que a mínima")
        return self


class Scorecard(StrictModel):
    category: Literal["RH", "MANAGER", "TECHNICAL"] = "RH"
    independent: bool = Field(default=True, title="Avaliação independente")
    criteria: list[ScorecardCriterion] = Field(min_length=1, max_length=50, title="Critérios")


class InterviewTemplate(StrictModel):
    questions: list[str] = Field(min_length=1, title="Perguntas")
    scorecard_id: str = Field(default="", title="Ficha de avaliação")


class Checklist(StrictModel):
    items: list[str] = Field(
        min_length=1, max_length=100, title="Documentos e verificações obrigatórias"
    )


class Survey(StrictModel):
    questions: list[str] = Field(min_length=1, max_length=20, title="Perguntas")
    nps: bool = Field(default=True, title="Solicitar nota de 0 a 10")


class Automation(StrictModel):
    event: Literal[
        "application.created",
        "application.stage_changed",
        "test.completed",
        "test.graded",
        "interview.created",
        "interview.completed",
        "application.decision",
        "vacancy.status_changed",
        "vacancy.sla_near",
        "offer.accepted",
    ]
    conditions: dict[str, Any] = Field(default_factory=dict)
    action: Literal["NOTIFY", "TASK", "TAG", "EMAIL", "ASSIGN", "MOVE"]
    target_id: str = ""
    text: str = Field(min_length=2, max_length=1000)
    approved: bool = False


class Report(StrictModel):
    entity: Literal["vacancies", "applications", "interviews", "offers", "tasks", "audit"]
    columns: list[str] = Field(min_length=1, max_length=20)
    filters: dict[str, str] = Field(default_factory=dict)
    order_by: str = "created_at"


class DocumentType(StrictModel):
    description: str = ""
    phase: Literal["APPLICATION", "PRE_ADMISSION"] = "PRE_ADMISSION"
    required: bool = True


SCHEMAS: dict[str, type[StrictModel]] = {
    "workflows": Workflow,
    "vacancy-templates": VacancyTemplate,
    "privacy-notices": PrivacyNotice,
    "pipelines": PipelineTemplate,
    "message-templates": MessageTemplate,
    "retention-policies": Retention,
    "branding": Brand,
    "scorecards": Scorecard,
    "interview-templates": InterviewTemplate,
    "checklists": Checklist,
    "surveys": Survey,
    "automations": Automation,
    "saved-reports": Report,
    "document-types": DocumentType,
    "skills": NamedCatalog,
    "tags": NamedCatalog,
    "closure-reasons": NamedCatalog,
}
