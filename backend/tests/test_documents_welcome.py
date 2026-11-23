from types import SimpleNamespace
from app.services.admission_documents import ADMISSION_CATALOG, admission_submission_complete


def documents():
    return [SimpleNamespace(type_name=item["type_name"], status="PENDING", scan_status="CLEAN")
            for item in ADMISSION_CATALOG if not item["optional"]]


def test_welcome_requires_valid_required_uploads_but_not_optional_dependents():
    submitted = documents()
    assert len(submitted) == 17
    assert admission_submission_complete(submitted)
    assert not admission_submission_complete(submitted[:-1])
    assert not admission_submission_complete([])
    submitted[0].status = "REJECTED"
    assert not admission_submission_complete(submitted)


def test_rejected_or_unscanned_latest_document_does_not_use_older_upload():
    submitted = documents()
    latest = SimpleNamespace(type_name=submitted[0].type_name, status="REJECTED", scan_status="CLEAN")
    assert not admission_submission_complete([latest] + submitted)
    latest.status = "PENDING"
    latest.scan_status = "PENDING"
    assert not admission_submission_complete([latest] + submitted)
