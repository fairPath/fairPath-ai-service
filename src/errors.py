"""The shared error envelope: { correlation_id, error_code, retryable }.

Only the code travels. Exception messages from the PDF library can carry
Resume content, so they never reach the response or the logs.
"""
from datetime import timezone
from email.utils import parsedate_to_datetime, format_datetime

from fastapi.responses import JSONResponse
from pydantic import BaseModel

TEXT_NOT_EXTRACTABLE = "TEXT_NOT_EXTRACTABLE"
FILE_UNREADABLE = "FILE_UNREADABLE"


class ErrorEnvelope(BaseModel):
    correlation_id: str
    error_code: str
    retryable: bool


class ExtractionError(Exception):
    """The Resume can't yield text. Never retryable: the same file fails again."""

    status_code = 422
    retryable = False

    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def retry_after_headers(value: str | None) -> dict[str, str]:
    """Forward only a valid Retry-After, never arbitrary provider headers or text."""
    if not value:
        return {}
    value = value.strip()
    if value.isascii() and value.isdecimal() and len(value) <= 18:
        return {"Retry-After": str(int(value))}
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return {}
        return {"Retry-After": format_datetime(date.astimezone(timezone.utc), usegmt=True)}
    except (ValueError, TypeError, OverflowError):
        return {}


def error_response(status_code: int, correlation_id: str, error_code: str, retryable: bool,
                   *, retry_after: str | None = None) -> JSONResponse:
    envelope = ErrorEnvelope(correlation_id=correlation_id, error_code=error_code, retryable=retryable)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(),
                        headers=retry_after_headers(retry_after) if retryable else {})
