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

# Same synthetic Resume with the contact line removed.
NO_CONTACT_RESUME_LINES = [line for line in SYNTHETIC_RESUME_LINES if "@" not in line]


def make_pdf(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 18
    pdf.save()
    return buffer.getvalue()


@pytest.fixture
def pdf_store():
    """Fake S3: s3_key -> PDF bytes. Tests add entries."""
    return {
        "resumes/ok.pdf": make_pdf(SYNTHETIC_RESUME_LINES),
        "resumes/no-contact.pdf": make_pdf(NO_CONTACT_RESUME_LINES),
    }


@pytest.fixture
def client(monkeypatch, pdf_store):
    monkeypatch.setattr(resume, "INTERNAL_TOKEN", TOKEN)
    main.app.dependency_overrides[resume.get_resume_fetcher] = lambda: pdf_store.__getitem__
    yield TestClient(main.app, raise_server_exceptions=False)
    main.app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return {"X-Internal-Token": TOKEN}
