BODY = {"analysis_id": "a-1", "s3_key": "resumes/ok.pdf", "user_id": "u-1"}


def test_analyze_returns_analysis_with_model(client, auth, fake_llm):
    response = client.post("/resume", json=BODY, headers=auth)

    assert response.status_code == 200
    assert response.json() == {
        "ats_parseability_score": 80,
        "experience_years": 4,
        "skills": ["Python", "FastAPI"],
        "formatting_issues": ["Inconsistent date format"],
        "writing_issues": [
            {
                "issue_type": "weak_verb",
                "description": "Bullet only lists a duty.",
                "suggestion": "Show the outcome.",
            }
        ],
        "suggestions": ["Quantify your impact."],
        "model": "fake-model",
    }
    assert len(fake_llm.calls) == 1


def test_llm_receives_redacted_text_never_contact_details(client, auth, fake_llm):
    client.post("/resume", json=BODY, headers=auth)

    sent = fake_llm.calls[0]["user"]
    assert "jane.testperson@example.com" not in sent
    assert "[EMAIL]" in sent
    assert "Software Engineer, Acme Widgets" in sent  # content survives


def test_missing_token_header_is_unauthorized(client, fake_llm):
    response = client.post("/resume", json=BODY)

    assert response.status_code == 401
    assert fake_llm.calls == []


def test_wrong_token_is_unauthorized(client, fake_llm):
    response = client.post("/resume", json=BODY, headers={"X-Internal-Token": "nope"})

    assert response.status_code == 401
    assert fake_llm.calls == []


def test_invalid_body_is_unprocessable(client, auth):
    response = client.post("/resume", json={"s3_key": "resumes/ok.pdf"}, headers=auth)

    assert response.status_code == 422


def test_llm_failure_surfaces_as_server_error(client, auth, fake_llm):
    fake_llm.error = ValueError("LLM did not return a parsed ResumeAnalysis")

    response = client.post("/resume", json=BODY, headers=auth)

    assert response.status_code == 500


def test_missing_s3_object_surfaces_as_server_error(client, auth, fake_llm):
    response = client.post(
        "/resume", json={**BODY, "s3_key": "resumes/missing.pdf"}, headers=auth
    )

    assert response.status_code == 500
    assert fake_llm.calls == []
