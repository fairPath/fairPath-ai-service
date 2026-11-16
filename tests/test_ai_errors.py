"""Synthetic provider responses exercise the reusable boundary, with no external calls."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from openai import APIStatusError, APIConnectionError, APITimeoutError
from pydantic import BaseModel

from ai_errors import AiErrorRoute, AiRequestError, call_ai
from errors import error_response, retry_after_headers


@pytest.mark.parametrize("value,expected", [
    ("60", "60"), (" 060 ", "60"),
    ("Sun, 15 Nov 2026 20:00:00 GMT", "Sun, 15 Nov 2026 20:00:00 GMT"),
    (None, None), ("", None), ("garbage", None), ("-1", None), ("1.5", None),
    ("9" * 30, None), ("60\r\nX-Private: secret", None),
])
def test_retry_header_validation(value, expected):
    assert retry_after_headers(value).get("Retry-After") == expected


def provider_error(status, retry_after):
    return APIStatusError("Synthetic private provider message", response=httpx.Response(
        status, headers={"Retry-After": retry_after, "X-Private": "secret"},
        request=httpx.Request("POST", "http://fake-model")), body=None)


@pytest.mark.parametrize("status,code", [(429, "UPSTREAM_RATE_LIMITED"), (503, "AI_UNAVAILABLE")])
@pytest.mark.parametrize("retry_after", ["60", "Sun, 15 Nov 2026 20:00:00 GMT"])
def test_comparison_forwards_provider_retry_header(client, auth, fake_llm, status, code, retry_after):
    fake_llm.error = provider_error(status, retry_after)
    correlation = str(uuid4())
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": correlation, "job_id": "job", "s3_key": "resumes/ok.pdf",
        "job_description": "Python"})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == retry_after
    assert response.json() == {"correlation_id": correlation, "error_code": code, "retryable": True}
    assert "X-Private" not in response.headers
    assert "private" not in response.text
    assert len(fake_llm.calls) == 1


@pytest.mark.parametrize("status,expected_status,code", [
    (401, 502, "AI_CONFIGURATION_ERROR"), (403, 502, "AI_CONFIGURATION_ERROR"),
    (400, 502, "INVALID_AI_REQUEST"),
])
def test_permanent_provider_failure_cannot_enable_retry(status, expected_status, code):
    llm = SimpleNamespace(analyze=Mock(side_effect=provider_error(status, "60")))
    with pytest.raises(AiRequestError) as failure:
        call_ai(llm, "system", "synthetic input", Success)
    error = failure.value
    assert (error.status_code, error.code, error.retryable) == (expected_status, code, False)
    response = error_response(error.status_code, "correlation", error.code, error.retryable,
                              retry_after=error.retry_after)
    assert "Retry-After" not in response.headers


@pytest.mark.parametrize("error,status,code", [
    (APIConnectionError(request=httpx.Request("POST", "http://fake-model")), 503, "AI_UNAVAILABLE"),
    (APITimeoutError(request=httpx.Request("POST", "http://fake-model")), 504, "AI_TIMED_OUT"),
    (ValueError("synthetic invalid output"), 502, "INVALID_AI_RESPONSE"),
])
def test_shared_classification_preserves_existing_policy(error, status, code):
    llm = SimpleNamespace(analyze=Mock(side_effect=error))
    with pytest.raises(AiRequestError) as failure:
        call_ai(llm, "system", "synthetic input", Success)
    assert (failure.value.status_code, failure.value.code) == (status, code)
    assert llm.analyze.call_count == 1


class Success(BaseModel):
    text: str


class RequestBody(BaseModel):
    correlation_id: str


def test_future_endpoint_only_supplies_request_and_success_schema():
    llm = SimpleNamespace(analyze=Mock(return_value=Success(text="synthetic success")))
    router = APIRouter(route_class=AiErrorRoute)

    @router.post("/future-ai-request")
    def future(body: RequestBody):
        return call_ai(llm, "system", "synthetic request", Success)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    body = {"correlation_id": str(uuid4())}
    assert client.post("/future-ai-request", json=body).json() == {"text": "synthetic success"}
    llm.analyze.side_effect = provider_error(429, "60")
    response = client.post("/future-ai-request", json=body)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert response.json() == {**body, "error_code": "UPSTREAM_RATE_LIMITED", "retryable": True}
