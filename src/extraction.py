import io
import logging

import pdfplumber

# pdfminer logs raw PDF content strings (Resume text) at DEBUG. Cap it so
# turning on debug logging can never leak a Resume into the logs.
logging.getLogger("pdfminer").setLevel(logging.WARNING)


def extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)
