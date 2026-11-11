import io

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

import main
import resume

TOKEN = "test-token"

SYNTHETIC_RESUME_LINES = [
    "Jane Testperson",
    "jane.testperson@example.com | 555-010-1234",
    "SKILLS",
    "Python, FastAPI, PostgreSQL",
    "EXPERIENCE",
    "Software Engineer, Acme Widgets 2020 - 2024",
    "- Built an internal tool that reduced report generation time.",
    "- Responsible for maintaining the deployment pipeline.",
    "EDUCATION",
    "B.S. Computer Science, Example State University",
]


def make_pdf(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()
    return buffer.getvalue()


class FakeLLM:
    """Stands in for the LLM gateway: records calls, returns a canned object."""

    model = "fake-model"

    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    def analyze(self, system: str, user: str, schema):
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def canned_analysis():
    return resume.ResumeAnalysis(
        ats_parseability_score=80,
        experience_years=4,
        skills=["Python", "FastAPI"],
        formatting_issues=["Inconsistent date format"],
        writing_issues=[
            resume.IssueDetail(
                issue_type="weak_verb",
                description="Bullet only lists a duty.",
                suggestion="Show the outcome.",
            )
        ],
        suggestions=["Quantify your impact."],
    )


@pytest.fixture
def fake_llm(canned_analysis):
    return FakeLLM(result=canned_analysis)


@pytest.fixture
def pdf_store():
    """Fake S3: s3_key -> PDF bytes. Tests add entries."""
    return {"resumes/ok.pdf": make_pdf(SYNTHETIC_RESUME_LINES)}


@pytest.fixture
def client(monkeypatch, fake_llm, pdf_store):
    monkeypatch.setattr(resume, "INTERNAL_TOKEN", TOKEN)
    main.app.dependency_overrides[resume.get_llm] = lambda: fake_llm
    main.app.dependency_overrides[resume.get_resume_fetcher] = lambda: pdf_store.__getitem__
    yield TestClient(main.app, raise_server_exceptions=False)
    main.app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return {"X-Internal-Token": TOKEN}
