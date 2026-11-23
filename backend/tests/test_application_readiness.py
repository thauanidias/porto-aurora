from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.errors import DomainError
from app.services.application_readiness import application_readiness, require_application_ready


def candidate(**changes):
    data = dict(id="candidate", name="Pessoa Teste", phone="91999999999", city="Belém", state="PA", country="BR",
        profile={"education": [{"course": "Ensino médio"}], "skills": ["Informática"], "shift": "Manhã"})
    return SimpleNamespace(**(data | changes))


def test_requires_saved_profile_and_validated_resume():
    db = Mock()
    db.scalar.return_value = None
    incomplete = candidate(phone="", city="", profile={})
    result = application_readiness(db, incomplete)
    assert not result["ready"]
    for field in ["Telefone", "Cidade", "Formação", "Competências", "Turno disponível", "Currículo anexado e validado"]:
        assert field in result["missing"]
    with pytest.raises(DomainError) as error:
        require_application_ready(db, incomplete)
    assert error.value.code == "PROFILE_INCOMPLETE"


def test_resume_alone_does_not_allow_application():
    db = Mock()
    db.scalar.return_value = "clean-resume"
    assert not application_readiness(db, candidate(profile={}))["ready"]


def test_complete_profile_still_requires_resume():
    db = Mock()
    db.scalar.return_value = None
    assert application_readiness(db, candidate())["missing"] == ["Currículo anexado e validado"]
    db.scalar.return_value = "clean-resume"
    assert require_application_ready(db, candidate()) == {"ready": True, "missing": [], "cv_id": "clean-resume"}


def test_first_job_does_not_require_experience_or_certifications():
    db = Mock()
    db.scalar.return_value = "clean-resume"
    assert application_readiness(db, candidate())["ready"]


def test_empty_imported_education_draft_does_not_unlock_enrollment():
    db = Mock()
    db.scalar.return_value = "clean-resume"
    person = candidate(profile={"education": [{"period_text": "2022"}], "skills": ["Excel"], "shift": "Manhã"})
    assert "Formação" in application_readiness(db, person)["missing"]
