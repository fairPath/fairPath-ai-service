"""The shared error envelope: { correlation_id, error_code, retryable }.

Only the code travels. Exception messages from the PDF library can carry
Resume content, so they never reach the response or the logs.
"""
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

    def __init__(self, error_code: str):
        super().__init__(error_code)
        self.error_code = error_code


def error_response(status_code: int, correlation_id: str, error_code: str, retryable: bool) -> JSONResponse:
    envelope = ErrorEnvelope(correlation_id=correlation_id, error_code=error_code, retryable=retryable)
    return JSONResponse(status_code=status_code, content=envelope.model_dump())
