from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.domain.scoring import Criterion
from app.schemas.auth import StrictModel
from app.schemas.vacancy_details import VacancyDetails


class Versioned(StrictModel):
    version: int = Field(ge=1)


class RequestInput(StrictModel):
    request_workflow_id: str | None = Field(default=None, title="Fluxo de análise do RH", description="Opcional quando existe apenas um fluxo ativo de solicitações.")
    title: str = Field(min_length=3, max_length=180)
    org_unit_id: str
    quantity: int = Field(ge=1, le=1000)
    reason: str = Field(min_length=3, title="Motivo da solicitação")
    request_type: Literal["NEW", "REPLACEMENT"]
    justification: str = Field(min_length=10)
    position: str = Field(min_length=2)
    cost_center: str
    urgency: Literal["NORMAL", "HIGH", "CRITICAL"] = "NORMAL"
    desired_date: str
    replaced_employee: str = ""


class VacancyInput(StrictModel):
    vacancy_template_id: str | None = None
    publish_on_save: bool = Field(
        default=False,
        title="Publicar ao salvar",
        description="Vagas externas e não confidenciais aparecem no portal público após salvar.",
    )
    title: str = Field(min_length=3, max_length=180)
    org_unit_id: str
    recruiter_id: str
    manager_id: str
    quantity: int = Field(ge=1, le=1000)
    audience: Literal["EXTERNAL", "INTERNAL", "BOTH"] = "EXTERNAL"
    confidential: bool = False
    blind: bool = False
    description: str = ""
    city: str = ""
    state: str = Field(default="", max_length=2)
    modality: Literal["PRESENCIAL", "HIBRIDO", "REMOTO"] = "PRESENCIAL"
    contract_type: str = "CLT"
    deadline: datetime | None = None
    details: VacancyDetails = Field(default_factory=VacancyDetails)

    @field_validator("deadline")
    @classmethod
    def timezone_required(cls, value):
        if value and value.tzinfo is None:
            raise ValueError("Informe data com fuso horário")
        return value


class VacancyUpdate(VacancyInput):
    version: int = Field(ge=1)


class StatusInput(Versioned):
    status: str
    reason: str = ""
    workflow_id: str | None = None


class ApprovalInput(Versioned):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str = ""

    @model_validator(mode="after")
    def reason_required(self):
        if self.decision == "REJECTED" and len(self.comment.strip()) < 5:
            raise ValueError("Reprovação exige justificativa")
        return self


class StageInput(StrictModel):
    name: str = Field(min_length=2, max_length=180)
    position: int = Field(ge=0)
    kind: Literal["SCREENING", "TEST", "INTERVIEW", "FINALIST", "OFFER", "HIRED"]
    candidate_phase: Literal["REGISTER", "RECRUITMENT", "SELECTION", "FORM", "INTERVIEW", "TEST", "ADMISSION"] | None = Field(
        default=None, title="Atividades liberadas ao candidato", description="Sem configuração, a primeira etapa libera recrutamento, a triagem libera seleção, entrevistas e testes são liberados separadamente.")
    required: bool = False
    reveal_identity: bool = False
    sla_hours: int = Field(default=72, ge=1, le=8760)
    rules: dict[str, Any] = Field(default_factory=dict)


class PipelineInput(Versioned):
    stages: list[StageInput] = Field(min_length=1, max_length=40)


class ScoreInput(StrictModel):
    criteria: list[Criterion]
    composition: dict[str, float] = Field(default_factory=lambda: {"OBJECTIVE": 100.0})
    bands: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = Field(min_length=5)


class ApplicationInput(StrictModel):
    vacancy_id: str
    notice_id: str = ""
    consent: bool = False
    enrollment: bool = False
    answers: dict[str, Any] = Field(default_factory=dict)
    cv_id: str | None = None
    invitation_token: str | None = None
    utm: dict[str, str] = Field(default_factory=dict)


class MoveInput(Versioned):
    stage_id: str
    reason: str = ""
    override: bool = False


class DecisionInput(Versioned):
    decision: Literal["SELECTED", "RESERVE", "REJECTED", "WITHDRAWN", "HIRED"]
    reason: str = ""
    override: bool = False
    send_rejection_email: bool = False
    rejection_email_body: str = Field(default="", max_length=10000)
