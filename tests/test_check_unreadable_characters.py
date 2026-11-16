"""UNREADABLE_CHARACTERS counts (cid:NN) markers, private-use characters and U+FFFD."""
import pytest

import analysis_config
from checks import check_unreadable_characters
from conftest import document_from_text

CLEAN = "Jane Testperson\nEXPERIENCE\nSoftware Engineer, Acme 2020 - 2024\n"


def test_clean_text_passes():
    result = check_unreadable_characters(document_from_text(CLEAN))

    assert result.component == "unreadable_characters"
    assert result.value == 1
    assert result.issues == []


@pytest.mark.parametrize(
    "bad",
    [
        "(cid:12)",
        "(cid:1)(cid:2)(cid:3)",
        "",  # start of the private-use area
        "",  # end of the private-use area
        "\U000f0001",  # supplementary private-use area
        "�",
    ],
    ids=["cid", "cid-run", "pua-start", "pua-end", "pua-supplementary", "replacement"],
)
def test_fails_on_any_unreadable_character(bad):
    result = check_unreadable_characters(document_from_text(f"{CLEAN}Phone {bad} 555\n"))

    assert result.value == 0
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "UNREADABLE_CHARACTERS"
    assert issue.snippet is None and issue.line_id is None  # document-level


def test_description_gives_the_count_and_never_quotes_the_text():
    result = check_unreadable_characters(document_from_text(f"{CLEAN}(cid:7) (cid:8) �\n"))

    issue = result.issues[0]
    assert "3" in issue.description
    assert "cid" not in issue.description and "Testperson" not in issue.description


def test_ordinary_non_ascii_text_is_not_unreadable():
    text = f"{CLEAN}Zoë Müller, São Paulo – café ‘quoted’ • bullet\n"

    assert check_unreadable_characters(document_from_text(text)).value == 1


def test_the_minimum_count_is_config(monkeypatch):
    monkeypatch.setattr(analysis_config, "UNREADABLE_MIN_COUNT", 2)

    one = document_from_text(f"{CLEAN}�\n")
    two = document_from_text(f"{CLEAN}��\n")

    assert check_unreadable_characters(one).value == 1
    assert check_unreadable_characters(two).value == 0
