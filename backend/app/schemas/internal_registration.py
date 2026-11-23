"""Employee-editable fields from FORM-PPO-RH-002.01, internal selection sheet."""
import base64
from datetime import date as Date
from io import BytesIO

from PIL import Image
from pydantic import Field, field_validator, model_validator

from app.schemas.auth import StrictModel
from app.schemas.selection_registration import (
    TRUTH_DECLARATION,
    Answer,
    BankDetails,
    Declaration,
    Dependent,
    EducationDetails,
    LanguageDetails,
    PersonalDetails,
)


class InternalPersonal(PersonalDetails):
    employee_number: str = Field(default="", max_length=40, title="Matrícula")
    age: int | None = Field(default=None, ge=0, le=130, title="Idade")


class InternalEmployment(StrictModel):
    admission_date: Date | None = Field(default=None, title="Data de admissão no Porto Aurora")
    department: str = Field(default="", max_length=180, title="Área em que trabalha")
    position: str = Field(default="", max_length=180, title="Cargo atual")
    supervisor: str = Field(default="", max_length=180, title="Superior imediato")
    vacation_start: Date | None = Field(default=None, title="Férias programadas — início")
    vacation_end: Date | None = Field(default=None, title="Férias programadas — término")
    flexible_hours: Answer = Field(default="Não informado", title="Tem flexibilidade de horário?")
    hours_restrictions: str = Field(default="", max_length=1000, title="Restrições de horário")
    flexible_weekends: Answer = Field(default="Não informado", title="Tem flexibilidade no final de semana?")
    weekend_restrictions: str = Field(default="", max_length=1000, title="Restrições no final de semana")
    related_employee: Answer = Field(default="Não informado", title="Possui parentesco com colaborador do Porto Aurora?")
    relative_name: str = Field(default="", max_length=180, title="Nome do colaborador com parentesco")
    relationship: str = Field(default="", max_length=80, title="Grau de parentesco")
    word: bool = Field(default=False, title="Conhecimento em Word")
    excel: bool = Field(default=False, title="Conhecimento em Excel")
    powerpoint: bool = Field(default=False, title="Conhecimento em PowerPoint")
    power_bi: bool = Field(default=False, title="Conhecimento em Power BI")
    access: bool = Field(default=False, title="Conhecimento em Access")
    other_systems: str = Field(default="", max_length=1000, title="Outros sistemas")

    @model_validator(mode="after")
    def vacation_period(self):
        if self.vacation_start and self.vacation_end and self.vacation_end < self.vacation_start:
            raise ValueError("O término das férias não pode ser anterior ao início.")
        return self


class Transport(StrictModel):
    daily_quantity: int | None = Field(default=None, ge=0, le=100, title="Quantidade diária")
    transport: str = Field(default="", max_length=180, title="Meio de transporte")
    fare: float | None = Field(default=None, ge=0, le=100000, title="Tarifa (R$)")


class UnionContribution(StrictModel):
    paid: Answer = Field(default="Não informado", title="Pagou a contribuição sindical do ano em exercício?")
    entity_name: str = Field(default="", max_length=180, title="Nome da entidade sindical")
    amount: float | None = Field(default=None, ge=0, le=1000000, title="Valor (R$)")
    cnpj: str = Field(default="", max_length=18, title="CNPJ da entidade sindical")
    entity_code: str = Field(default="", max_length=80, title="Código da entidade sindical")


class InternalDeclaration(Declaration):
    signature_name: str = Field(default="", max_length=180, title="Nome completo do signatário")
    signature_image: str = Field(default="", max_length=250000, title="Assinatura eletrônica", json_schema_extra={"format": "signature"})

    @field_validator("signature_image")
    @classmethod
    def valid_signature(cls, value):
        if not value:
            return value
        try:
            if not value.startswith("data:image/png;base64,"):
                raise ValueError()
            content = base64.b64decode(value.split(",", 1)[1], validate=True)
            with Image.open(BytesIO(content)) as image:
                if image.format != "PNG" or image.width > 1800 or image.height > 600 or image.width < 10 or image.height < 10:
                    raise ValueError()
                image.load()
                background = Image.new("RGBA", image.size, "white")
                background.alpha_composite(image.convert("RGBA"))
                if not any(background.convert("L").histogram()[:241]):
                    raise ValueError()
        except Exception as exc:
            raise ValueError("Registre uma assinatura válida antes de confirmar as declarações.") from exc
        return value

    @model_validator(mode="after")
    def signed_confirmation(self):
        if self.accepted and not self.signature_image:
            raise ValueError("Assine a ficha antes de confirmar as declarações.")
        return self


class InternalRegistration(StrictModel):
    desired_position: str = Field(default="", max_length=180, title="Cargo pretendido")
    personal: InternalPersonal = Field(default_factory=InternalPersonal, title="Dados pessoais")
    bank: BankDetails = Field(default_factory=BankDetails, title="Dados bancários", description="Informe conta corrente, conforme a ficha original. Não informe conta poupança.")
    dependents: list[Dependent] = Field(default_factory=list, max_length=6, title="Dependentes", description="Adicione somente os dependentes aplicáveis, até seis. Se não tiverem CPF, informe o CPF do responsável.")
    employment: InternalEmployment = Field(default_factory=InternalEmployment, title="Informações profissionais no Porto Aurora")
    languages: LanguageDetails = Field(default_factory=LanguageDetails, title="Idiomas")
    education: EducationDetails = Field(default_factory=EducationDetails, title="Grau de instrução")
    motivation: str = Field(default="", max_length=10000, title="Motivo de interesse na vaga", description="Descreva suas motivações, experiências e como a vaga se alinha aos seus objetivos de carreira.")
    transport: list[Transport] = Field(default_factory=list, max_length=3, title="Vale-transporte")
    union: UnionContribution = Field(default_factory=UnionContribution, title="Contribuição sindical", description="CNPJ e código da entidade: campos previstos para categorias diferenciadas na ficha original.")
    declaration: InternalDeclaration = Field(default_factory=InternalDeclaration, title="Declarações, local, data e assinatura", description=TRUTH_DECLARATION + "\n\nDeclaro ainda ter ciência de que todas as informações aqui prestadas que porventura sofram alguma alteração deverão por mim ser comunicadas à empresa imediatamente, sob pena de responsabilidade.")


class InternalRegistrationInput(StrictModel):
    data: InternalRegistration
    version: int = Field(ge=0)
