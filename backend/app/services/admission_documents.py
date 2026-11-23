"""Checklist from FORM-PPO-RH-002.06, provided by RH."""

from sqlalchemy import select

from app.models import Application


def admission_can_release(db, candidate):
    if not candidate:
        return False
    from app.services.candidate_journey import application_permissions
    return any(application_permissions(db, application)["permissions"]["admission"] for application in
        db.scalars(select(Application).where(Application.candidate_id == candidate.id)))


def admission_eligible(db, candidate):
    if not candidate:
        return False
    return admission_can_release(db, candidate)

ADMISSION_DOCUMENTS = [
    ("CTPS", "CTPS digital", "Com informações dos dois últimos empregos."),
    ("CERTIDAO", "Certidão de nascimento, casamento ou declaração de união estável", ""),
    ("RG", "RG", "A CNH não substitui o RG."),
    ("CPF", "CPF", ""),
    ("PIS", "Extrato PIS ou cartão cidadão", ""),
    ("REGISTRO_PROFISSIONAL", "Carteira de habilitação profissional", "Válida, para profissões regulamentadas (OAB, CREA etc.)."),
    ("TITULO", "Título de eleitor", ""),
    ("RESERVISTA", "Certificado de reservista", ""),
    ("CNH", "Carteira Nacional de Habilitação (CNH)", "Não substitui o RG."),
    ("CNS", "Carteira Nacional de Saúde (CNS)", ""),
    ("VACINACAO", "Carteira de vacinação", "Tétano, Hepatite B, Febre Amarela e COVID-19 (duas doses), conforme a relação do RH."),
    ("SANGUE", "Tipagem sanguínea", ""),
    ("RESIDENCIA", "Comprovante de residência", ""),
    ("ESCOLARIDADE", "Comprovante de escolaridade", ""),
    ("TREINAMENTOS", "Certificados de treinamentos normativos", "Para cargos operacionais. Reúna os certificados em um único PDF."),
    ("BANCO", "Dados bancários", "Comprovante de abertura de conta Bradesco."),
    ("PCD", "Carteira de PCD e laudo médico atualizado", "Para candidatos com deficiência. Reúna os documentos em um único PDF."),
    ("DEP_CASAMENTO", "Certidão de casamento ou documento de união estável", "Documento registrado em cartório."),
    ("DEP_CONJUGE", "RG e CPF do cônjuge", "Reúna os documentos em um único PDF."),
    ("DEP_NASCIMENTO", "Certidão de nascimento dos filhos", "Inclua todos os filhos em um único PDF."),
    ("DEP_IDENTIDADE", "RG e CPF dos filhos", "Inclua todos os filhos em um único PDF."),
    ("DEP_CNS", "Carteira Nacional de Saúde do cônjuge e dos filhos", "Reúna os documentos em um único PDF."),
    ("DEP_VACINACAO", "Carteira de vacinação dos filhos", "Para filhos menores de sete anos. Reúna os documentos em um único PDF."),
    ("DEP_ESCOLA", "Declaração de frequência escolar dos filhos", "De sete anos e um dia até 14 anos. Reúna as declarações em um único PDF."),
]

ADMISSION_CATALOG = [
    {"type_name": "ADM_" + code, "title": title, "description": description,
     "group": "Dependentes" if code.startswith("DEP_") else "Candidato",
     "optional": code.startswith("DEP_")}
    for code, title, description in ADMISSION_DOCUMENTS
]
ADMISSION_TYPES = {item["type_name"] for item in ADMISSION_CATALOG}


def admission_submission_complete(documents):
    latest = {}
    for document in documents:
        latest.setdefault(document.type_name, document)
    required = [item for item in ADMISSION_CATALOG if not item.get("optional")]
    return bool(required) and all(
        item["type_name"] in latest
        and latest[item["type_name"]].status not in {"REJECTED", "REMOVED"}
        and latest[item["type_name"]].scan_status in {"CLEAN", "NOT_CONFIGURED"}
        for item in required)


def candidate_documents_complete(db, candidate_id):
    from app.models import Document
    documents = db.scalars(select(Document).where(Document.candidate_id == candidate_id,
        Document.type_name.in_(ADMISSION_TYPES), Document.scan_status != "DELETED")
        .order_by(Document.created_at.desc())).all()
    return admission_submission_complete(documents)
