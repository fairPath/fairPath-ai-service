import job_comparison

from conftest import make_pdf


def test_comparison_uses_gateway_and_updates_result(client, auth, fake_llm):
    fake_llm.result = job_comparison.JobComparisonResult(
        match_score=85,
        matched_skills=["Python"],
        missing_skills=["Java"],
        relevant_experience="Software engineering experience",
        other_gaps=[],
    )
    response = client.post(
        "/job-comparison",
        headers=auth,
        json={"job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python and Java"},
    )
    assert response.status_code == 200
    assert response.json()["match_score"] == 85
    assert response.json()["model"] == "fake-model"
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
        json={"job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python"},
    )
    assert response.status_code == 401
    assert not fake_llm.calls


def test_blank_pdf_rejected_before_model(client, auth, pdf_store, fake_llm):
    pdf_store["blank.pdf"] = make_pdf([""])
    response = client.post(
        "/job-comparison", headers=auth,
        json={"job_id": "job-1", "s3_key": "blank.pdf", "job_description": "Python"},
    )
    assert response.status_code == 422
    assert not fake_llm.calls


def test_model_failure_returns_error_for_worker_retry(client, auth, fake_llm):
    fake_llm.error = RuntimeError("Model unavailable")
    response = client.post(
        "/job-comparison", headers=auth,
        json={"job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": "Python"},
    )
    assert response.status_code == 500
    assert len(fake_llm.calls) == 1


def test_full_description_including_final_segment_reaches_model(client, auth, fake_llm):
    fake_llm.result = job_comparison.JobComparisonResult(
        match_score=85, matched_skills=[], missing_skills=[], relevant_experience="", other_gaps=[]
    )
    description = "A" * 255 + "B" * 252 + "C" * 1000 + " FINAL_REQUIREMENT"
    response = client.post(
        "/job-comparison", headers=auth,
        json={"job_id": "job-1", "s3_key": "resumes/ok.pdf", "job_description": description},
    )
    assert response.status_code == 200
    assert fake_llm.calls[0]["user"].endswith("Job description:\n" + description)
