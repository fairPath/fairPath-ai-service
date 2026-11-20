"""Analysis configuration: versioned with the pipeline.

Bump PIPELINE_VERSION on any change to the prompt, rubric, Checks, weights or model.
"""
from dataclasses import dataclass

from contract import Category, Severity, Source

PIPELINE_VERSION = "0.1.0"

# Component weights per Category (spec "Scorer"). The multi-column and table
# Checks are cut (#63), so Parseability sums to 5; the Scorer divides by the
# sum, so only the ratio matters. A component that hasn't run, or isn't
# applicable, drops out of both sums.
WEIGHTS: dict[Category, dict[str, int]] = {
    "parseability": {
        "unreadable_characters": 3,
        "missing_sections": 2,
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
    "TOO_LONG": IssueTypeSpec(category="formatting", source="check", severity="medium"),
    "INCONSISTENT_DATES": IssueTypeSpec(category="formatting", source="check", severity="low"),
    "UNREADABLE_CHARACTERS": IssueTypeSpec(category="parseability", source="check", severity="high"),
    "MISSING_SECTION": IssueTypeSpec(category="parseability", source="check", severity="medium"),
}

# TOO_LONG fails when a Resume has more pages than this.
MAX_PAGES = 2

# UNREADABLE_CHARACTERS fails at this many unreadable characters in total:
# `(cid:NN)` markers, private-use characters and U+FFFD. Icon-font templates
# put private-use glyphs beside contact details; raise this if that proves a
# problem on real Resumes.
UNREADABLE_MIN_COUNT = 1

# MISSING_SECTION is a count Check: score = max(0, 1 - missing / MISSING_SECTION_K).
MISSING_SECTION_K = 3

# A section is present when a whole line of the Resume, lowercased and with
# surrounding punctuation removed ("&" read as "and"), equals a synonym.
SECTION_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Experience": (
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
    ),
    "Education": ("education", "academic background", "education and training"),
    "Skills": ("skills", "technical skills", "core competencies", "skills and tools", "technologies"),
}

# INCONSISTENT_DATES compares the styles of dates that carry a month. "May" is
# both a full name and its own abbreviation, so it fits either style and is
# counted as a date without choosing one.
FULL_MONTHS = (
    "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december",
)
ABBREVIATED_MONTHS = ("jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec")

ISSUE_ID_PREFIX: dict[Category, str] = {
    "formatting": "fmt",
    "parseability": "prs",
    "writing": "wrt",
}
