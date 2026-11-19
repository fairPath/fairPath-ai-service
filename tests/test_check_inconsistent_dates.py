"""INCONSISTENT_DATES fails when dates that carry a month use two or more styles."""
import pytest

from checks import check_inconsistent_dates
from conftest import document_from_text


def run(*lines):
    return check_inconsistent_dates(document_from_text("\n".join(lines)))


@pytest.mark.parametrize(
    "lines",
    [
        ("Acme, Jan 2020 - Mar 2021", "Beta, Jun 2021 - Dec 2022"),
        ("Acme, January 2020 - March 2021", "Beta, June 2021 - December 2022"),
        ("Acme, 01/2020 - 03/2021", "Beta, 6/2021 - 12/2022"),
        ("Acme, 2020-01 - 2021-03", "Beta, 2021-06 - 2022-12"),
        ("Acme, Sept. 2020 - Dec. 2021", "Beta, Jan. 2022 - Present"),
    ],
    ids=["abbreviated", "full", "numeric", "iso", "abbreviated-with-periods"],
)
def test_one_style_throughout_passes(lines):
    result = run(*lines)

    assert result.component == "inconsistent_dates"
    assert result.value == 1
    assert result.issues == []


@pytest.mark.parametrize(
    "lines",
    [
        ("Acme, January 2020 - Mar 2021",),
        ("Acme, Jan 2020 - 03/2021",),
        ("Acme, January 2020 - 2021-03",),
        ("Acme, 01/2020", "Beta, 2021-06"),
    ],
    ids=["full-vs-abbreviated", "abbreviated-vs-numeric", "full-vs-iso", "numeric-vs-iso"],
)
def test_two_styles_fail_with_one_document_level_issue(lines):
    result = run(*lines)

    assert result.value == 0
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.issue_type == "INCONSISTENT_DATES"
    assert issue.snippet is None and issue.line_id is None  # document-level


def test_description_names_the_styles_without_quoting_dates():
    issue = run("Acme, January 2020 - Mar 2021").issues[0]

    assert "full month names" in issue.description
    assert "abbreviated month names" in issue.description
    assert "2020" not in issue.description


def test_may_fits_either_month_name_style():
    assert run("Acme, May 2020 - Jan 2021").value == 1
    assert run("Acme, May 2020 - January 2021").value == 1
    assert run("Acme, May 2020 - May 2021").value == 1


@pytest.mark.parametrize(
    "lines",
    [
        ("Acme, May 2020 - 03/2021",),
        ("Acme, May 2020 - 2021-03",),
        ("Acme, May 2020", "Beta, 2021-06"),
    ],
    ids=["may-vs-numeric", "may-vs-iso", "may-alone-vs-iso"],
)
def test_may_does_not_fit_numeric_or_iso_dates(lines):
    result = run(*lines)

    assert result.value == 0
    assert "month names" in result.issues[0].description
    assert "2020" not in result.issues[0].description


def test_may_cannot_bridge_two_named_styles():
    # Jan is abbreviated and January is full; May fits both but joins neither.
    assert run("Acme, Jan 2020 - May 2020 - January 2021").value == 0


def test_year_only_dates_are_ignored():
    assert run("Acme, Jan 2020 - Mar 2021", "B.S., 2016 - 2020").value == 1


def test_present_is_ignored():
    assert run("Acme, Jan 2020 - Present", "Beta, Feb 2018 - Current").value == 1


def test_fewer_than_two_month_dates_is_not_applicable():
    assert run("Acme, Jan 2020").value is None
    assert run("Acme, 2016 - 2020").value is None
    assert run("No dates at all").value is None


def test_a_single_style_with_one_stray_year_only_range_stays_consistent():
    assert run("Jan 2020 - Mar 2021", "2018 - 2019", "Jun 2017 - Dec 2017").value == 1


@pytest.mark.parametrize(
    "text",
    ["Call 555-010-1234 or 12/31/2020", "ZIP 12345-6789", "Python 3.12 and 2.7"],
    ids=["phone-and-full-date", "zip", "versions"],
)
def test_lookalikes_are_not_dates(text):
    assert run(text, "Acme, Jan 2020 - Mar 2021").value == 1
