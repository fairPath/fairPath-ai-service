"""Deterministic Checks. They run on the Extracted text, never on Redacted text."""
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import analysis_config
from extraction import ExtractedDocument


@dataclass(frozen=True)
class CheckIssue:
    """An Issue as a Check raises it. The pipeline adds the id, Category,
    source and severity from the Issue type's config."""

    issue_type: str
    description: str
    suggestion: str
    # All None for a document-level Issue.
    snippet: str | None = None
    line_id: int | None = None
    line_text: str | None = None
    section: str | None = None
    line_kind: str | None = None


@dataclass(frozen=True)
class CheckResult:
    """One score component: value in [0, 1], or None when not applicable."""

    component: str
    value: float | None
    issues: list[CheckIssue] = field(default_factory=list)


# The top-level domain must be letters, so `version 1.2@3.4` is not an email.
EMAIL_PATTERN = re.compile(r"[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}")

# A phone is a run of digits joined by spaces, dots, parentheses or dashes
# (hyphen, en dash, em dash: PDF extraction often yields the latter two).
# The regex only finds candidates; _is_phone then applies the digit-count and
# not-a-list-of-years rules, which a regex can't express cleanly.
PHONE_CANDIDATE = re.compile(r"(?<!\w)\+?\(?\d[\d \t().\-–—]*\d(?!\d)")
PHONE_MIN_DIGITS = 10
PHONE_MAX_DIGITS = 15
YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")
MONTH_PATTERN = re.compile(r"0?[1-9]|1[0-2]")


def _is_date_like(group: str) -> bool:
    return bool(YEAR_PATTERN.fullmatch(group) or MONTH_PATTERN.fullmatch(group))


def _is_phone(candidate: str) -> bool:
    """True if some run of digit groups inside the candidate looks like a phone.

    Adjacent numbers ("555-010-1234  555-010-5678") arrive as one long
    candidate, so each contiguous slice of groups is tried. A slice is a phone
    when it has 10 to 15 digits, is not only years and months ("2018 - 2020",
    "2020-01 - 2021-03" are date spans) and does not start with a year or month,
    so "2019 - 2020 2021 12345" (years, then a ZIP) is not a number. A leading
    country code like "+1" is still found through the slice that follows it.
    """
    groups = re.findall(r"\d+", candidate)
    for start in range(len(groups)):
        if _is_date_like(groups[start]):
            continue
        digits = 0
        for end in range(start, len(groups)):
            digits += len(groups[end])
            if digits > PHONE_MAX_DIGITS:
                break
            if digits >= PHONE_MIN_DIGITS and not all(_is_date_like(g) for g in groups[start:end + 1]):
                return True
    return False


def _has_phone(text: str) -> bool:
    return any(_is_phone(match.group()) for match in PHONE_CANDIDATE.finditer(text))


# Every Check reads the same document, whether it needs the text, the page count or both.
Check = Callable[[ExtractedDocument], CheckResult]


def check_missing_contact(doc: ExtractedDocument) -> CheckResult:
    """Presence Check: fails only when neither an email nor a phone is found."""
    if EMAIL_PATTERN.search(doc.text) or _has_phone(doc.text):
        return CheckResult(component="missing_contact", value=1)
    return CheckResult(
        component="missing_contact",
        value=0,
        issues=[
            CheckIssue(
                issue_type="MISSING_CONTACT",
                description="No email address or phone number was found in your resume.",
                suggestion="Add an email address or phone number near the top so recruiters can reach you.",
            )
        ],
    )


def check_too_long(doc: ExtractedDocument) -> CheckResult:
    """Presence Check: fails when the Resume has more pages than MAX_PAGES."""
    limit = analysis_config.MAX_PAGES
    if doc.page_count <= limit:
        return CheckResult(component="too_long", value=1)
    return CheckResult(
        component="too_long",
        value=0,
        issues=[
            CheckIssue(
                issue_type="TOO_LONG",
                description=f"Your resume is {doc.page_count} pages long.",
                suggestion=f"Trim it to {limit} pages or fewer, keeping your most relevant experience.",
            )
        ],
    )


# Month-name word followed by a year, e.g. "Jan 2020", "Sept. 2020", "March, 2020".
_MONTH_NAME_DATE = re.compile(r"\b([A-Za-z]{3,9})\.?,?[ \t]+(?:19|20)\d{2}(?!\d)")
# 01/2020 or 1/2020, not part of a longer date such as 12/31/2020.
_NUMERIC_DATE = re.compile(r"(?<![\d/])(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}(?!\d)")
# 2020-01, not part of a longer number such as 555-010-1234 or 2020-10-1234.
_ISO_DATE = re.compile(r"(?<![\d-])(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?![\d-])")

_DATE_STYLE_LABELS = {
    "full": "full month names",
    "abbreviated": "abbreviated month names",
    "month_name": "month names",  # only "May", which is both full and abbreviated
    "numeric": "numeric dates (MM/YYYY)",
    "iso": "YYYY-MM dates",
}
_MONTH_NAME_STYLES = frozenset({"full", "abbreviated"})


def check_inconsistent_dates(doc: ExtractedDocument) -> CheckResult:
    """Presence Check: fails when no single date style fits every date that carries a month.

    Each date fits one or more styles: "May" fits full and abbreviated month
    names, every other date fits exactly one. The dates are consistent when one
    style fits them all. Year-only dates and "Present" are ignored. With fewer
    than two dates that carry a month there is nothing to compare, so the
    component is not applicable.
    """
    fits: list[frozenset[str]] = []
    for match in _MONTH_NAME_DATE.finditer(doc.text):
        month = match.group(1).lower()
        if month in analysis_config.FULL_MONTHS:
            fits.append(frozenset({"full"}))
        elif month in analysis_config.ABBREVIATED_MONTHS:
            fits.append(frozenset({"abbreviated"}))
        elif month == "may":
            fits.append(_MONTH_NAME_STYLES)
    for style, pattern in (("numeric", _NUMERIC_DATE), ("iso", _ISO_DATE)):
        fits.extend(frozenset({style}) for _ in pattern.findall(doc.text))

    dates = len(fits)
    if dates < 2:
        return CheckResult(component="inconsistent_dates", value=None)
    if frozenset.intersection(*fits):
        return CheckResult(component="inconsistent_dates", value=1)
    styles = {style for fit in fits if len(fit) == 1 for style in fit}
    if not styles & _MONTH_NAME_STYLES and any(len(fit) > 1 for fit in fits):
        styles.add("month_name")
    used = ", ".join(label for style, label in _DATE_STYLE_LABELS.items() if style in styles)
    return CheckResult(
        component="inconsistent_dates",
        value=0,
        issues=[
            CheckIssue(
                issue_type="INCONSISTENT_DATES",
                description=f"Your resume mixes date formats: {used}.",
                suggestion="Use one date format throughout, for example Jan 2020 - Mar 2021.",
            )
        ],
    )


_UNREADABLE = re.compile(
    r"\(cid:\d+\)"
    "|[-\U000f0000-\U000ffffd\U00100000-\U0010fffd�]"
)


def check_unreadable_characters(doc: ExtractedDocument) -> CheckResult:
    """Presence Check: fails at UNREADABLE_MIN_COUNT characters an ATS can't read.

    Counts `(cid:NN)` markers (a font without a usable character map),
    private-use characters and the replacement character.
    """
    count = len(_UNREADABLE.findall(doc.text))
    if count < analysis_config.UNREADABLE_MIN_COUNT:
        return CheckResult(component="unreadable_characters", value=1)
    return CheckResult(
        component="unreadable_characters",
        value=0,
        issues=[
            CheckIssue(
                issue_type="UNREADABLE_CHARACTERS",
                description=f"{count} characters in your resume could not be read as text.",
                suggestion=(
                    "Export the resume again with standard fonts, and replace icons "
                    "or symbols with plain text, so an ATS can read it."
                ),
            )
        ],
    )


def _normalise_heading(line: str) -> str:
    line = line.lower().replace("&", " and ")
    line = re.sub(r"^\W+|\W+$", "", line)
    return re.sub(r"\s+", " ", line)


def check_missing_section(doc: ExtractedDocument) -> CheckResult:
    """Count Check: one Issue per missing Experience, Education or Skills section.

    A section is present when a whole line, normalised, equals one of its
    synonyms, so the word "experience" inside a bullet doesn't count. The value
    is max(0, 1 - missing / MISSING_SECTION_K).
    """
    headings = {_normalise_heading(line) for line in doc.text.splitlines()}
    missing = [
        section
        for section, synonyms in analysis_config.SECTION_SYNONYMS.items()
        if not headings.intersection(synonyms)
    ]
    value = max(0, 1 - len(missing) / analysis_config.MISSING_SECTION_K)
    return CheckResult(
        component="missing_sections",
        value=value,
        issues=[
            CheckIssue(
                issue_type="MISSING_SECTION",
                description=f"No {section} section was found in your resume.",
                suggestion=f'Add a section with the heading "{section}" so an ATS can find it.',
            )
            for section in missing
        ],
    )
