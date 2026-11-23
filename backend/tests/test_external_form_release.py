from types import SimpleNamespace
from unittest.mock import Mock
from app.services.candidate_journey import application_permissions
from app.services.candidate_journey import candidate_permissions


def access(phase, review=None, status="ACTIVE"):
    db = Mock()
    db.get.return_value = SimpleNamespace(candidate_phase=phase)
    db.scalar.return_value = SimpleNamespace(status=review) if review else None
    application = SimpleNamespace(id="app", stage_id="stage", status=status)
    return application_permissions(db, application)["permissions"]["selection_registration"]


def test_external_form_requires_approval_during_screening():
    assert not access("RECRUITMENT", "APPROVED")
    assert not access("SELECTION")
    assert not access("SELECTION", "PENDING")
    assert not access("SELECTION", "REJECTED")
    assert access("SELECTION", "APPROVED")


def test_external_form_available_after_screening_but_not_rejection():
    assert access("FORM")
    assert access("INTERVIEW")
    assert access("TEST")
    assert not access("SELECTION", "APPROVED", "REJECTED")


def test_profile_available_without_application_and_external_form_hidden():
    permissions = candidate_permissions(Mock(), None)
    for section in ("basic_profile", "resume", "professional_profile", "sensitive_profile"):
        assert permissions[section]
    assert not permissions["selection_registration"]
