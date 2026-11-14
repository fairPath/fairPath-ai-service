"""POST /resume: extraction failures return the shared 422 envelope before any pipeline work."""
import io

import pytest
from PIL import Image, ImageDraw

import extraction
from conftest import make_pdf

BODY = {
    "correlation_id": "c-9",
    "s3_key": "resumes/x.pdf",
    "known_pii": {"full_name": None, "email": None, "phone": None},
}


def image_only_pdf() -> bytes:
    """A page holding a picture of text: visible to a person, no text layer."""
    image = Image.new("RGB", (600, 200), "white")
    ImageDraw.Draw(image).text((20, 80), "Jane Testperson Software Engineer", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PDF")
    return buffer.getvalue()


def short_pdf() -> bytes:
    return make_pdf(["Jane Testperson", "Engineer"])


def whitespace_padded_pdf() -> bytes:
    """Plenty of characters, but almost none that aren't whitespace."""
    return make_pdf(["Jane", "   " * 100, "Doe"])


@pytest.mark.parametrize(
    "pdf, error_code",
    [
        pytest.param(image_only_pdf(), "TEXT_NOT_EXTRACTABLE", id="image-only"),
        pytest.param(short_pdf(), "TEXT_NOT_EXTRACTABLE", id="very-short"),
        pytest.param(whitespace_padded_pdf(), "TEXT_NOT_EXTRACTABLE", id="whitespace-padded"),
        pytest.param(b"%PDF-1.4 this is not really a pdf", "FILE_UNREADABLE", id="corrupt"),
        pytest.param(b"", "FILE_UNREADABLE", id="empty-file"),
    ],
)
def test_unextractable_file_returns_422_envelope(client, auth, pdf_store, pdf, error_code):
    pdf_store["resumes/x.pdf"] = pdf

    response = client.post("/resume", json=BODY, headers=auth)

    assert response.status_code == 422
    assert response.json() == {
        "correlation_id": "c-9",
        "error_code": error_code,
        "retryable": False,
    }


def test_floor_comes_from_config(client, auth, pdf_store, monkeypatch):
    pdf_store["resumes/x.pdf"] = short_pdf()
    monkeypatch.setattr(extraction, "EXTRACTION_MIN_CHARS", 5)

    response = client.post("/resume", json=BODY, headers=auth)

    assert response.status_code == 200


def test_failure_does_not_reach_the_pipeline_or_the_logs(client, auth, pdf_store, caplog, monkeypatch):
    import resume

    pdf_store["resumes/x.pdf"] = short_pdf()
    monkeypatch.setattr(resume, "analyze_text", lambda text: pytest.fail("pipeline ran"))
    caplog.set_level("DEBUG")

    client.post("/resume", json=BODY, headers=auth)

    assert "Jane" not in caplog.text
