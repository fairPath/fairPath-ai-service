"""Analysis configuration: versioned with the pipeline.

Bump PIPELINE_VERSION on any change to the prompt, rubric, Checks, weights or model.
"""
from dataclasses import dataclass

from contract import Category, Severity, Source

PIPELINE_VERSION = "0.1.0"

# Component weights per Category (spec "Scorer"; each Category sums to 10).
# A component that hasn't run, or isn't applicable, drops out of both sums.
WEIGHTS: dict[Category, dict[str, int]] = {
    "parseability": {
        "multi_column": 3,
        "unreadable_characters": 3,
        "missing_sections": 2,
        "table_content": 2,
    },
    "formatting": {
        "missing_contact": 5,
        "too_long": 3,
        "inconsistent_dates": 2,
    },
    "writing": {
        "impact": 3,
        "clarity": 3,
        "spelling": 2,
        "grammar": 2,
    },
}


@dataclass(frozen=True)
class IssueTypeSpec:
    """An Issue type fixes its Category, source and severity."""

    category: Category
    source: Source
    severity: Severity


ISSUE_TYPES: dict[str, IssueTypeSpec] = {
    "MISSING_CONTACT": IssueTypeSpec(category="formatting", source="check", severity="high"),
}

ISSUE_ID_PREFIX: dict[Category, str] = {
    "formatting": "fmt",
    "parseability": "prs",
    "writing": "wrt",
}
