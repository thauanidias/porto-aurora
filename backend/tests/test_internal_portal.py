from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from test_integration import call, register_candidate, setup_vacancy

from app.core.db import utcnow
from app.models import Document, Role, UserRole, Vacancy


def test_internal_filters_and_audience_are_applied_together(client, db, actors):
    suffix = uuid4().hex[:8]
    for index, (audience, city, modality) in enumerate([
        ("INTERNAL", "Barcarena", "PRESENCIAL"),
        ("INTERNAL", "Belem", "REMOTO"),
        ("EXTERNAL", "Barcarena", "PRESENCIAL"),
        ("BOTH", "Barcarena", "PRESENCIAL"),
    ]):
        db.add(Vacancy(code=f"FILTER-{suffix}-{index}", slug=f"filter-{suffix}-{index}", title=f"Analista {suffix}",
                       org_unit_id=actors["org"], recruiter_id=actors["admin"]["id"], manager_id=actors["manager"]["id"],
                       audience=audience, city=city, modality=modality, status="PUBLISHED",
                       description="Logistica " + suffix, deadline=utcnow() + timedelta(days=10)))
    db.commit()
    path = "/internal/vacancies?q=" + suffix + "&city=Barcarena&modality=PRESENCIAL"
    call(client, "get", path, {}, expected=401)
    call(client, "get", path, actors["manager"]["headers"], expected=403)
    result = call(client, "get", path, actors["admin"]["headers"])
    assert result["total"] == 2
    assert {row["audience"] for row in result["items"]} == {"INTERNAL", "BOTH"}
    visible = call(client, "get", "/public/internal-vacancies?q=" + suffix + "&city=Barcarena&modality=PRESENCIAL", {})
    assert visible["total"] == 2
    assert {row["audience"] for row in visible["items"]} == {"INTERNAL", "BOTH"}
    assert call(client, "get", "/internal/vacancies?q=Logistica%20" + suffix, actors["admin"]["headers"])["total"] == 3
    public = call(client, "get", "/public/vacancies?q=" + suffix, {})
    assert public["total"] == 2
    assert all(row["audience"] != "INTERNAL" for row in public["items"])
    directory = "/vacancies?q=" + suffix + "&status=PUBLISHED&audience=INTERNAL"
    listed = call(client, "get", directory, actors["admin"]["headers"])
    assert listed["total"] == 2
    assert all(row["audience"] == "INTERNAL" for row in listed["items"])
    assert call(client, "get", directory, actors["outsider"]["headers"])["total"] == 0
    assert call(client, "get", directory.replace("PUBLISHED", "CLOSED"), actors["admin"]["headers"])["total"] == 0


def test_employee_can_apply_and_follow_internal_vacancy(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    row = db.get(Vacancy, vacancy["id"])
    row.audience = "INTERNAL"
    db.flush()
    headers, profile, _ = register_candidate(client, notice)
    call(client, "get", "/public/vacancies/" + row.slug, {}, expected=404)
    call(client, "get", "/internal/vacancies/" + row.slug, {}, expected=401)
    call(client, "post", "/applications", headers, {"vacancy_id": row.id, "enrollment": True}, 403)
    role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
    db.add(UserRole(user_id=profile["user_id"], role_id=role.id))
    db.flush()
    call(client, "get", "/internal/vacancies/" + row.slug, headers)
    application = call(client, "post", "/applications", headers, {"vacancy_id": row.id, "enrollment": True}, 201)
    detail = call(client, "get", "/applications/" + application["id"], headers)
    assert detail["vacancy_id"] == row.id
    assert detail["recruitment_type"] == "INTERNAL"


def test_internal_application_reuses_only_own_validated_resume(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    db.get(Vacancy, vacancy["id"]).audience = "INTERNAL"
    headers, candidate, _ = register_candidate(client, notice)
    _, other, _ = register_candidate(client, notice)
    role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
    db.add(UserRole(user_id=candidate["user_id"], role_id=role.id))
    now = utcnow()

    def document(person, kind, scan, status, days):
        item = Document(candidate_id=person["id"], uploaded_by=person["user_id"], type_name=kind,
            filename="teste.pdf", storage_key=uuid4().hex, sha256=uuid4().hex, size=20, mime="application/pdf",
            revision=1, scan_status=scan, status=status, created_at=now + timedelta(days=days))
        db.add(item)
        return item

    expected = document(candidate, "CURRICULO", "CLEAN", "APPROVED", -3)
    document(candidate, "CURRICULO", "PENDING", "PENDING", -1)
    document(candidate, "CURRICULO", "CLEAN", "REJECTED", 0)
    document(candidate, "CERTIFICADO", "CLEAN", "APPROVED", 1)
    document(other, "CURRICULO", "CLEAN", "APPROVED", 2)
    db.flush()
    before = len(list(db.scalars(select(Document.id))))
    application = call(client, "post", "/applications", headers, {"vacancy_id": vacancy["id"], "enrollment": True}, 201)
    assert application["cv_id"] == expected.id
    assert len(list(db.scalars(select(Document.id)))) == before


def test_rh_application_lists_separate_both_audiences_and_preserve_origin(client, db, actors):
    vacancy, notice, _, _ = setup_vacancy(client, actors)
    row = db.get(Vacancy, vacancy["id"])
    row.audience = "BOTH"
    db.commit()
    external, _, _ = register_candidate(client, notice)
    outside = call(client, "post", "/applications", external, {"vacancy_id": row.id, "enrollment": True}, 201)
    employee, profile, _ = register_candidate(client, notice)
    role = db.scalar(select(Role).where(Role.name == "COLABORADOR"))
    db.add(UserRole(user_id=profile["user_id"], role_id=role.id))
    db.commit()
    inside = call(client, "post", "/applications", employee, {"vacancy_id": row.id, "enrollment": True}, 201)
    assert outside["recruitment_type"] == "EXTERNAL"
    assert inside["recruitment_type"] == "INTERNAL"
    root = "/applications?vacancy_id=" + row.id
    for kind, expected in [("INTERNAL", inside["id"]), ("EXTERNAL", outside["id"])]:
        result = call(client, "get", root + "&recruitment_type=" + kind, actors["admin"]["headers"])
        assert result["total"] == 1
        assert result["items"][0]["id"] == expected
        assert call(client, "get", root + "&recruitment_type=" + kind, actors["outsider"]["headers"])["total"] == 0
    assert call(client, "get", root + "&recruitment_type=INTERNAL", external)["total"] == 0
    assert call(client, "get", root + "&recruitment_type=EXTERNAL&status=REJECTED", actors["admin"]["headers"])["total"] == 0
    assert call(client, "get", root + "&recruitment_type=INTERNAL&q=not-a-matching-name", actors["admin"]["headers"])["total"] == 0
    call(client, "get", root + "&recruitment_type=INTERNAL", {}, expected=401)
    row.audience = "EXTERNAL"
    db.commit()
    assert call(client, "get", root + "&recruitment_type=INTERNAL", actors["admin"]["headers"])["items"][0]["id"] == inside["id"]
