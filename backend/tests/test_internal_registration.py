import json

from sqlalchemy import select
from test_candidate_journey import register_basic_candidate
from test_integration import call

from app.core.security import decrypt
from app.models import Role, SensitiveData, UserRole

PATH = "/candidates/me/internal-registration"


def employee(client, db):
    headers, candidate, _ = register_basic_candidate(client)
    role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
    db.add(UserRole(user_id=candidate["user_id"], role_id=role.id))
    db.commit()
    return headers, candidate


def test_internal_profile_roundtrip_is_encrypted_private_and_versioned(client, db, actors):
    owner, candidate = employee(client, db)
    outside, _, _ = register_basic_candidate(client)
    assert call(client, "get", PATH, owner)["data"] is None
    data = {"personal": {"name": "Pessoa Teste", "employee_number": "TEST123"},
            "bank": {"checking_account": "PRIVATE123"},
            "employment": {"department": "Operações", "position": "Assistente", "excel": True},
            "motivation": "Aprender e crescer profissionalmente.",
            "transport": [{"daily_quantity": 2, "transport": "Ônibus", "fare": 5.5}]}
    saved = call(client, "put", PATH, owner, {"data": data, "version": 0})
    assert saved["data"]["employment"]["excel"] is True
    assert saved["version"] == 1 and saved["confirmed_at"] is None
    assert call(client, "get", PATH, owner) == saved
    stored = db.scalar(select(SensitiveData).where(SensitiveData.candidate_id == candidate["id"]))
    assert "PRIVATE123" not in stored.encrypted_data
    assert json.loads(decrypt(stored.encrypted_data))["internal_registration"]["form_code"] == "FORM-PPO-RH-002.01"
    call(client, "get", PATH, outside, expected=403)
    call(client, "get", PATH, actors["manager"]["headers"], expected=403)
    call(client, "get", PATH, {}, expected=401)
    call(client, "put", PATH, owner, {"data": data, "version": 0}, 409)
    other, _ = employee(client, db)
    assert call(client, "get", PATH, other)["data"] is None


def test_employee_resume_upload_is_available_before_enrollment(client, db):
    from types import SimpleNamespace

    from app.models import User
    from app.services.candidate_journey import require_candidate_section

    _, candidate = employee(client, db)
    user = db.get(User, candidate["user_id"])
    require_candidate_section(db, SimpleNamespace(user=user, permissions={"internal.view"}), "resume")
    require_candidate_section(db, SimpleNamespace(user=user, permissions=set()), "resume")


def test_internal_profile_validates_dates_limits_and_keeps_manager_fields_separate(client, db, actors):
    import base64
    from io import BytesIO

    from PIL import Image, ImageDraw

    owner, _ = employee(client, db)
    for data in [{"employment": {"vacation_start": "2026-12-10", "vacation_end": "2026-12-01"}},
                 {"dependents": [{}] * 7}, {"transport": [{}] * 4},
                 {"manager_recommendation": "Aprovado"}, {"declaration": {"accepted": True}}]:
        call(client, "put", PATH, owner, {"data": data, "version": 0}, 422)
    image = Image.new("RGBA", (900, 220), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    blank = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    call(client, "put", PATH, owner, {"data": {"declaration": {"signature_image": blank}}, "version": 0}, 422)
    ImageDraw.Draw(image).line([(40, 120), (110, 60), (160, 140), (250, 110)], fill="black", width=3)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    signature = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    declaration = {"accepted": True, "place": "Barcarena", "date": "2026-10-15", "signature_name": "Pessoa Teste"}
    call(client, "put", PATH, owner, {"data": {"declaration": declaration}, "version": 0}, 422)
    result = call(client, "put", PATH, owner, {"data": {"declaration": {**declaration, "signature_image": signature}}, "version": 0})
    assert result["confirmed_at"]
    assert call(client, "get", PATH, owner)["data"]["declaration"]["signature_image"] == signature
    from pypdf import PdfReader

    candidate = call(client, "get", "/candidates/me", owner)
    root = "/candidates/" + candidate["id"]
    metadata = call(client, "get", root + "/internal-profile-downloads", actors["admin"]["headers"])
    assert metadata["available"] and metadata["confirmed_at"] and metadata["resume"] is None
    pdf = client.get("/api/v1" + root + "/internal-registration.pdf", headers=actors["admin"]["headers"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    document = PdfReader(BytesIO(pdf.content))
    text = " ".join(page.extract_text() for page in document.pages)
    assert "FORM-PPO-RH-002.01" in text and "Pessoa Teste" in text and "Declarações confirmadas" in text
    assert sum(len(page.images) for page in document.pages) == 1
    import zipfile

    import openpyxl

    from app.services.internal_profile_xlsx import TEMPLATE

    excel = client.get("/api/v1" + root + "/internal-registration.xlsx", headers=actors["admin"]["headers"])
    assert excel.status_code == 200
    assert excel.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    workbook = openpyxl.load_workbook(BytesIO(excel.content))
    sheet = workbook.worksheets[1]
    assert sheet["G109"].value == "Pessoa Teste"
    assert sheet["A107"].value == "Barcarena, 15/10/2026"
    assert len(sheet._images) == 2  # Original logo plus the saved signature.
    assert "RECOMENDAÇÕES DO GESTOR" in sheet["A77"].value
    with zipfile.ZipFile(TEMPLATE) as original, zipfile.ZipFile(BytesIO(excel.content)) as filled:
        assert original.read("xl/worksheets/sheet1.xml") == filled.read("xl/worksheets/sheet1.xml")
        assert filled.read("xl/media/employee-signature.png") == base64.b64decode(signature.split(",")[1])
    call(client, "get", root + "/internal-registration.xlsx", owner, expected=403)
    call(client, "get", root + "/internal-registration.pdf", owner, expected=403)
    call(client, "get", root + "/internal-registration.pdf", actors["outsider"]["headers"], expected=404)
    call(client, "get", root + "/internal-registration.pdf", {}, expected=401)
