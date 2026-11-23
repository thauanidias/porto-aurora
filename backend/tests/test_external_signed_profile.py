import copy
import io
import zipfile
from xml.etree import ElementTree as ET

import pytest
from external_helpers import complete_data
from openpyxl import load_workbook
from sqlalchemy import func, select
from test_candidate_journey import journey_owner  # noqa: F401
from test_integration import call
from test_selection_registration import registration_owner  # noqa: F401

from app.models import ConsentReceipt
from app.services.external_profile_xlsx import TEMPLATE, external_profile_xlsx


def test_signed_original_contains_all_data_and_signature(client, actors, registration_owner, db):  # noqa: F811
    owner, candidate, _ = registration_owner
    payload = complete_data()
    payload["education"] = {"high_school": "Completo", "technical": "Incompleto", "technical_course": "Técnico em Informática"}
    payload["complementary"] = {"related_employee": "Não", "relationship": "NÃO", "flexible_hours": "Não", "hours_restrictions": "NÃO"}
    receipts_before = db.scalar(select(func.count()).select_from(ConsentReceipt))
    saved = call(client, "put", "/candidates/me/selection-registration", owner, {"data": payload, "version": 0})
    assert db.scalar(select(func.count()).select_from(ConsentReceipt)) == receipts_before
    assert saved["signature_record"]["protocol"].startswith("TGPM-FICHA-")
    path = f"/candidates/{candidate['id']}/selection-registration.xlsx"
    admin = actors["admin"]["headers"]
    assert call(client, "get", path.replace(".xlsx", "-download"), admin)["available"]
    response = client.get("/api/v1" + path, headers=admin)
    assert response.status_code == 200, response.text
    workbook = load_workbook(io.BytesIO(response.content))
    original = workbook.worksheets[0]
    assert original["D67"].value == "Completo  ( X )"
    assert original["F68"].value == "Incompleto  ( X )"
    assert original["H68"].value == "Curso: Técnico em Informática"
    assert original["A77"].value == "Grau de parentesco: Não se aplica"
    assert original["F78"].value == "Restrições: Nenhuma"
    assert original["B8"].value == payload["personal"]["name"]
    assert original["B26"].value == payload["dependents"][0]["name"]
    assert original["B28"].value == payload["dependents"][0]["cpf"]
    assert original["B28"].number_format == "@"
    assert original["E23"].value == "Agência: 1234"
    assert original.row_dimensions[26].hidden
    template = load_workbook(TEMPLATE)
    for row in [1, 2, 3, 4, 6, 7, 14, 15, 19, 20, 46, 47, 48, 60, 61, 65, 66, 73, 74]:
        assert original.row_dimensions[row].height == template.worksheets[0].row_dimensions[row].height
    assert original.column_dimensions['A'].width == template.worksheets[0].column_dimensions['A'].width
    assert len(original._images) == 2
    complete_text = "\n".join(str(cell.value or "") for row in workbook["Dados completos"] for cell in row)
    activity_chunks = [str(row[1].value or "") for row in workbook["Dados completos"] if "Principais atividades exercidas" in str(row[0].value)]
    assert "".join(activity_chunks) == payload["employment"]["description"]
    assert "Mae de Teste" in complete_text
    assert "Comprovante" in workbook.sheetnames
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        styles = ET.fromstring(archive.read("xl/styles.xml"))
        for style in styles.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}cellXfs"):
            children = [node.tag.rsplit("}", 1)[-1] for node in style]
            if "alignment" in children and "protection" in children:
                assert children.index("alignment") < children.index("protection")
        assert archive.read("xl/media/candidate-signature.png").startswith(b"\x89PNG")
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(name))
    docs = call(client, "get", f"/candidates/{candidate['id']}/selection-documents", admin)
    assert docs["registration"]["data"] == saved["data"]
    assert client.get("/api/v1" + path, headers=owner).status_code == 403
    assert client.get("/api/v1" + path, headers=actors["outsider"]["headers"]).status_code in {403, 404}
    tampered = copy.deepcopy(saved)
    tampered["data"]["personal"]["name"] = "Outro nome"
    with pytest.raises(ValueError, match="assinatura"):
        external_profile_xlsx(tampered)
    saved["data"]["declaration"]["accepted"] = False
    call(client, "put", "/candidates/me/selection-registration", owner, {"data": saved["data"], "version": 1})
    assert client.get("/api/v1" + path, headers=admin).status_code == 409


def test_cannot_confirm_incomplete_or_unsigned_form(client, registration_owner):  # noqa: F811
    owner, _, _ = registration_owner
    for field in ("signature_image",):
        payload = complete_data()
        payload["declaration"][field] = ""
        assert client.put("/api/v1/candidates/me/selection-registration", headers=owner, json={"data": payload, "version": 0}).status_code == 422
    payload = complete_data()
    payload["personal"]["name"] = ""
    assert client.put("/api/v1/candidates/me/selection-registration", headers=owner, json={"data": payload, "version": 0}).status_code == 422
