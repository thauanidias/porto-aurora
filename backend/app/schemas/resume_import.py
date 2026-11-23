import re
from datetime import date

from pydantic import EmailStr, Field, field_validator

from app.schemas.auth import StrictModel
from app.schemas.candidates import CandidateInput
from app.schemas.selection_registration import Address


class ResumePersonal(StrictModel):
    cpf: str = Field(default="", max_length=14, title="CPF, se informado no currículo")
    birth_date: date | None = Field(default=None, title="Data de nascimento")
    email: EmailStr | None = Field(default=None, title="E-mail informado no currículo")
    address: Address = Field(default_factory=Address, title="Endereço informado no currículo")

    @field_validator("cpf")
    @classmethod
    def valid_cpf(cls, value):
        digits = re.sub(r"\D", "", value)
        if not digits:
            return ""
        if len(digits) != 11 or len(set(digits)) == 1:
            raise ValueError("Confira o CPF informado")
        for size in (9, 10):
            digit = (sum(int(digits[i]) * (size + 1 - i) for i in range(size)) * 10 % 11) % 10
            if digit != int(digits[size]):
                raise ValueError("Confira o CPF informado")
        return digits

    @field_validator("birth_date")
    @classmethod
    def valid_birth_date(cls, value):
        if value and value > date.today():
            raise ValueError("Confira a data de nascimento")
        return value


class ResumePersonalInput(StrictModel):
    data: ResumePersonal
    version: int = Field(ge=0)


class ConfirmResumeImport(StrictModel):
    candidate: CandidateInput
    personal: ResumePersonal
    personal_version: int = Field(ge=0)
    confirmed: bool
