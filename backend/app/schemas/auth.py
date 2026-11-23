from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    source: str = "LOCAL"
    area: Literal["RH", "GESTOR", "CANDIDATO"] | None = None
    revalidate_network_password: bool = False


class Register(StrictModel):
    name: str = Field(min_length=3, max_length=180)
    email: EmailStr
    notice_id: str | None = None
    receipt_id: str | None = None
    consent: bool
    defer_consent_to_profile: bool = False
    return_to: str | None = Field(default=None, max_length=1000)

    @field_validator("return_to")
    @classmethod
    def validate_return_to(cls, value):
        if value and (
            not value.startswith(("/carreiras/vagas/", "/oportunidades-internas/", "/convite"))
            or "\\" in value or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("Destino de retorno inválido")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower()


class EmailRequest(StrictModel):
    email: EmailStr
    purpose: str = "RESET"
    return_to: str | None = Field(default=None, max_length=1000)

    @field_validator("return_to")
    @classmethod
    def validate_return_to(cls, value):
        return Register.validate_return_to(value)


class TokenRequest(StrictModel):
    token: str = Field(min_length=20, max_length=300)
    password: str | None = Field(default=None, min_length=6, max_length=6)


class PasswordChange(StrictModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=6)
