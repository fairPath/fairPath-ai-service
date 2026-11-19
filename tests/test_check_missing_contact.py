"""MISSING_CONTACT fails only when neither an email nor a phone is found."""
import pytest

from checks import check_missing_contact
from conftest import document_from_text

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
    result = check_missing_contact(document_from_text(f"{header}\n{BODY}"))

    assert result.component == "missing_contact"
    assert result.value == 1
    assert result.issues == []


def test_fails_when_neither_email_nor_phone_is_present():
    result = check_missing_contact(document_from_text(f"Jane Testperson | Springfield\n{BODY}"))

    assert result.value == 0
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "MISSING_CONTACT"
    assert issue.snippet is None  # document-level
    assert issue.line_id is None


def test_date_ranges_and_years_are_not_mistaken_for_a_phone():
    text = "Jane Testperson\nEXPERIENCE\nAcme 2019 - 2020, 2021-2024\nZIP 12345\n"

    assert check_missing_contact(document_from_text(text)).value == 0


@pytest.mark.parametrize(
    "span",
    ["Acme 2020-01 - 2021-03", "Acme 01/2020 - 03/2021", "Acme 2019-06 to 2021-11 2022-01"],
    ids=["iso-range", "numeric-range", "iso-ranges-run-together"],
)
def test_month_year_date_ranges_are_not_mistaken_for_a_phone(span):
    text = f"Jane Testperson\nEXPERIENCE\n{span}\n"

    assert check_missing_contact(document_from_text(text)).value == 0


@pytest.mark.parametrize(
    "span",
    ["Acme 2019 - 2020 2021 12345", "Acme 2020-01 - 2021-03 2022-05 12345"],
    ids=["years-then-zip", "ranges-then-zip"],
)
def test_dates_followed_by_a_zip_are_not_mistaken_for_a_phone(span):
    assert check_missing_contact(document_from_text(f"Jane Testperson\n{span}\n")).value == 0


def test_a_phone_next_to_a_date_range_is_still_found():
    text = "Jane Testperson | 555-010-1234\nEXPERIENCE\nAcme 2020-01 - 2021-03\n"

    assert check_missing_contact(document_from_text(text)).value == 1


@pytest.mark.parametrize(
    "line",
    [
        "Phone 555-010-1234  555-010-5678",
        "Jane Testperson | 555-010-1234 | 555-010-5678",
        "555-010-1234 Springfield 12345",
        "Mobile 555 010 1234 Office 555 010 5678",
    ],
    ids=["two-spaced", "two-piped", "phone-then-zip", "two-labelled"],
)
def test_adjacent_numbers_are_checked_one_at_a_time(line):
    assert check_missing_contact(document_from_text(f"Jane Testperson\n{line}\n")).value == 1


@pytest.mark.parametrize(
    "phone",
    [
        "+44 20 7946 0958",
        "+61 2 9374 4000",
        "+33 1 42 68 53 00",
        "+49 30 12345678",
        "+91 98765 43210",
        "07911 123456",
        "555–010–1234",  # en dash, common in PDF extraction
        "555—010—1234",  # em dash
    ],
    ids=["uk", "au", "fr", "de", "in", "uk-local", "en-dash", "em-dash"],
)
def test_non_us_phone_and_dash_separators_are_recognized(phone):
    assert check_missing_contact(document_from_text(f"Jane Testperson | {phone}\n{BODY}")).value == 1


@pytest.mark.parametrize(
    "email",
    ["jane@example.com", "jane.t+jobs@mail.example.co.uk", "jane_t@sub-domain.example.org"],
)
def test_common_email_forms_are_recognized(email):
    assert check_missing_contact(document_from_text(f"Jane Testperson | {email}\n{BODY}")).value == 1


@pytest.mark.parametrize(
    "text",
    [
        "Built it with version 1.2@3.4 of the tool",
        "Acme 2018 - 2020 - 2022",  # a run of years is not a phone
        "Years: 2019 2020 2021",
        "Order 12345678",  # too few digits to be a phone with separators absent
    ],
    ids=["version-number", "year-run-dashes", "year-run-spaces", "short-digits"],
)
def test_lookalikes_are_not_contact_details(text):
    assert check_missing_contact(document_from_text(f"Jane Testperson\n{text}\n{BODY}")).value == 0
