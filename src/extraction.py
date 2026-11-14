import io
import logging
import os

import pdfplumber

from errors import FILE_UNREADABLE, TEXT_NOT_EXTRACTABLE, ExtractionError

# pdfminer logs raw PDF content strings (Resume text) at DEBUG. Cap it so
# turning on debug logging can never leak a Resume into the logs.
logging.getLogger("pdfminer").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Fewer non-whitespace characters than this means there is no text layer worth
# analysing (an image-only scan, or a near-empty file). Tuned on extraction fixtures.
EXTRACTION_MIN_CHARS = int(os.environ.get("EXTRACTION_MIN_CHARS", "200"))


def extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_resume_text(pdf_bytes: bytes, correlation_id: str) -> str:
    """The text for an Analysis, or an ExtractionError.

    pdfplumber reads the text layer only; there is no OCR. Job comparison keeps
    using extract_text and its own blank check.
    """
    try:
        text = extract_text(pdf_bytes)
    except Exception as e:
        # The library raises many unrelated types on malformed files. Class
        # name only: messages can carry file content.
        logger.warning("resume unreadable correlation_id=%s error=%s", correlation_id, type(e).__name__)
        raise ExtractionError(FILE_UNREADABLE) from None

    if sum(1 for ch in text if not ch.isspace()) < EXTRACTION_MIN_CHARS:
        raise ExtractionError(TEXT_NOT_EXTRACTABLE)
    return text
