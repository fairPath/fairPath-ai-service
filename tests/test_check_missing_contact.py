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


# Known gap: PHONE_PATTERN is deliberately NANP (US/Canada) only for now.
# A resume whose only contact is a non-US number gets a false MISSING_CONTACT.
# Flip this (and widen PHONE_PATTERN) when international support is added.
@pytest.mark.xfail(reason="international phone formats not supported yet", strict=True)
@pytest.mark.parametrize(
    "phone",
    ["+44 20 7946 0958", "+61 2 9374 4000", "+33 1 42 68 53 00"],
    ids=["uk", "au", "fr"],
)
def test_non_us_phone_is_recognized(phone):
    assert check_missing_contact(f"Jane Testperson | {phone}\n{BODY}").value == 1
