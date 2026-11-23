"""Digital version of FORM-PPO-RH-002.02, kept outside scoring/profile facts."""

from datetime import date as Date
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.auth import StrictModel
from app.schemas.signature import validate_signature

Answer = Literal["Não informado", "Sim", "Não"]
Level = Literal["Não informado", "Básico", "Intermediário", "Avançado", "Fluente"]
Completion = Literal["Não informado", "Completo", "Incompleto"]

TRUTH_DECLARATION = (
    "Declaro que as informações acima são verdadeiras, podendo a empresa averiguá-las "
    "pelos meios legais que julgar convenientes."
)
UPDATE_DECLARATION = (
    "Declaro ainda ter a ciência de que, numa eventual contratação, todas as informações "
    "aqui prestadas que porventura sofram alguma alteração, deverão por mim ser comunicadas "
    "à empresa IMEDIATAMENTE, sob pena de responsabilidade."
)


class Address(StrictModel):
    street: str = Field(default="", max_length=200, title="Endereço")
    number: str = Field(default="", max_length=30, title="Número")
    complement: str = Field(default="", max_length=120, title="Complemento")
    neighborhood: str = Field(default="", max_length=120, title="Bairro")
    city: str = Field(default="", max_length=120, title="Cidade")
    state: str = Field(default="", max_length=2, title="UF")
    postal_code: str = Field(default="", max_length=10, title="CEP")


class PersonalDetails(StrictModel):
    name: str = Field(default="", max_length=180, title="Nome completo")
    birth_date: Date | None = Field(default=None, title="Data de nascimento")
    marital_status: Literal[
        "Não informado", "Solteiro", "Casado", "Viúvo", "Marital", "Separado", "Divorciado"
    ] = Field(default="Não informado", title="Estado civil")
    address: Address = Field(default_factory=Address, title="Endereço residencial")
    mobile: str = Field(default="", max_length=30, title="Celular com DDD")
    email: EmailStr | None = Field(default=None, title="E-mail")


class IdentityDocuments(StrictModel):
    cpf: str = Field(default="", max_length=14, title="CPF")
    cnh: str = Field(default="", max_length=30, title="CNH — número")
    cnh_category: str = Field(default="", max_length=10, title="Categoria da CNH")
    rg: str = Field(default="", max_length=30, title="RG")
    issuing_authority: str = Field(default="", max_length=120, title="Órgão emissor do RG")
    issuing_state: str = Field(default="", max_length=2, title="Estado emissor do RG")
    issued_on: Date | None = Field(default=None, title="Data de expedição do RG")
    professional_council: str = Field(
        default="", max_length=120, title="Órgão de classe (OGMO, OAB, CREA etc.)"
    )
    council_region: str = Field(default="", max_length=80, title="Região do órgão de classe")
    council_registration: str = Field(default="", max_length=80, title="Número de inscrição")


class ForeignerDetails(StrictModel):
    naturalized: Answer = Field(default="Não informado", title="Naturalizado?")
    visa: Literal["Não informado", "Temporário", "Definitivo"] = Field(
        default="Não informado", title="Tipo de visto"
    )
    rne: str = Field(default="", max_length=40, title="RNE")
    arrival_date: Date | None = Field(default=None, title="Data de chegada ao Brasil")


class BankDetails(StrictModel):
    bank_name: str = Field(default="Bradesco", max_length=100, title="Banco")
    bank_number: str = Field(default="", max_length=10, title="Número do banco")
    branch: str = Field(default="", max_length=20, title="Agência")
    checking_account: str = Field(default="", max_length=30, title="Conta corrente — número")


class Dependent(StrictModel):
    name: str = Field(default="", max_length=180, title="Nome do dependente")
    relationship: str = Field(default="", max_length=80, title="Parentesco")
    mother_name: str = Field(default="", max_length=180, title="Nome da mãe do dependente")
    mother_cpf: str = Field(default="", max_length=14, title="CPF da mãe do dependente")
    cns: str = Field(default="", max_length=20, title="Cartão CNS")
    cpf: str = Field(
        default="", max_length=14, title="CPF do dependente ou do responsável",
        description="Caso o dependente não possua CPF, informe o CPF do responsável.",
    )
    rg: str = Field(default="", max_length=30, title="RG do dependente")
    birth_date: Date | None = Field(default=None, title="Data de nascimento do dependente")
    income_tax_dependent: Answer = Field(default="Não informado", title="Dependente no IR?")


class EmploymentDetails(StrictModel):
    company: str = Field(default="", max_length=180, title="Empresa")
    phone: str = Field(default="", max_length=30, title="Telefone da empresa")
    address: Address = Field(default_factory=Address, title="Endereço da empresa")
    initial_position: str = Field(default="", max_length=180, title="Cargo inicial")
    final_position: str = Field(default="", max_length=180, title="Cargo final")
    admission_date: Date | None = Field(default=None, title="Data de admissão")
    departure_date: Date | None = Field(default=None, title="Data de saída")
    last_salary: float | None = Field(default=None, ge=0, le=10000000, title="Último salário (R$)")
    benefits: str = Field(default="", max_length=2000, title="Benefícios")
    reason: str = Field(default="", max_length=2000, title="Motivo da saída")
    supervisor: str = Field(default="", max_length=180, title="Superior imediato")
    description: str = Field(default="", max_length=5000, title="Principais atividades exercidas")

    @model_validator(mode="after")
    def valid_period(self):
        if self.admission_date and self.departure_date and self.departure_date < self.admission_date:
            raise ValueError("A data de saída não pode ser anterior à data de admissão.")
        return self


class LanguageDetails(StrictModel):
    english: Level = Field(default="Não informado", title="Inglês — nível")
    spanish: Level = Field(default="Não informado", title="Espanhol — nível")
    other_language: str = Field(default="", max_length=80, title="Outro idioma")
    other_level: Level = Field(default="Não informado", title="Outro idioma — nível")


class EducationDetails(StrictModel):
    high_school: Completion = Field(default="Não informado", title="Ensino médio")
    technical: Completion = Field(default="Não informado", title="Técnico")
    technical_course: str = Field(default="", max_length=200, title="Curso técnico")
    higher: Completion = Field(default="Não informado", title="Superior")
    higher_course: str = Field(default="", max_length=200, title="Curso superior")
    extension: Completion = Field(default="Não informado", title="Curso de extensão")
    extension_course: str = Field(default="", max_length=200, title="Nome do curso de extensão")
    postgraduate: Completion = Field(default="Não informado", title="Pós-graduação")
    postgraduate_course: str = Field(default="", max_length=200, title="Curso de pós-graduação")
    masters: Completion = Field(default="Não informado", title="Mestrado")
    masters_course: str = Field(default="", max_length=200, title="Curso de mestrado")


class ComplementaryDetails(StrictModel):
    related_employee: Answer = Field(default="Não informado", title="Possui parentesco com colaborador do Porto Aurora?")
    employee_name: str = Field(default="", max_length=180, title="Nome do colaborador")
    relationship: str = Field(default="", max_length=80, title="Grau de parentesco")
    flexible_hours: Answer = Field(default="Não informado", title="Tem flexibilidade de horário?")
    hours_restrictions: str = Field(default="", max_length=1000, title="Restrições de horário")
    flexible_weekends: Answer = Field(default="Não informado", title="Tem flexibilidade no final de semana?")
    weekend_restrictions: str = Field(default="", max_length=1000, title="Restrições no final de semana")
    available_for_travel: Answer = Field(default="Não informado", title="Tem disponibilidade de viajar pela empresa?")
    travel_restrictions: str = Field(default="", max_length=1000, title="Restrições para viagens")
    shirt_size: str = Field(default="", max_length=20, title="Tamanho de uniforme — camisa")
    pants_size: str = Field(default="", max_length=20, title="Tamanho de uniforme — calça")
    boot_size: str = Field(default="", max_length=20, title="Tamanho de uniforme — bota")


class Declaration(StrictModel):
    accepted: bool = Field(default=False, title="Li e confirmo as duas declarações acima")
    place: str = Field(default="", max_length=180, title="Local")
    date: Date | None = Field(default=None, title="Data da declaração")
    signature_name: str = Field(default="", max_length=180, title="Assinatura do candidato — nome completo")

    @model_validator(mode="after")
    def valid_confirmation(self):
        if self.accepted and (not self.place.strip() or not self.date or len(self.signature_name.strip()) < 3):
            raise ValueError("Para confirmar as declarações, informe local, data e nome completo.")
        return self


class ExternalDeclaration(Declaration):
    signature_image: str = Field(default="", max_length=250000, title="Assinatura eletrônica do candidato", json_schema_extra={"format": "signature"})

    @field_validator("signature_image")
    @classmethod
    def valid_signature(cls, value):
        return validate_signature(value)

    @model_validator(mode="after")
    def signed(self):
        if self.accepted and not self.signature_image:
            raise ValueError("Assine a ficha antes de confirmar as declarações.")
        return self


class SelectionRegistration(StrictModel):
    desired_position: str = Field(default="", max_length=180, title="Cargo pretendido")
    personal: PersonalDetails = Field(default_factory=PersonalDetails, title="Dados pessoais")
    documents: IdentityDocuments = Field(default_factory=IdentityDocuments, title="Documentação")
    foreigner: ForeignerDetails = Field(default_factory=ForeignerDetails, title="Estrangeiro")
    bank: BankDetails = Field(
        default_factory=BankDetails, title="Dados bancários",
        description="Informe conta corrente. A ficha orienta não informar conta poupança.",
    )
    dependents: list[Dependent] = Field(
        default_factory=list, max_length=6, title="Dependentes",
        description="A ficha possui espaço para seis dependentes. Nome da mãe e CPF: "
        "informações indicadas na ficha para seguro saúde / odontológico.",
    )
    employment: EmploymentDetails = Field(default_factory=EmploymentDetails, title="Histórico profissional — emprego atual ou último")
    languages: LanguageDetails = Field(default_factory=LanguageDetails, title="Idiomas")
    education: EducationDetails = Field(default_factory=EducationDetails, title="Grau de instrução")
    complementary: ComplementaryDetails = Field(default_factory=ComplementaryDetails, title="Informações complementares")
    declaration: ExternalDeclaration = Field(
        default_factory=ExternalDeclaration, title="Revise, assine e confirme a ficha",
        description=TRUTH_DECLARATION + "\n\n" + UPDATE_DECLARATION,
    )

    @model_validator(mode="after")
    def complete_signed_form(self):
        if not self.declaration.accepted:
            return self
        required = {"Cargo pretendido": self.desired_position, "Nome completo": self.personal.name,
                    "Data de nascimento": self.personal.birth_date, "Celular": self.personal.mobile,
                    "E-mail": self.personal.email, "Endereço": self.personal.address.street,
                    "Cidade": self.personal.address.city, "UF": self.personal.address.state,
                    "CPF": self.documents.cpf, "RG": self.documents.rg}
        missing = [label for label, value in required.items() if not value or not str(value).strip()]
        if missing:
            raise ValueError("Para concluir a ficha, preencha: " + ", ".join(missing) + ". Complete também as informações que se aplicam a você.")
        if self.declaration.signature_name.strip().casefold() != self.personal.name.strip().casefold():
            raise ValueError("O nome do signatário deve ser igual ao nome completo informado na ficha.")
        return self


class SelectionRegistrationInput(StrictModel):
    data: SelectionRegistration
    version: int = Field(ge=0)
