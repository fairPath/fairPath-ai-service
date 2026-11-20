"""The Analysis pipeline: Checks on the Extracted document, then the Scorer."""
from collections import defaultdict

from analysis_config import ISSUE_ID_PREFIX, ISSUE_TYPES
from checks import (
    Check,
    CheckIssue,
    check_inconsistent_dates,
    check_missing_contact,
    check_missing_section,
    check_too_long,
    check_unreadable_characters,
)
from contract import IssueDetail, Scores
from extraction import ExtractedDocument
from scorer import score

CHECKS: list[Check] = [
    check_missing_contact,
    check_too_long,
    check_inconsistent_dates,
    check_unreadable_characters,
    check_missing_section,
]


def analyze_document(doc: ExtractedDocument) -> tuple[Scores, list[IssueDetail]]:
    results = [check(doc) for check in CHECKS]
    scores = score({result.component: result.value for result in results})
    issues = _to_issue_details([issue for result in results for issue in result.issues])
    return scores, issues


def _to_issue_details(raw_issues: list[CheckIssue]) -> list[IssueDetail]:
    """Code, never a Check or the LLM, sets Category, source and severity
    from the Issue type, and numbers Issues per Category (fmt-001, ...)."""
    counters: dict[str, int] = defaultdict(int)
    details = []
    for raw in raw_issues:
        spec = ISSUE_TYPES[raw.issue_type]
        counters[spec.category] += 1
        details.append(
            IssueDetail(
                issue_id=f"{ISSUE_ID_PREFIX[spec.category]}-{counters[spec.category]:03d}",
                issue_type=raw.issue_type,
                category=spec.category,
                source=spec.source,
                severity=spec.severity,
                snippet=raw.snippet,
                line_id=raw.line_id,
                line_text=raw.line_text,
                section=raw.section,
                line_kind=raw.line_kind,
                description=raw.description,
                suggestion=raw.suggestion,
            )
        )
    return details
