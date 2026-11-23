"""Prepare valid enrollment fixtures through the same APIs used by the candidate."""
from sqlalchemy import select

from app.models import Candidate, Document


def ready_candidate(client, headers):
    person = client.get("/api/v1/candidates/me", headers=headers).json()
    profile = {key: value for key, value in (person.get("profile") or {}).items() if key not in {"facts"}}
    profile.setdefault("education", [])
    if not profile["education"]:
        profile["education"] = [{"course": "Ensino medio", "institution": "Escola ficticia",
                                 "degree": "MEDIO", "status": "CONCLUIDO", "start": "2015-01-01", "end": "2018-12-01"}]
    if not profile.get("skills"):
        profile["skills"] = ["Operacao"]
    if not profile.get("shift"):
        profile["shift"] = "Manha"
    data = {key: person.get(key, "") for key in ["name", "phone", "city", "state", "country"]}
    data.update(phone=data["phone"] or "91999999999", city=data["city"] or "Belem",
                state=data["state"] or "PA", country=data["country"] or "BR", profile=profile, version=person["version"])
    saved = client.put("/api/v1/candidates/me", headers=headers, json=data)
    if saved.status_code == 403 and saved.json().get("code") == "CONSENT_REQUIRED":
        receipt = client.post("/api/v1/public/consent-receipts", headers=headers,
                              json={"name": person["name"], "email": person["email"],
                                    "context": "CADASTRO", "accepted": True, "read_to_end": True})
        assert receipt.status_code == 201, receipt.text
        saved = client.put("/api/v1/candidates/me", headers=headers, json=data)
    assert saved.status_code == 200, saved.text
    db = client.test_db
    candidate = db.get(Candidate, person["id"])
    if not db.scalar(select(Document.id).where(Document.candidate_id == candidate.id,
                                               Document.type_name == "CURRICULO",
                                               Document.scan_status.in_(["CLEAN", "NOT_CONFIGURED"]))):
        uploaded = client.post("/api/v1/documents", headers=headers, data={"type_name": "CURRICULO"},
                               files={"file": ("curriculo-teste.pdf", b"%PDF-1.4\n1 0 obj <<>> endobj\n%%EOF\n", "application/pdf")})
        assert uploaded.status_code == 201, uploaded.text
    return saved.json()
