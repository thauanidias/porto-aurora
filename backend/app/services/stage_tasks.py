"""Task completion from recorded submissions, separate from the RH approval decision."""
import json
from sqlalchemy import select
from app.core.security import decrypt
from app.models import CandidateActivityLink, Candidate, Document, Interview, InterviewParticipant, ProcessForm, SensitiveData, TestAssignment, TestAttempt, Vacancy
from app.services.candidate_journey import application_permissions, questions_completed


def stage_tasks(db, application):
    phase = application_permissions(db, application)["phase"]
    tasks = []

    def add(key, title, complete, detail, tab, applicable=True):
        tasks.append({"key": key, "title": title, "status": "NOT_APPLICABLE" if not applicable else "COMPLETED" if complete else "PENDING", "detail": detail, "tab": tab})

    if phase in {"REGISTER", "RECRUITMENT", "SELECTION"}:
        document = db.scalar(select(Document).where(Document.candidate_id == application.candidate_id,
            Document.type_name == "CURRICULO", Document.status != "REJECTED", Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"])).limit(1))
        add("resume", "Currículo", bool(document), "Currículo enviado; aguarda análise do RH." if document else "O candidato ainda precisa enviar um currículo válido.", "profile")
    elif phase == "FORM":
        row = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == application.candidate_id))
        saved = json.loads(decrypt(row.encrypted_data)) if row and row.encrypted_data else {}
        internal = application.recruitment_type == "INTERNAL"
        registration = saved.get("internal_registration" if internal else "selection_registration", {})
        signed = bool(registration.get("confirmed_at") and registration.get("data", {}).get("declaration", {}).get("signature_image"))
        if not internal:
            signed = signed and bool((registration.get("signature_record") or {}).get("protocol"))
        vacancy = db.get(Vacancy, application.vacancy_id)
        form = db.scalar(select(ProcessForm).where(ProcessForm.application_id == application.id))
        questions = form.questions if form else vacancy.details.get("questions", []) if vacancy else []
        answers = application.answers or {}
        required = [q for q in questions if q.get("required")]
        answered = questions_completed(db, application)
        add("questions", "Perguntas da vaga", answered,
            "Respostas enviadas. Clique para consultar." if answered else "O candidato ainda precisa concluir as respostas." if questions else "Esta vaga não possui perguntas configuradas.", "selection", bool(questions))
        add("registration", "Ficha interna" if internal else "Ficha externa assinada", signed,
            "Ficha concluída e assinada. Disponível para conferência do RH." if signed else "Rascunho salvo; falta concluir e assinar." if registration.get("data") else "O candidato ainda não enviou a ficha assinada." if answered or internal else "Será liberada automaticamente após o envio das respostas às perguntas do RH.", "selection")
    elif phase == "INTERVIEW":
        interviews = db.scalars(select(Interview).join(InterviewParticipant, InterviewParticipant.interview_id == Interview.id).where(InterviewParticipant.application_id == application.id)).all()
        interviews = [item for item in interviews if item.status not in {"CANCELED", "CANCELLED"}]
        add("interview", "Participação na entrevista", bool(interviews) and all(item.status == "COMPLETED" for item in interviews),
            "Consulte os registros da entrevista e as avaliações do RH." if interviews else "Nenhuma entrevista registrada para esta candidatura.", "activities")
    elif phase == "TEST":
        assignments = db.scalars(select(TestAssignment).where(TestAssignment.application_id == application.id)).all()
        for assignment in assignments:
            attempt = db.scalar(select(TestAttempt).where(TestAttempt.assignment_id == assignment.id).order_by(TestAttempt.number.desc()).limit(1))
            submitted = bool(attempt and (attempt.submitted_at or attempt.status in {"SUBMITTED", "GRADED"}))
            add("test-" + assignment.id, (assignment.snapshot or {}).get("title") or (assignment.snapshot or {}).get("name") or "Teste da candidatura", submitted,
                "Entrega recebida; consulte as respostas e a correção." if submitted else "O candidato ainda não concluiu o teste.", "activities")
        links = db.scalars(select(CandidateActivityLink).where(CandidateActivityLink.application_id == application.id, CandidateActivityLink.kind == "TEST", CandidateActivityLink.active.is_(True))).all()
        for link in links:
            add("external-test-" + link.id, link.title, bool(link.completed_at),
                "Conclusão informada pelo candidato; confira o resultado na plataforma do teste." if link.completed_at else "O candidato ainda não confirmou a conclusão deste teste.", "activities")
        if not assignments and not links:
            add("tests", "Testes da candidatura", False, "Nenhum teste atribuído. Configure a atividade antes de solicitar a realização.", "activities")
    elif phase == "ADMISSION":
        from app.services.admission_documents import ADMISSION_CATALOG
        documents = db.scalars(select(Document).where(Document.candidate_id == application.candidate_id, Document.scan_status != "DELETED").order_by(Document.created_at.desc())).all()
        latest = {}
        for document in documents: latest.setdefault(document.type_name, document)
        for item in ADMISSION_CATALOG:
            document = latest.get(item["type_name"])
            sent = bool(document and document.status not in {"REJECTED", "REMOVED"} and document.scan_status in {"CLEAN", "NOT_CONFIGURED"})
            add("document-" + item["type_name"], item["title"], sent, "Arquivo enviado; consulte a análise do RH." if sent else "Documento devolvido para correção." if document and document.status == "REJECTED" else "Documento opcional de dependentes; envio não obrigatório." if item.get("optional") else "Não enviado. Confira se este item se aplica ao candidato.", "checklist", not item.get("optional", False) or sent)
    applicable = [task for task in tasks if task["status"] != "NOT_APPLICABLE"]
    completed = sum(task["status"] == "COMPLETED" for task in applicable)
    return {"tasks": tasks, "completed": completed, "pending": len(applicable) - completed,
            "status": "COMPLETED" if applicable and completed == len(applicable) else "PENDING" if applicable else "NOT_APPLICABLE"}
