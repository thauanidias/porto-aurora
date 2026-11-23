from datetime import datetime, UTC
from io import BytesIO
from openpyxl import load_workbook
from test_candidate_journey import journey_owner, enroll  # noqa: F401
from test_integration import call
from app.models import Vacancy


def test_monthly_and_single_vacancy_excel_with_scope_and_safe_text(client, db, journey_owner, actors):
    owner, job, admin, _ = journey_owner
    enroll(client, owner, job)
    vacancy = db.get(Vacancy, job["id"])
    vacancy.published_at = datetime(2026, 11, 1, 3, 0, tzinfo=UTC)
    vacancy.title = "=FAKE()"
    db.commit()
    assert call(client, "get", "/analytics/vacancies?month=2026-10", admin)["total"] == 0
    assert call(client, "get", "/analytics/vacancies?month=2026-11", admin)["total"] == 1
    response = client.get("/api/v1/analytics/vacancies/export.xlsx?month=2026-11", headers=admin)
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    workbook = load_workbook(BytesIO(response.content), data_only=True)
    summary = workbook["Resumo"]
    assert summary.sheet_view.showGridLines is False
    assert summary.column_dimensions["A"].width >= 50
    assert "Novembro de 2026" in summary["A2"].value
    assert summary["A1"].font.sz == 16
    assert summary["A4"].font.color.rgb == "FFFFFFFF"
    assert summary["B5"].font.bold
    assert summary.auto_filter.ref is None
    assert summary.page_setup.orientation == "portrait"
    assert workbook.sheetnames == ["Resumo", "Vagas", "Candidaturas", "Histórico de etapas"]
    assert workbook["Vagas"]["B5"].value == "=FAKE()"
    assert workbook["Vagas"]["B5"].data_type == "s"
    assert workbook["Vagas"]["G5"].value == 1
    assert workbook["Vagas"].freeze_panes == "A5"
    assert workbook["Candidaturas"]["C5"].value == "Pessoa da Jornada"
    single = client.get("/api/v1/analytics/vacancies/export.xlsx?vacancy_id=" + job["id"], headers=admin)
    assert single.status_code == 200
    assert load_workbook(BytesIO(single.content))["Vagas"].max_row == 5
    assert client.get("/api/v1/analytics/vacancies/export.xlsx?month=2026-11", headers=owner).status_code == 403
    assert client.get("/api/v1/analytics/vacancies/export.xlsx?vacancy_id=" + job["id"], headers=actors["outsider"]["headers"]).status_code in {403, 404}
    assert client.get("/api/v1/analytics/vacancies/export.xlsx?month=2026-99", headers=admin).status_code in {400, 422}
