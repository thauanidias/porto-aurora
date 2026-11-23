from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.api.assessments import AssignInput


def assignment(link):
    now = datetime.now(timezone.utc)
    return AssignInput(application_id="application", opens_at=now,
                       due_at=now + timedelta(days=1), external_url=link)


def test_external_test_link_preserves_personal_query_and_allows_internal_test():
    assert assignment(" https://tests.example.com/exam?token=person ").external_url == "https://tests.example.com/exam?token=person"
    assert assignment("").external_url == ""


@pytest.mark.parametrize("link", ["javascript:alert(1)", "file:///test", "https://user:secret@example.com", "not a link"])
def test_external_test_link_rejects_unsafe_or_invalid_urls(link):
    with pytest.raises(ValidationError):
        assignment(link)
