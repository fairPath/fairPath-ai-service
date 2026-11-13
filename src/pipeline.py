"""The Analysis pipeline: Checks on the Extracted text, then the Scorer."""
from collections import defaultdict
from collections.abc import Callable

from analysis_config import ISSUE_ID_PREFIX, ISSUE_TYPES
from checks import CheckIssue, CheckResult, check_missing_contact
from contract import IssueDetail, Scores
from scorer import score

CHECKS: list[Callable[[str], CheckResult]] = [check_missing_contact]


def analyze_text(text: str) -> tuple[Scores, list[IssueDetail]]:
    results = [check(text) for check in CHECKS]
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
