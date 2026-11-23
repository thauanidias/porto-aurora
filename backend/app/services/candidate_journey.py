"""Candidate-facing permissions derived from the current recruitment stage."""
from typing import Literal

from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Application, Candidate, PipelineStage, ProcessForm, StageReview, Vacancy

CandidatePhase = Literal["REGISTER", "RECRUITMENT", "SELECTION", "FORM", "INTERVIEW", "TEST", "ADMISSION"]
ACTIVE_STATUSES = {"ACTIVE", "RESERVE", "SELECTED", "PRE_ADMISSION", "HIRED"}
PHASE_RANK = {"REGISTER": 0, "RECRUITMENT": 1, "SELECTION": 2, "FORM": 2, "INTERVIEW": 3,
              "TEST": 4, "ADMISSION": 5}
PHASE_LABELS = {"REGISTER": "Cadastro", "RECRUITMENT": "Recrutamento",
                "SELECTION": "Seleção de currículo", "FORM": "Perguntas e ficha externa",
                "INTERVIEW": "Entrevistas", "TEST": "Testes", "ADMISSION": "Admissão"}
SECTIONS = {
    "basic_profile": (0, "Cadastro e dados básicos", "perfil"),
    "resume": (0, "Currículo", "perfil#curriculo"),
    "professional_profile": (0, "Formação, experiências e competências", "perfil#perfil-profissional"),
    "questions": (4, "Perguntas da vaga", "testes#perguntas"),
    "selection_registration": (2, "Ficha de inscrição externa", "perfil#ficha-externa"),
    "consent": (0, "Termo de consentimento", "privacidade"),
    "sensitive_profile": (0, "Acessibilidade e informações opcionais", "perfil#informacoes-complementares"),
    "interviews": (3, "Entrevistas", "entrevistas"),
    "tests": (4, "Testes", "testes"),
    "messages": (2, "Conversa com o RH", "mensagens"),
    "admission": (5, "Documentos admissionais", "documentos"),
}


def stage_phase(db, stage):
    if stage.candidate_phase:
        return stage.candidate_phase
    if stage.kind in {"INTERVIEW", "TEST"}:
        return stage.kind
    if stage.kind in {"FINALIST", "OFFER", "HIRED"}:
        return "ADMISSION"
    first = db.scalar(select(PipelineStage.id).where(PipelineStage.vacancy_id == stage.vacancy_id)
                      .order_by(PipelineStage.position).limit(1))
    return "RECRUITMENT" if stage.id == first else "SELECTION"


def questions_completed(db, application):
    form = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application.id))
    vacancy = db.get(Vacancy, application.vacancy_id)
    questions = form.questions if form else (vacancy.details or {}).get("questions", []) if vacancy else []
    if not questions or (form and form.status == "COMPLETED"):
        return True
    answers = application.answers or {}
    required = [q for q in questions if q.get("required")]
    return bool(answers) and all(answers.get(q["key"]) not in (None, "", []) for q in required)


def application_permissions(db, application):
    stage = db.get(PipelineStage, application.stage_id)
    phase = stage_phase(db, stage) if stage else "REGISTER"
    if application.status in {"SELECTED", "PRE_ADMISSION", "HIRED"}:
        phase = "ADMISSION"
    active = application.status in ACTIVE_STATUSES
    rank = PHASE_RANK.get(phase, 0) if active else 0
    permissions = {key: active and rank >= required for key, (required, _, _) in SECTIONS.items()}
    # A favorable review alone does not release activities: RH must confirm advancement.
    permissions["selection_registration"] = active and (phase == "FORM" or rank >= 3)
    permissions["messages"] = active and (phase == "FORM" or rank >= 3)
    if application.recruitment_type != "INTERNAL":
        permissions["selection_registration"] = permissions["selection_registration"] and questions_completed(db, application)
    permissions["process_form"] = active and (phase == "FORM" or rank >= 3)
    permissions["consent"] = True
    permissions["questions"] = active and (phase == "FORM" or rank >= 3)
    # Documents additionally require selection and explicit RH approval in the documents API.
    permissions["admission"] = active and phase == "ADMISSION"
    return {"phase": phase, "phase_label": PHASE_LABELS[phase], "rank": rank,
            "active": active, "permissions": permissions}


def candidate_permissions(db, candidate):
    permissions = {key: required == 0 for key, (required, _, _) in SECTIONS.items()}
    permissions["process_form"] = False
    if candidate:
        applications = db.scalars(select(Application).where(Application.candidate_id == candidate.id))
        for application in applications:
            access = application_permissions(db, application)
            for key, allowed in access["permissions"].items():
                permissions[key] = permissions[key] or allowed
        from app.services.admission_documents import admission_can_release
        permissions["admission"] = bool(candidate.admission_documents_approved and admission_can_release(db, candidate))
    return permissions


def require_candidate_section(db, actor, section):
    if actor.user.kind != "CANDIDATO":
        return
    if section == "resume" and "internal.view" in actor.permissions:
        return
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    if not candidate_permissions(db, candidate).get(section, False):
        raise DomainError("Esta atividade está bloqueada. Aguarde o RH liberar a etapa correspondente.",
                          403, "STAGE_LOCKED")


def require_application_section(db, application, section):
    if not application_permissions(db, application)["permissions"].get(section, False):
        raise DomainError("Esta atividade ainda não foi liberada para esta candidatura.", 403, "STAGE_LOCKED")


def journey(db, candidate):
    permissions = candidate_permissions(db, candidate)
    processes = []
    if candidate:
        for application in db.scalars(select(Application).where(Application.candidate_id == candidate.id)
                                      .order_by(Application.updated_at.desc())):
            vacancy = db.get(Vacancy, application.vacancy_id)
            stage = db.get(PipelineStage, application.stage_id)
            access = application_permissions(db, application)
            processes.append({"id": application.id, "vacancy_title": vacancy.title,
                              "stage_name": stage.name, "status": application.status,
                              "updated_at": application.updated_at, **access})
    active = [item for item in processes if item["active"]]
    current = max(active, key=lambda item: item["rank"]) if active else None
    return {"phase": current["phase"] if current else "REGISTER", "processes": processes,
            "sections": {key: {"enabled": allowed, "title": SECTIONS[key][1],
                               "path": SECTIONS[key][2], "reason": "Liberado para preenchimento."
                               if allowed else "Aguardando avanço e liberação pelo RH."}
                         for key, allowed in permissions.items() if key in SECTIONS}}
