"""Deterministic Checks. They run on the Extracted text, never on Redacted text."""
import re
from dataclasses import dataclass, field


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


EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# NANP-style numbers with an optional country code: 555-010-1234, (555) 010-1234,
# +1 555.010.1234. Ten digits are required, so years and date ranges don't match.
PHONE_PATTERN = re.compile(
    r"(?<![\d\w])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
)


def check_missing_contact(text: str) -> CheckResult:
    """Presence Check: fails only when neither an email nor a phone is found."""
    if EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text):
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
