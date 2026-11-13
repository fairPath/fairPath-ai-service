"""POST /resume: the Spring → AI service Analyze contract."""
import logging

KNOWN_PII = {
    "full_name": "Jane Testperson",
    "email": "jane.testperson@example.com",
    "phone": None,
}
BODY = {"correlation_id": "c-1", "s3_key": "resumes/ok.pdf", "known_pii": KNOWN_PII}


def test_clean_resume_returns_full_scores_and_no_issues(client, auth):
    response = client.post("/resume", json=BODY, headers=auth)

    assert response.status_code == 200
    assert response.json() == {
        "correlation_id": "c-1",
        "scores": {"formatting": 100, "parseability": 100, "writing": 100, "overall": 100},
        "issues": [],
        "model": None,  # the walking skeleton makes no LLM call
        "pipeline_version": "0.1.0",
    }


def test_resume_without_email_or_phone_gets_a_document_level_missing_contact_issue(client, auth):
    response = client.post(
        "/resume", json={**BODY, "s3_key": "resumes/no-contact.pdf"}, headers=auth
    )

    assert response.status_code == 200
    body = response.json()
    assert body["issues"] == [
        {
            "issue_id": "fmt-001",
            "issue_type": "MISSING_CONTACT",
            "category": "formatting",
            "source": "check",
            "severity": "high",
            "snippet": None,
            "line_id": None,
            "line_text": None,
            "section": None,
            "line_kind": None,
            "description": "No email address or phone number was found in your resume.",
            "suggestion": "Add an email address or phone number near the top so recruiters can reach you.",
        }
    ]
    # Formatting has only missing_contact so far; (0 + 100 + 100) / 3 = 66.67
    assert body["scores"] == {"formatting": 0, "parseability": 100, "writing": 100, "overall": 67}


def test_correlation_id_is_echoed(client, auth):
    response = client.post("/resume", json={**BODY, "correlation_id": "c-42"}, headers=auth)

    assert response.json()["correlation_id"] == "c-42"


def test_known_pii_fields_are_nullable(client, auth):
    body = {**BODY, "known_pii": {"full_name": None, "email": None, "phone": None}}

    assert client.post("/resume", json=body, headers=auth).status_code == 200


def test_old_request_contract_is_rejected(client, auth):
    old = {"analysis_id": "a-1", "s3_key": "resumes/ok.pdf", "user_id": "u-1"}

    assert client.post("/resume", json=old, headers=auth).status_code == 422


def test_missing_token_header_is_unauthorized(client):
    assert client.post("/resume", json=BODY).status_code == 401


def test_wrong_token_is_unauthorized(client):
    response = client.post("/resume", json=BODY, headers={"X-Internal-Token": "nope"})

    assert response.status_code == 401


def test_missing_s3_object_surfaces_as_server_error(client, auth):
    response = client.post(
        "/resume", json={**BODY, "s3_key": "resumes/missing.pdf"}, headers=auth
    )

    assert response.status_code == 500


def test_resume_text_never_reaches_stdout_or_logs(client, auth, capsys, caplog):
    caplog.set_level(logging.DEBUG)

    client.post("/resume", json=BODY, headers=auth)

    out, err = capsys.readouterr()
    captured = out + err + caplog.text
    assert "Built an internal tool" not in captured
    assert "Acme Widgets" not in captured
