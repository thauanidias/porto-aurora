import re
import unicodedata
from copy import deepcopy
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import DomainError
from app.core.permissions import vacancy_access
from app.core.security import digest
from app.domain.rules import matches
from app.domain.scoring import calculate
from app.models import (
    Application,
    ApplicationScore,
    AuthToken,
    Candidate,
    CandidateActivityLink,
    ConfigRecord,
    Consent,
    Document,
    Evaluation,
    PipelineStage,
    Referral,
    ScoringVersion,
    StageHistory,
    StageReview,
    TestAssignment,
    TestAttempt,
    User,
    Vacancy,
)
from app.repositories.common import serialize
from app.services.events import audit, event, notify


def create_vacancy(db, actor, data: dict):
    actor.require("vacancy.create")
    data.pop("publish_on_save", None)
    template_id = data.pop("vacancy_template_id", None)
    template = db.get(ConfigRecord, template_id) if template_id else None
    if template_id and (
        not template or template.kind != "vacancy-templates" or not template.active
    ):
        raise DomainError("Template de vaga inválido.")
    if template:
        data["description"] = data.get("description") or template.data["description"]
        data["details"] = deepcopy(template.data["details"]) | {
            k: v for k, v in data.get("details", {}).items() if v not in (None, "", [], False)
        }
    for key in ("recruiter_id", "manager_id"):
        user = db.get(User, data[key])
        if not user or user.kind != "INTERNAL" or not user.active:
            raise DomainError("Responsável inválido.")
    code = "Porto Aurora-" + uuid4().hex[:10].upper()
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        unicodedata.normalize("NFKD", data["title"]).encode("ascii", "ignore").decode().lower(),
    ).strip("-")
    vacancy = Vacancy(**data, code=code, slug=slug + "-" + code.lower())
    db.add(vacancy)
    db.flush()
    if template:
        for stage in template.data["stages"]:
            db.add(PipelineStage(vacancy_id=vacancy.id, **deepcopy(stage)))
        db.add(
            ScoringVersion(
                vacancy_id=vacancy.id,
                number=1,
                criteria=deepcopy(template.data["criteria"]),
                composition={"OBJECTIVE": 100},
                bands=[],
                reason="Template " + template.name + " versão " + str(template.version),
                created_by=actor.user.id,
            )
        )
    event(db, actor, "vacancy.created", vacancy, vacancy.id)
    return vacancy


def publication_checklist(
    db: Session, vacancy: Vacancy, *, approval_required: bool = True
) -> list[dict]:
    pipeline = db.scalar(select(PipelineStage.id).where(PipelineStage.vacancy_id == vacancy.id))
    model = db.scalar(select(ScoringVersion.id).where(ScoringVersion.vacancy_id == vacancy.id))
    notice = db.get(ConfigRecord, vacancy.details.get("notice_id", ""))
    checks = {
        "Título": len(vacancy.title) >= 3,
        "Descrição": len(vacancy.description.strip()) >= 30,
        "Localização": bool(vacancy.city and vacancy.state),
        "Pipeline": bool(pipeline),
        "Responsável": bool(vacancy.recruiter_id),
        "Requisitos e aderência": bool(model and vacancy.details.get("requirements")),
        "Formulário de candidatura": "questions" in vacancy.details,
        "Política de privacidade": bool(
            notice and notice.kind == "privacy-notices" and notice.active
        ),
        "Prazo": bool(vacancy.deadline and vacancy.deadline > utcnow()),
    }
    if approval_required:
        checks["Aprovação"] = vacancy.status in {"APPROVED", "PAUSED", "PUBLISHED"}
    return [{"label": label, "ok": bool(ok)} for label, ok in checks.items()]


def publish_direct(db: Session, actor, vacancy: Vacancy) -> None:
    """Allow RH to publish a complete vacancy without a separate approval flow."""
    actor.require("vacancy.publish")
    if vacancy.status not in {"DRAFT", "APPROVED"}:
        raise DomainError("A vaga não está pronta para publicação direta.", 409)
    if not vacancy.details.get("notice_id"):
        notice = db.scalar(
            select(ConfigRecord)
            .where(ConfigRecord.kind == "privacy-notices", ConfigRecord.active.is_(True))
            .order_by(ConfigRecord.created_at.desc())
            .limit(1)
        )
        if notice:
            vacancy.details = vacancy.details | {"notice_id": notice.id}
    if not db.scalar(select(PipelineStage.id).where(PipelineStage.vacancy_id == vacancy.id)):
        from app.services.process_workflow import configure_workflow
        configure_workflow(db, vacancy)
    if not db.scalar(select(ScoringVersion.id).where(ScoringVersion.vacancy_id == vacancy.id)):
        db.add(
            ScoringVersion(
                vacancy_id=vacancy.id,
                number=1,
                criteria=[
                    {
                        "key": "analise_manual",
                        "name": "Análise manual do perfil",
                        "field": "skills",
                        "kind": "MULTI_CHOICE",
                        "weight": 100,
                        "expected": ["Análise manual"],
                        "mandatory": False,
                        "knockout": False,
                        "not_applicable": True,
                        "category": "OBJECTIVE",
                        "justification": "A avaliação será feita pelo RH; não há pontuação nem eliminação automática.",
                    }
                ],
                composition={"OBJECTIVE": 100},
                bands=[],
                reason="Modelo inicial sem pontuação automática; avaliação manual pelo RH.",
                created_by=actor.user.id,
            )
        )
    db.flush()
    failed = [
        item["label"]
        for item in publication_checklist(db, vacancy, approval_required=False)
        if not item["ok"]
    ]
    if failed:
        raise DomainError("Pendências para publicar: " + ", ".join(failed))
    vacancy.status = "PUBLISHED"
    vacancy.published_at = vacancy.published_at or utcnow()
    from app.services.talent_bank import enroll_talents
    enroll_talents(db, actor, vacancy)
    event(db, actor, "vacancy.status_changed", vacancy, vacancy.id)


def calculate_application(db, actor, application, model=None, curriculum_analysis=None):
    model = model or db.scalar(
        select(ScoringVersion)
        .where(ScoringVersion.vacancy_id == application.vacancy_id)
        .order_by(ScoringVersion.number.desc())
        .limit(1)
    )
    if not model:
        raise DomainError("A vaga não possui modelo de aderência.")
    tests = db.scalars(
        select(TestAttempt)
        .join(TestAssignment, TestAttempt.assignment_id == TestAssignment.id)
        .where(TestAssignment.application_id == application.id, TestAttempt.status == "GRADED")
        .distinct(TestAttempt.assignment_id)
        .order_by(TestAttempt.assignment_id, TestAttempt.number.desc())
    ).all()
    test_score = sum(float(item.score) for item in tests) / len(tests) if tests else None
    evaluations = db.scalars(
        select(Evaluation).where(
            Evaluation.application_id == application.id, Evaluation.submitted_at.is_not(None)
        )
    ).all()
    evaluation_score = (
        sum(float(item.score) for item in evaluations) / len(evaluations) if evaluations else None
    )
    facts = application.profile_snapshot.get("facts", {}) | {
        "test_score": test_score,
        "evaluation_score": evaluation_score,
    }
    result = calculate(model.criteria, facts)
    components = {"OBJECTIVE": result["total"], "TEST": test_score}
    objective = result["total"]
    for category in ("RH", "MANAGER", "TECHNICAL"):
        scores = [float(item.score) for item in evaluations if item.category == category]
        components[category] = sum(scores) / len(scores) if scores else None
    composition = model.composition or {"OBJECTIVE": 100}
    available = sum(
        weight for key, weight in composition.items() if components.get(key) is not None
    )
    total = (
        round(
            sum(
                components[key] * weight
                for key, weight in composition.items()
                if components.get(key) is not None
            )
            / available,
            2,
        )
        if available
        else None
    )
    result.update(
        {
            "objective_total": objective,
            "total": total,
            "components": components,
            "composition": composition,
            "pending_components": [key for key in composition if components.get(key) is None],
            "model_version": model.number,
        }
    )
    if curriculum_analysis is None:
        previous_analysis = db.scalar(select(ApplicationScore).where(
            ApplicationScore.application_id == application.id, ApplicationScore.model_id == model.id,
            ApplicationScore.breakdown.op("?")("curriculum_analysis"))
            .order_by(ApplicationScore.created_at.desc(), ApplicationScore.id.desc()).limit(1))
        if previous_analysis:
            curriculum_analysis = previous_analysis.breakdown["curriculum_analysis"]
    if curriculum_analysis is not None:
        result["curriculum_analysis"] = curriculum_analysis
    score = ApplicationScore(
        application_id=application.id,
        model_id=model.id,
        total=total,
        knockout=result["knockout"],
        breakdown=result,
        created_by=actor.user.id,
    )
    db.add(score)
    db.flush()
    event(db, actor, "score.calculated", score, application.vacancy_id)
    return score


def apply(db, actor, body):
    from app.core.config import settings

    if settings().environment == "production" and not actor.user.email_verified:
        raise DomainError(
            "Confirme seu e-mail antes de enviar a candidatura.", 409, "EMAIL_UNVERIFIED"
        )
    vacancy = db.scalar(select(Vacancy).where(Vacancy.id == body.vacancy_id).with_for_update())
    invitation = (
        db.scalar(
            select(AuthToken)
            .where(AuthToken.token_hash == digest(body.invitation_token))
            .with_for_update()
        )
        if body.invitation_token
        else None
    )
    invited = bool(
        invitation
        and not invitation.used_at
        and invitation.expires_at > utcnow()
        and invitation.user_id == actor.user.id
        and invitation.purpose == "VACANCY_INVITE:" + body.vacancy_id
    )
    if (
        not vacancy
        or vacancy.status != "PUBLISHED"
        or vacancy.confidential
        and not invited
        or not vacancy.deadline
        or vacancy.deadline <= utcnow()
    ):
        raise DomainError("Esta vaga não está recebendo candidaturas.", 409)
    if vacancy.audience == "INTERNAL" and "internal.view" not in actor.permissions:
        raise DomainError("Oportunidade exclusiva para colaboradores.", 403)
    candidate = db.scalar(select(Candidate).where(Candidate.user_id == actor.user.id))
    if not candidate:
        raise DomainError("Preencha seu perfil de candidato.")
    if db.scalar(
        select(Application.id).where(
            Application.vacancy_id == vacancy.id, Application.candidate_id == candidate.id
        )
    ):
        raise DomainError("Você já possui uma candidatura nesta vaga.", 409, "ALREADY_APPLIED")
    from app.services.application_readiness import require_application_ready
    readiness = require_application_ready(db, candidate)
    from app.services.candidate_journey import PHASE_RANK, stage_phase
    from app.services.process_workflow import initial_application_stage
    stage = initial_application_stage(db, vacancy.id)
    if not stage:
        raise DomainError("Pipeline não configurado.")
    if body.enrollment and (body.answers or body.consent):
        raise DomainError("O termo será liberado na seleção; as perguntas, na etapa de testes.", 403, "STAGE_LOCKED")
    if not body.enrollment and PHASE_RANK[stage_phase(db, stage)] < 2:
        raise DomainError("Registre sua inscrição primeiro. Aguarde a liberação da seleção para aceitar o termo.", 403, "STAGE_LOCKED")
    if body.answers and PHASE_RANK[stage_phase(db, stage)] < 4:
        raise DomainError("Aguarde a liberação da etapa de testes para responder às perguntas.", 403, "STAGE_LOCKED")
    notice = db.get(ConfigRecord, body.notice_id) if body.notice_id else None
    if (
        not body.enrollment and (not body.consent
        or not notice
        or not notice.active
        or notice.kind != "privacy-notices"
        or vacancy.details.get("notice_id") != notice.id)
    ):
        raise DomainError("Aceite o aviso de privacidade da vaga.")
    questions = vacancy.details.get("questions", [])
    if set(body.answers) - {q["key"] for q in questions}:
        raise DomainError("O formulário contém respostas para perguntas inexistentes.")
    for question in questions:
        if not body.enrollment and PHASE_RANK[stage_phase(db, stage)] >= 4 and question.get("required") and body.answers.get(question["key"]) in (None, "", []):
            raise DomainError("Responda a pergunta: " + question["label"])
        value = body.answers.get(question["key"])
        if value is not None and value != "":
            kind = question.get("kind")
            if (
                kind == "BOOLEAN"
                and type(value) is not bool
                or kind == "NUMBER"
                and (type(value) not in {int, float} or not __import__("math").isfinite(value))
                or kind == "SINGLE"
                and value not in question.get("options", [])
                or kind == "MULTIPLE"
                and (
                    not isinstance(value, list)
                    or any(v not in question.get("options", []) for v in value)
                )
            ):
                raise DomainError("Resposta inválida: " + question["label"])
    recruitment_type = "INTERNAL" if vacancy.audience == "INTERNAL" or (
        vacancy.audience == "BOTH" and "internal.view" in actor.permissions
    ) else "EXTERNAL"
    cv_id = body.cv_id or readiness["cv_id"]
    if not cv_id and recruitment_type == "INTERNAL":
        cv_id = db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
            Document.type_name == "CURRICULO", Document.status != "REJECTED", Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"])
        ).order_by(Document.created_at.desc(), Document.revision.desc()).limit(1))
    if cv_id:
        document = db.get(Document, cv_id)
        if (
            not document
            or document.candidate_id != candidate.id
            or document.type_name != "CURRICULO"
            or document.status == "REJECTED"
            or document.scan_status not in {"CLEAN", "NOT_CONFIGURED"}
        ):
            raise DomainError("Currículo inválido.")
    application = Application(
        candidate_id=candidate.id,
        vacancy_id=vacancy.id,
        stage_id=stage.id,
        answers=body.answers,
        profile_snapshot=deepcopy(candidate.profile),
        source=candidate.source,
        recruitment_type=recruitment_type,
        cv_id=cv_id,
        utm=body.utm,
        stage_entered_at=utcnow(),
    )
    if invited and invitation:
        invitation.used_at = utcnow()
    referral = db.scalar(
        select(Referral)
        .where(
            Referral.vacancy_id == vacancy.id,
            Referral.email == actor.user.email,
            Referral.status != "CONFIRMED",
        )
        .with_for_update()
    )
    if referral:
        referral.status = "CONFIRMED"
        referral.candidate_id = candidate.id
        application.source = "INDICACAO"
    db.add(application)
    db.flush()
    if not body.enrollment and notice:
        db.add(
            Consent(candidate_id=candidate.id, notice_id=notice.id,
                    notice_version=notice.version, notice_snapshot=notice.data,
                    purpose="RECRUITMENT", granted=True, ip=actor.ip)
        )
    db.add(
        StageHistory(
            application_id=application.id,
            stage_id=stage.id,
            entered_at=utcnow(),
            changed_by=actor.user.id,
        )
    )
    calculate_application(db, actor, application)
    event(db, actor, "application.created", application, vacancy.id)
    notify(
        db,
        vacancy.recruiter_id,
        "Nova candidatura",
        "Há uma candidatura em " + vacancy.title,
        "CANDIDATE",
        "/app/vagas/" + vacancy.id,
    )
    notify(
        db,
        actor.user.id,
        "Candidatura recebida",
        "Sua candidatura está na etapa " + stage.name + ". Consulte as atividades liberadas no portal.",
        "CANDIDATE",
        "/candidato/candidaturas/" + application.id,
    )
    return application


def move(db, actor, application, stage_id, reason="", override=False):
    from app.services.candidate_journey import SECTIONS, application_permissions
    before_access = application_permissions(db, application)
    actor.require("candidate.move")
    vacancy = vacancy_access(db, actor, application.vacancy_id, "candidate.move")
    target = db.get(PipelineStage, stage_id)
    current = db.get(PipelineStage, application.stage_id)
    if not target or target.vacancy_id != vacancy.id:
        raise DomainError("Etapa inválida.")
    if target.kind in {"OFFER", "HIRED"}:
        raise DomainError("O fluxo de seleção termina em Finalistas. Registre a decisão nesta etapa.", 409)
    if application.status not in {"ACTIVE", "RESERVE"} or vacancy.status not in {
        "PUBLISHED",
        "PAUSED",
    }:
        raise DomainError("O processo não permite movimentação.", 409)
    if target.id == current.id:
        return application
    from app.services.process_workflow import workflow_blockers
    workflow_errors = workflow_blockers(db, application, vacancy, current, target)
    if workflow_errors and not (override and vacancy.details.get("allow_override") and len(reason.strip()) >= 10):
        raise DomainError(" ".join(workflow_errors), 409, "WORKFLOW_PENDING")
    facts = application.profile_snapshot.get("facts", {}) | {
        "status": application.status,
        "stage_id": application.stage_id,
    }
    if not matches(target.rules, facts):
        raise DomainError(
            "Esta etapa não se aplica aos critérios profissionais da candidatura.", 409
        )
    score = db.scalar(
        select(ApplicationScore)
        .where(ApplicationScore.application_id == application.id)
        .order_by(ApplicationScore.created_at.desc())
        .limit(1)
    )
    required = db.scalars(
        select(PipelineStage).where(
            PipelineStage.vacancy_id == vacancy.id,
            PipelineStage.required.is_(True),
            PipelineStage.position < target.position,
        )
    ).all()
    visited = set(
        db.scalars(
            select(StageHistory.stage_id).where(
                StageHistory.application_id == application.id, StageHistory.left_at.is_not(None)
            )
        )
    )
    blocked = any(
        stage.id not in visited and stage.id != current.id and matches(stage.rules, facts)
        for stage in required
    ) or bool(score and score.knockout)
    if current.required and current.kind == "TEST":
        pending = db.scalars(
            select(TestAssignment).where(TestAssignment.application_id == application.id)
        ).all()
        external_links = db.scalars(select(CandidateActivityLink).where(
            CandidateActivityLink.application_id == application.id,
            CandidateActivityLink.kind == "TEST", CandidateActivityLink.active.is_(True))).all()
        if external_links and any(not link.completed_at for link in external_links):
            raise DomainError("Confirme que o candidato concluiu a fase de testes por link antes de avançar.", 409)
        blocked = (
            blocked
            or (not pending and not external_links)
            or any(
                not db.scalar(
                    select(TestAttempt.id).where(
                        TestAttempt.assignment_id == item.id,
                        TestAttempt.status == "GRADED",
                        TestAttempt.score >= item.snapshot.get("pass_score", 60),
                    )
                )
                for item in pending
            )
        )
    if current.required and current.kind == "INTERVIEW":
        interview_review = db.scalar(select(StageReview).where(
            StageReview.application_id == application.id, StageReview.stage_id == current.id,
            StageReview.created_at >= application.stage_entered_at)
            .order_by(StageReview.created_at.desc(), StageReview.id.desc()).limit(1))
        validated = interview_review is not None and interview_review.status == "APPROVED"
        blocked = blocked or not (validated or db.scalar(
            select(Evaluation.id).where(
                Evaluation.application_id == application.id, Evaluation.submitted_at.is_not(None)
            )
        ))
    if blocked and not (
        override and vacancy.details.get("allow_override") and len(reason.strip()) >= 10
    ):
        raise DomainError(
            "Há requisitos ou etapas obrigatórias pendentes. Uma exceção exige política e justificativa.",
            409,
        )
    now = utcnow()
    history = db.scalar(
        select(StageHistory)
        .where(StageHistory.application_id == application.id, StageHistory.left_at.is_(None))
        .with_for_update()
    )
    if history:
        history.left_at = now
    db.add(
        StageHistory(
            application_id=application.id,
            stage_id=target.id,
            entered_at=now,
            changed_by=actor.user.id,
            reason=("Exceção autorizada: " if blocked else "") + reason,
        )
    )
    application.stage_id = target.id
    application.stage_entered_at = now
    event(db, actor, "application.stage_changed", application, vacancy.id)
    candidate = db.get(Candidate, application.candidate_id)
    after_access = application_permissions(db, application)
    if after_access["permissions"]["admission"] and not before_access["permissions"]["admission"]:
        candidate.admission_documents_approved = True
        audit(db, actor, "candidate.admission_documents_approved", candidate, vacancy_id=vacancy.id)
    released = [SECTIONS[key][1] for key, allowed in after_access["permissions"].items()
                if key in SECTIONS and allowed and not before_access["permissions"][key] and key != "basic_profile"]
    advanced = target.position > current.position
    text = ("Você passou para a etapa " if advanced else "Sua etapa foi atualizada para ") + target.name + "."
    if released:
        text += " Atividades liberadas: " + ", ".join(released) + ". Acesse o portal para continuar."
    title = "Sua candidatura avançou" if advanced else "Etapa atualizada"
    if advanced and target.kind == "FINALIST":
        first_name = candidate.name.strip().split()[0] if candidate.name.strip() else ""
        title = "Parabéns! Você está entre os finalistas!"
        text = (f"Olá, {first_name}!\n\n"
                f"Temos uma ótima notícia: você chegou à etapa de finalistas para a vaga de {vacancy.title}!\n\n"
                "Foi muito bom conhecer sua trajetória e acompanhar sua participação até aqui. "
                "Celebre essa conquista: estamos felizes em seguir com você nesta fase!\n\n"
                "Acompanhe os próximos passos e as orientações do RH no seu portal. "
                "Estar entre os finalistas ainda não representa a confirmação da contratação.\n\n"
                "Torcendo por uma ótima próxima etapa!\nEquipe de Recursos Humanos — Porto Aurora Talentos")
    notify(db, candidate.user_id, title, text, "CANDIDATE", "/candidato/candidaturas/" + application.id)
    return application


def candidate_view(db, actor, candidate, application=None):
    hidden = False
    if candidate.user_id != actor.user.id:
        if application:
            vacancy = db.get(Vacancy, application.vacancy_id)
            stage = db.get(PipelineStage, application.stage_id)
            hidden = vacancy.blind and not stage.reveal_identity
        else:
            processes = db.execute(
                select(Vacancy, PipelineStage)
                .join(Application, Application.vacancy_id == Vacancy.id)
                .join(PipelineStage, PipelineStage.id == Application.stage_id)
                .where(Application.candidate_id == candidate.id)
            ).all()
            hidden = any(v.blind and not s.reveal_identity for v, s in processes)
    result = serialize(candidate)
    if hidden:
        result = {
            "id": candidate.id,
            "name": "Candidato #" + candidate.id[:5].upper(),
            "profile": {"facts": candidate.profile.get("facts", {})},
            "blind": True,
            "version": candidate.version,
        }
    return result
