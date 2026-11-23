from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from app.schemas.auth import StrictModel


class Experience(StrictModel):
    company: str = Field(min_length=2, title="Empresa")
    position: str = Field(min_length=2, title="Cargo")
    start: date | None = Field(default=None, title="Início — data completa, se informada")
    period_text: str = Field(default="", max_length=180, title="Período informado no currículo (ex.: 2021–2023)")
    end: date | None = Field(default=None, title="Fim")
    current: bool = Field(default=False, title="Emprego atual")
    description: str = Field(default="", title="Atividades")

    @model_validator(mode="after")
    def dates(self):
        if (self.start and self.start > date.today()) or (self.end and self.start and self.end < self.start):
            raise ValueError("Período profissional inválido")
        if self.start and not self.current and not self.end and not self.period_text:
            raise ValueError("Informe a data de saída")
        return self


class Education(StrictModel):
    institution: str = Field(default="", max_length=180, title="Instituição")
    course: str = Field(default="", max_length=180, title="Curso")
    degree: Literal["FUNDAMENTAL", "MEDIO", "TECNICO", "SUPERIOR", "POS", "MESTRADO", "DOUTORADO"] | None = None
    status: Literal["CURSANDO", "CONCLUIDO", "INTERROMPIDO"] | None = None
    start: date | None = None
    end: date | None = None
    period_text: str = Field(default="", max_length=180, title="Período / conclusão ou previsão informada no currículo")


class Course(StrictModel):
    name: str = Field(min_length=2, title="Curso")
    institution: str = Field(default="", max_length=180, title="Instituição")
    hours: int | None = Field(default=None, ge=0, le=10000, title="Carga horária")
    completion: date | None = None
    completion_text: str = Field(default="", max_length=180, title="Conclusão informada no currículo")


class Certification(StrictModel):
    name: str = Field(min_length=2, title="Certificação")
    issuer: str = Field(default="", max_length=180, title="Emissor")
    issued: date | None = None
    issued_text: str = Field(default="", max_length=180, title="Emissão informada no currículo")
    expires: date | None = None
    code: str = ""
    document_id: UUID | None = Field(default=None, title="PDF do certificado")


class Language(StrictModel):
    language: str = Field(min_length=2, title="Idioma")
    reading: int | None = Field(default=None, ge=0, le=5, title="Leitura (0 a 5, se informado)")
    writing: int | None = Field(default=None, ge=0, le=5, title="Escrita (0 a 5, se informado)")
    speaking: int | None = Field(default=None, ge=0, le=5, title="Conversação (0 a 5, se informado)")
    level_text: str = Field(default="", max_length=180, title="Nível informado no currículo (ex.: intermediário)")


class Profile(StrictModel):
    desired_position: str = Field(default="", max_length=180, title="Cargo pretendido")
    notes: str = Field(default="", max_length=2000, title="Observações profissionais")
    experiences: list[Experience] = Field(
        default_factory=list, max_length=50, title="Experiência profissional"
    )
    education: list[Education] = Field(default_factory=list, max_length=30, title="Formação")
    courses: list[Course] = Field(default_factory=list, max_length=100, title="Cursos")
    certifications: list[Certification] = Field(
        default_factory=list, max_length=100, title="Certificações"
    )
    languages: list[Language] = Field(default_factory=list, max_length=30, title="Idiomas")
    skills: list[str] = Field(default_factory=list, max_length=100, title="Competências")
    availability: bool = Field(default=False, title="Disponibilidade imediata")
    shift: str = Field(default="", title="Turno disponível")
    travel: bool = Field(default=False, title="Disponível para viagens")
    relocation: bool = Field(default=False, title="Disponível para mudança")
    expected_salary: float | None = Field(
        default=None, ge=0, le=1000000, title="Pretensão salarial"
    )
    links: list[HttpUrl] = Field(default_factory=list, max_length=10, title="Links profissionais")


class CandidateInput(StrictModel):
    name: str = Field(min_length=3, max_length=180, title="Nome")
    social_name: str = Field(default="", max_length=180, title="Nome social")
    phone: str = Field(default="", max_length=30, title="Telefone")
    city: str = Field(default="", max_length=120, title="Cidade")
    state: str = Field(default="", max_length=2, title="Estado")
    country: str = Field(default="BR", min_length=2, max_length=2, title="País")
    profile: Profile
    version: int | None = None


def professional_facts(profile: Profile):
    months: set[int] = set()
    today = date.today()
    for experience in profile.experiences:
        end = today if experience.current else experience.end
        if end and experience.start:
            months.update(
                range(
                    experience.start.year * 12 + experience.start.month,
                    min(end, today).year * 12 + min(end, today).month,
                )
            )
    degrees = {
        "FUNDAMENTAL": 1,
        "MEDIO": 2,
        "TECNICO": 3,
        "SUPERIOR": 4,
        "POS": 5,
        "MESTRADO": 6,
        "DOUTORADO": 7,
    }
    return {
        "experience_years": None if any(not item.start or (not item.current and not item.end) for item in profile.experiences) else round(len(months) / 12, 4),
        "education_level": None if any(item.degree is None or item.status is None for item in profile.education) else max(
            (degrees[item.degree] for item in profile.education if item.status == "CONCLUIDO" and item.degree in degrees),
            default=0,
        ),
        "certifications": [
            item.name
            for item in profile.certifications
            if not item.expires or item.expires >= today
        ],
        "skills": profile.skills,
        "languages": None if any(value is None for item in profile.languages for value in [item.reading, item.writing, item.speaking]) else max(
            (min(value for value in [item.reading, item.writing, item.speaking] if value is not None) for item in profile.languages
             if all(value is not None for value in [item.reading, item.writing, item.speaking])),
            default=0,
        ),
        "availability": profile.availability,
        "shift": profile.shift,
        "travel": profile.travel,
        "relocation": profile.relocation,
    }
