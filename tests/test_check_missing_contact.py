"""MISSING_CONTACT fails only when neither an email nor a phone is found."""
import pytest

from checks import check_missing_contact

BODY = "EXPERIENCE\nSoftware Engineer, Acme Widgets 2020 - 2024\n- Built an internal tool.\n"


@pytest.mark.parametrize(
    "header",
    [
        "Jane Testperson | jane.testperson@example.com | 555-010-1234",
        "Jane Testperson | jane.testperson@example.com",
        "Jane Testperson | (555) 010-1234",
        "Jane Testperson | +1 555.010.1234",
        "Jane Testperson | 555 010 1234",
    ],
    ids=["both", "email-only", "phone-parens", "phone-intl-dots", "phone-spaces"],
)
def test_passes_when_an_email_or_a_phone_is_present(header):
    result = check_missing_contact(f"{header}\n{BODY}")

    assert result.component == "missing_contact"
    assert result.value == 1
    assert result.issues == []


def test_fails_when_neither_email_nor_phone_is_present():
    result = check_missing_contact(f"Jane Testperson | Springfield\n{BODY}")

    assert result.value == 0
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "MISSING_CONTACT"
    assert issue.snippet is None  # document-level
    assert issue.line_id is None


def test_date_ranges_and_years_are_not_mistaken_for_a_phone():
    text = "Jane Testperson\nEXPERIENCE\nAcme 2019 - 2020, 2021-2024\nZIP 12345\n"

    assert check_missing_contact(text).value == 0
