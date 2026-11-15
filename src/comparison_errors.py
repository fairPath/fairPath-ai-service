"""Safe comparison-only envelopes, including validation and dependency errors."""
import logging
from uuid import UUID

from fastapi import Request
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from errors import error_response
from fastapi.routing import APIRoute

logger = logging.getLogger(__name__)


class ComparisonError(HTTPException):
    def __init__(self, status: int, code: str, retryable: bool):
        super().__init__(status_code=status)
        self.code = code
        self.retryable = retryable


class ComparisonRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            correlation_id = None
            try:
                body = await request.json()
                correlation_id = str(UUID(str(body.get("correlation_id"))))
            except (ValueError, TypeError, AttributeError):
                pass
            try:
                return await original(request)
            except ComparisonError as error:
                status, code, retryable = error.status_code, error.code, error.retryable
            except RequestValidationError:
                status, code, retryable = 422, "INVALID_COMPARISON_REQUEST", False
            except HTTPException as error:
                status = error.status_code
                code = "AI_AUTHENTICATION_FAILED" if status in (401, 403) else "INVALID_COMPARISON_REQUEST"
                retryable = False
            except Exception:
                status, code, retryable = 500, "INTERNAL_ERROR", False
            logger.warning("comparison failed correlation_id=%s error_code=%s", correlation_id, code)
            return error_response(status, correlation_id or "", code, retryable)

        return handler
