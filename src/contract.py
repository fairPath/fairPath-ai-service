"""The Spring → AI service Analyze contract (spec: "API contracts")."""
from typing import Literal

from pydantic import BaseModel

Category = Literal["formatting", "parseability", "writing"]
Source = Literal["check", "llm"]
Severity = Literal["low", "medium", "high"]
Section = Literal["EXPERIENCE", "PROJECTS", "OTHER"]
LineKind = Literal["BULLET", "OTHER"]


class KnownPii(BaseModel):
    """The user's own details. Used only as a deny-list; each field is nullable."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None


class AnalyzeRequest(BaseModel):
    correlation_id: str
    s3_key: str
    known_pii: KnownPii


class Scores(BaseModel):
    """Integers 0–100, computed by code."""

    formatting: int
    parseability: int
    writing: int
    overall: int


class IssueDetail(BaseModel):
    issue_id: str
    issue_type: str
    category: Category
    source: Source
    severity: Severity
    # Snippet and Line fields are all null for a document-level Issue.
    snippet: str | None
    line_id: int | None
    line_text: str | None
    section: Section | None
    line_kind: LineKind | None
    description: str
    suggestion: str


class AnalyzeResponse(BaseModel):
    correlation_id: str
    scores: Scores
    issues: list[IssueDetail]
    # The model the LLM gateway reported; null while the pipeline makes no LLM call.
    model: str | None
    pipeline_version: str
