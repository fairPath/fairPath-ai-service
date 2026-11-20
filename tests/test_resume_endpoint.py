"""POST /resume: the Spring → AI service Analyze contract."""
import logging

from conftest import SYNTHETIC_RESUME_LINES, make_multipage_pdf, make_pdf

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
    # Formatting: contact fails (weight 5), length passes (3), dates not applicable.
    # 100 × (5·0 + 3·1) / 8 = 37.5, rounded half up to 38; overall (38 + 100 + 100) / 3 = 79.3
    assert body["scores"] == {"formatting": 38, "parseability": 100, "writing": 100, "overall": 79}


def test_three_page_resume_gets_a_document_level_too_long_issue(client, auth, pdf_store):
    pdf_store["resumes/long.pdf"] = make_multipage_pdf([SYNTHETIC_RESUME_LINES] * 3)

    body = client.post("/resume", json={**BODY, "s3_key": "resumes/long.pdf"}, headers=auth).json()

    [issue] = body["issues"]
    assert issue["issue_id"] == "fmt-001"
    assert issue["issue_type"] == "TOO_LONG"
    assert issue["category"] == "formatting"
    assert issue["severity"] == "medium"
    assert issue["snippet"] is None and issue["line_id"] is None
    # Contact passes (5), length fails (3), dates not applicable: 100 × 5 / 8 = 62.5 -> 63
    assert body["scores"] == {"formatting": 63, "parseability": 100, "writing": 100, "overall": 88}


def test_resume_without_standard_sections_gets_one_issue_per_missing_section(client, auth, pdf_store):
    lines = [line for line in SYNTHETIC_RESUME_LINES if line not in ("SKILLS", "EDUCATION")]
    pdf_store["resumes/sections.pdf"] = make_pdf(lines)

    body = client.post("/resume", json={**BODY, "s3_key": "resumes/sections.pdf"}, headers=auth).json()

    assert [(i["issue_id"], i["issue_type"]) for i in body["issues"]] == [
        ("prs-001", "MISSING_SECTION"),
        ("prs-002", "MISSING_SECTION"),
    ]
    # Parseability: unreadable passes (3), sections score 1/3 (2): 100 × (3 + 2/3) / 5 = 73.3 -> 73
    assert body["scores"]["parseability"] == 73


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
