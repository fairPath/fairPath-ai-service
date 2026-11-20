"""TOO_LONG fails when a Resume has more pages than MAX_PAGES."""
import pytest

import analysis_config
from checks import check_too_long
from conftest import document_from_text


@pytest.mark.parametrize("pages", [1, 2])
def test_passes_at_or_under_the_page_limit(pages):
    result = check_too_long(document_from_text("text", page_count=pages))

    assert result.component == "too_long"
    assert result.value == 1
    assert result.issues == []


@pytest.mark.parametrize("pages", [3, 5])
def test_fails_over_the_page_limit(pages):
    result = check_too_long(document_from_text("text", page_count=pages))

    assert result.value == 0
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "TOO_LONG"
    assert str(pages) in issue.description
    assert issue.snippet is None and issue.line_id is None  # document-level


def test_the_limit_is_config(monkeypatch):
    monkeypatch.setattr(analysis_config, "MAX_PAGES", 1)

    assert check_too_long(document_from_text("text", page_count=2)).value == 0
