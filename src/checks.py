"""Deterministic Checks. They run on the Extracted text, never on Redacted text."""
import re
from collections.abc import Callable
from dataclasses import dataclass, field

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


def _is_phone(candidate: str) -> bool:
    digit_groups = re.findall(r"\d+", candidate)
    if not PHONE_MIN_DIGITS <= sum(len(group) for group in digit_groups) <= PHONE_MAX_DIGITS:
        return False
    # "2018 - 2020 - 2022" has enough digits but is a list of years.
    return not all(YEAR_PATTERN.fullmatch(group) for group in digit_groups)


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
