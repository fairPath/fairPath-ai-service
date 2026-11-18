"""Shared provider-call failures and safe AI-route error responses."""
import logging
from uuid import UUID

from fastapi import Request
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from errors import error_response
from openai import APIStatusError, APITimeoutError, APIConnectionError
from pydantic import BaseModel
from typing import TypeVar
from fastapi.routing import APIRoute

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class AiRequestError(HTTPException):
    def __init__(self, status: int, code: str, retryable: bool, *, retry_after: str | None = None):
        super().__init__(status_code=status)
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


class AiErrorRoute(APIRoute):
    invalid_request_code = "INVALID_AI_REQUEST"

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            correlation_id = None
            try:
                body = await request.json()
                correlation_id = str(UUID(str(body.get("correlation_id"))))
            except (ValueError, TypeError, AttributeError):
                pass
            retry_after = None
            try:
                return await original(request)
            except AiRequestError as error:
                status, code, retryable = error.status_code, error.code, error.retryable
                retry_after = error.retry_after
            except RequestValidationError:
                status, code, retryable = 422, self.invalid_request_code, False
            except HTTPException as error:
                status = error.status_code
                code = "AI_AUTHENTICATION_FAILED" if status in (401, 403) else self.invalid_request_code
                retryable = False
            except Exception:
                status, code, retryable = 500, "INTERNAL_ERROR", False
            logger.warning("AI request failed correlation_id=%s error_code=%s", correlation_id, code)
            return error_response(status, correlation_id or "", code, retryable, retry_after=retry_after)

        return handler


def call_ai(llm, system: str, user: str, schema: type[T],
            *, invalid_request_code: str = "INVALID_AI_REQUEST") -> T:
    """A feature supplies its request and success schema; provider failures stay here.

    invalid_request_code supports existing endpoint contracts without copying policy.
    No automatic retries happen here: Spring owns attempt limits and scheduling.
    """
    try:
        return llm.analyze(system, user, schema)
    except APITimeoutError:
        raise AiRequestError(504, "AI_TIMED_OUT", True) from None
    except APIConnectionError:
        raise AiRequestError(503, "AI_UNAVAILABLE", True) from None
    except APIStatusError as error:
        if error.status_code in (401, 403):
            raise AiRequestError(502, "AI_CONFIGURATION_ERROR", False) from None
        retry_after = error.response.headers.get("Retry-After")
        if error.status_code == 429:
            raise AiRequestError(503, "UPSTREAM_RATE_LIMITED", True, retry_after=retry_after) from None
        if error.status_code >= 500:
            raise AiRequestError(503, "AI_UNAVAILABLE", True, retry_after=retry_after) from None
        raise AiRequestError(502, invalid_request_code, False) from None
    except ValueError:
        raise AiRequestError(502, "INVALID_AI_RESPONSE", False) from None
