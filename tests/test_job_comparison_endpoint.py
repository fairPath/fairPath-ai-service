import job_comparison
import pytest
from uuid import uuid4

CORRELATION_ID = str(uuid4())

from conftest import make_pdf


def test_comparison_uses_gateway_and_updates_result(client, auth, fake_llm):
    fake_llm.result = job_comparison.JobComparisonResult(
        skill_match_score=90, experience_match_score=80, resume_advice="Highlight your relevant Python projects.",
        matched_skills=["Python"],
        missing_skills=["Java"],
        relevant_experience="Software engineering experience",
        other_gaps=[],
    )
    response = client.post(
        "/job-comparison",
        headers=auth,
        json={"correlation_id": CORRELATION_ID, "job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python and Java"},
    )
    assert response.status_code == 200
    assert response.json()["match_score"] == 85
    assert response.json()["skill_match_score"] == 90
    assert response.json()["experience_match_score"] == 80
    assert response.json()["resume_advice"] == "Highlight your relevant Python projects."
    assert response.json()["model"] == "fake-model"
    assert response.json()["correlation_id"] == CORRELATION_ID
    assert len(fake_llm.calls) == 1
    call = fake_llm.calls[0]
    assert call["schema"] is job_comparison.JobComparisonResult
    assert "Python and Java" in call["user"]
    assert "jane.testperson@example.com" not in call["user"]
    assert "555-010-1234" not in call["user"]


def test_comparison_requires_internal_auth(client, fake_llm):
    response = client.post(
        "/job-comparison",
        headers={"X-Internal-Token": "wrong-token"},
        json={"correlation_id": CORRELATION_ID, "job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python"},
    )
    assert response.status_code == 401
    assert not fake_llm.calls


def test_blank_pdf_rejected_before_model(client, auth, pdf_store, fake_llm):
    pdf_store["blank.pdf"] = make_pdf([""])
    response = client.post(
        "/job-comparison", headers=auth,
        json={"correlation_id": CORRELATION_ID, "job_id": "job-1", "s3_key": "blank.pdf", "job_description": "Python"},
    )
    assert response.status_code == 422
    assert response.json() == {"correlation_id": CORRELATION_ID, "error_code": "RESUME_UNREADABLE", "retryable": False}
    assert not fake_llm.calls


def test_model_failure_returns_error_for_worker_retry(client, auth, fake_llm):
    fake_llm.error = RuntimeError("Model unavailable")
    response = client.post(
        "/job-comparison", headers=auth,
        json={"correlation_id": CORRELATION_ID, "job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python"},
    )
    assert response.status_code == 500
    assert response.json() == {"correlation_id": CORRELATION_ID, "error_code": "INTERNAL_ERROR", "retryable": False}
    assert len(fake_llm.calls) == 1


def test_full_description_including_final_segment_reaches_model(client, auth, fake_llm):
    fake_llm.result = job_comparison.JobComparisonResult(
        skill_match_score=90, experience_match_score=80, resume_advice="Highlight your relevant Python projects.", matched_skills=[], missing_skills=[], relevant_experience="", other_gaps=[]
    )
    description = "A" * 255 + "B" * 252 + "C" * 1000 + " FINAL_REQUIREMENT"
    response = client.post(
        "/job-comparison", headers=auth,
        json={"correlation_id": CORRELATION_ID, "job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": description},
    )
    assert response.status_code == 200
    assert fake_llm.calls[0]["user"].endswith("Job description:\n" + description)

def test_missing_internal_token_returns_a_safe_nonretryable_envelope(client):
    response = client.post("/job-comparison", json={
        "correlation_id": CORRELATION_ID, "job_id": "job", "s3_key": "resumes/ok.pdf",
        "job_description": "Python",
    })
    assert response.status_code in (401, 403)
    assert response.json() == {
        "correlation_id": CORRELATION_ID, "error_code": "AI_AUTHENTICATION_FAILED", "retryable": False,
    }


def test_invalid_request_never_echoes_input_in_validation_errors(client, auth):
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": CORRELATION_ID, "job_id": "sensitive input", "job_description": "",
    })
    assert response.status_code == 422
    assert response.json() == {
        "correlation_id": CORRELATION_ID, "error_code": "INVALID_COMPARISON_REQUEST", "retryable": False,
    }


def test_model_connection_failure_is_retryable(client, auth, fake_llm):
    import httpx
    from openai import APIConnectionError
    fake_llm.error = APIConnectionError(request=httpx.Request("POST", "http://fake-model"))
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": CORRELATION_ID, "job_id": "job", "s3_key": "resumes/ok.pdf",
        "job_description": "Python",
    })
    assert response.status_code == 503
    assert response.json()["retryable"] is True
    assert response.json()["error_code"] == "AI_UNAVAILABLE"


def test_missing_resume_is_terminal_and_does_not_call_model(client, auth, monkeypatch, fake_llm):
    from botocore.exceptions import ClientError
    def missing(key):
        raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "private data"}}, "GetObject")
    import main, resume
    main.app.dependency_overrides[resume.get_resume_fetcher] = lambda: missing
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": CORRELATION_ID, "job_id": "job", "s3_key": "missing.pdf",
        "job_description": "Python",
    })
    assert response.status_code == 422
    assert response.json()["error_code"] == "RESUME_UNAVAILABLE"
    assert response.json()["retryable"] is False
    assert not fake_llm.calls
    assert "private data" not in response.text


def test_model_requests_disable_provider_storage():
    from types import SimpleNamespace
    from unittest.mock import Mock
    from llm import LLMGateway
    result = job_comparison.JobComparisonResult(
        skill_match_score=80, experience_match_score=80, resume_advice="Highlight your relevant projects.", matched_skills=[], missing_skills=[], relevant_experience="", other_gaps=[]
    )
    parse = Mock(return_value=SimpleNamespace(output_parsed=result))
    gateway = LLMGateway.__new__(LLMGateway)
    gateway.model = "fake-model"
    gateway._client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    assert gateway.analyze("system", "synthetic resume", job_comparison.JobComparisonResult) == result
    assert parse.call_args.kwargs["store"] is False


def test_service_startup_rejects_missing_provider_configuration(monkeypatch):
    from fastapi.testclient import TestClient
    import main
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "fake-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://fake-model")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY must be set"):
        with TestClient(main.app):
            pass


def test_short_text_uses_the_shared_extraction_floor(client, auth, pdf_store, fake_llm):
    pdf_store["short.pdf"] = make_pdf(["Synthetic short resume"])
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": CORRELATION_ID, "job_id": "job", "s3_key": "short.pdf",
        "job_description": "Python",
    })
    assert response.status_code == 422
    assert response.json()["error_code"] == "RESUME_UNREADABLE"
    assert response.json()["retryable"] is False
    assert not fake_llm.calls


@pytest.mark.parametrize("skills,experience,total", [(0, 0, 0), (100, 100, 100), (80, 91, 86)])
def test_total_is_computed_from_component_scores(client, auth, fake_llm, skills, experience, total):
    fake_llm.result = job_comparison.JobComparisonResult(
        skill_match_score=skills, experience_match_score=experience,
        resume_advice="Highlight your relevant projects. Clarify your demonstrated impact.",
        matched_skills=[], missing_skills=[], relevant_experience="Synthetic experience", other_gaps=[],
    )
    response = client.post("/job-comparison", headers=auth, json={
        "correlation_id": CORRELATION_ID, "job_id": "job", "s3_key": "resumes/ok.pdf",
        "job_description": "Python",
    })
    assert response.status_code == 200
    assert response.json()["match_score"] == total


@pytest.mark.parametrize("changes", [
    {"skill_match_score": -1}, {"experience_match_score": 101}, {"skill_match_score": 80.5},
    {"resume_advice": "Highlight projects. Clarify impact. Add examples."},
    {"resume_advice": 'Highlight projects. Clarify impact! "Add examples."'},
    {"resume_advice": " "}, {"resume_advice": "A" * 401},
])
def test_invalid_scores_or_excessive_advice_are_rejected(changes):
    from pydantic import ValidationError
    fields = dict(skill_match_score=80, experience_match_score=90,
                  resume_advice="Highlight your relevant projects.", matched_skills=[],
                  missing_skills=[], relevant_experience="Synthetic experience", other_gaps=[])
    with pytest.raises(ValidationError):
        job_comparison.JobComparisonResult(**(fields | changes))
