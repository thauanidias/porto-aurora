from sqlalchemy import select

from app.core.errors import DomainError
from app.models import Candidate, Document, Evaluation, PipelineStage, ProcessForm, StageReview
from app.services.candidate_journey import stage_phase


def initial_application_stage(db, vacancy_id):
    """Completed enrollments enter resume screening; retain custom-pipeline fallback."""
    stages = list(db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy_id)
                             .order_by(PipelineStage.position)))
    return next((stage for stage in stages if stage_phase(db, stage) == "SELECTION"), stages[0] if stages else None)


def configure_workflow(db, vacancy):
    stages = list(db.scalars(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy.id)
                             .order_by(PipelineStage.position)))
    if not stages:
        for position, (name, kind, phase) in enumerate([
            ("Cadastro", "SCREENING", "REGISTER"),
            ("Recrutamento", "SCREENING", "RECRUITMENT"),
            ("Triagem de currículos", "SCREENING", "SELECTION"),
            ("Perguntas e ficha externa", "SCREENING", "FORM"),
            ("Entrevista", "INTERVIEW", "INTERVIEW"), ("Teste", "TEST", "TEST"),
            ("Finalistas", "FINALIST", "ADMISSION"),
        ]):
            db.add(PipelineStage(vacancy_id=vacancy.id, name=name, kind=kind,
                candidate_phase=phase, position=position, required=phase in {"SELECTION", "FORM", "INTERVIEW", "TEST"}))
    else:
        phases = {stage_phase(db, stage) for stage in stages}
        if "RECRUITMENT" not in phases or "SELECTION" not in phases or not {"INTERVIEW", "TEST"} <= phases:
            raise DomainError("Configure recrutamento, seleção, entrevista e teste antes de ativar o fluxo completo.")
        if "FORM" not in phases:
            insertion = next((i for i, stage in enumerate(stages) if stage_phase(db, stage) == "INTERVIEW"), len(stages))
            stages.insert(insertion, PipelineStage(vacancy_id=vacancy.id, name="Perguntas e ficha externa",
                kind="SCREENING", candidate_phase="FORM", required=True))
        if "REGISTER" not in phases:
            stages.insert(0, PipelineStage(vacancy_id=vacancy.id, name="Cadastro", kind="SCREENING", candidate_phase="REGISTER"))
        for stage in stages:
            if not stage.candidate_phase:
                stage.candidate_phase = stage_phase(db, stage)
        order = {"REGISTER": 0, "RECRUITMENT": 1, "SELECTION": 2, "FORM": 3,
                 "INTERVIEW": 4, "TEST": 5, "ADMISSION": 6}
        stages.sort(key=lambda stage: order.get(stage.candidate_phase, 6))
        # Move to temporary positions first to preserve the unique position constraint.
        offset = max(stage.position for stage in stages if stage.position is not None) + len(stages) + 1
        for stage in stages:
            if stage.id:
                stage.position += offset
        db.flush()
        for position, stage in enumerate(stages):
            stage.position = position
            if stage.candidate_phase in {"SELECTION", "FORM", "INTERVIEW", "TEST"} or stage.kind in {"INTERVIEW", "TEST"}:
                stage.required = True
            db.add(stage)
    vacancy.details = vacancy.details | {"structured_workflow": True}
    db.flush()


def workflow_blockers(db, application, vacancy, current, target):
    if not vacancy.details.get("structured_workflow") or target.position <= current.position:
        return []
    phase = stage_phase(db, current)
    blockers = []
    next_stage = db.scalar(select(PipelineStage).where(PipelineStage.vacancy_id == vacancy.id,
        PipelineStage.position > current.position).order_by(PipelineStage.position).limit(1))
    if next_stage and target.id != next_stage.id:
        blockers.append("Avance uma etapa por vez após concluir as atividades obrigatórias.")
    if phase == "REGISTER":
        candidate = db.get(Candidate, application.candidate_id)
        if not candidate.name.strip() or not candidate.email or not candidate.phone:
            blockers.append("Conclua o cadastro com nome, e-mail e telefone antes do recrutamento.")
    if phase == "RECRUITMENT":
        candidate = db.get(Candidate, application.candidate_id)
        cv = db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
            Document.type_name == "CURRICULO", Document.status != "REJECTED",
            Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"])))
        if not candidate.phone or not cv:
            blockers.append("Preencha o telefone e anexe um currículo válido antes da análise.")
    if phase == "SELECTION":
        review = db.scalar(select(StageReview).where(StageReview.application_id == application.id,
            StageReview.stage_id == current.id, StageReview.created_at >= application.stage_entered_at)
            .order_by(StageReview.created_at.desc(), StageReview.id.desc()).limit(1))
        if not review or review.status != "APPROVED":
            blockers.append("Registre a aprovação do currículo e a justificativa antes de avançar.")
    if phase == "FORM":
        from app.services.stage_tasks import stage_tasks
        pending = [task["title"] for task in stage_tasks(db, application)["tasks"] if task["status"] == "PENDING"]
        if pending:
            blockers.append("Aguarde a conclusão: " + ", ".join(pending) + ".")
    if phase == "INTERVIEW":
        evaluations = db.scalars(select(Evaluation).where(Evaluation.application_id == application.id)).all()
        review = db.scalar(select(StageReview).where(StageReview.application_id == application.id,
            StageReview.stage_id == current.id, StageReview.created_at >= application.stage_entered_at)
            .order_by(StageReview.created_at.desc(), StageReview.id.desc()).limit(1))
        validated = review and review.status == "APPROVED"
        if review and review.status != "APPROVED":
            blockers.append("Valide a entrevista com parecer favorável antes de avançar.")
        elif not validated and (not evaluations or any(not e.submitted_at or e.recommendation != "ADVANCE" for e in evaluations)):
            blockers.append("Clique em Validar entrevista com gestor e confirme a aprovação para avançar.")
        from app.services.stage_tasks import stage_tasks
        if stage_tasks(db, application)["pending"]:
            blockers.append("Conclua os agendamentos de entrevista pendentes antes de avançar.")
    return blockers
