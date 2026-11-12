import os
from typing import Callable

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

load_dotenv(override=True)

from extraction import extract_text  # noqa: E402
from llm import LLMGateway, get_llm  # noqa: E402
from redaction import redact_pii  # noqa: E402
from storage import fetch_resume_bytes  # noqa: E402

INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

internal_token_header = APIKeyHeader(name="X-Internal-Token")


def verify_internal_token(token: str = Depends(internal_token_header)):
    if token != INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal token",
        )


def get_resume_fetcher() -> Callable[[str], bytes]:
    return fetch_resume_bytes


router = APIRouter(dependencies=[Depends(verify_internal_token)])


class IssueDetail(BaseModel):
    issue_type: str
    description: str
    suggestion: str


class ResumeAnalysis(BaseModel):
    ats_parseability_score: int
    experience_years: int
    skills: list[str]
    formatting_issues: list[str]
    writing_issues: list[IssueDetail]
    suggestions: list[str]


class ResumeRequest(BaseModel):
    analysis_id: str
    s3_key: str
    user_id: str


class resumeResponse(BaseModel):
    ats_parseability_score: int
    experience_years: int
    skills: list[str]
    formatting_issues: list[str]
    writing_issues: list[IssueDetail]
    suggestions: list[str]
    model: str


ANALYZE_SYSTEM_PROMPT = (
    "You are an ATS (Applicant Tracking System) resume analyzer. "
    "Given resume text, score its ATS-parseability and flag formatting "
    "and writing issues in the document itself — do not compare it against "
    "any specific job or role, since none is provided."
)


@router.post("/resume", response_model=resumeResponse)
async def resume_endpoint(
    request: ResumeRequest,
    llm: LLMGateway = Depends(get_llm),
    fetch_resume: Callable[[str], bytes] = Depends(get_resume_fetcher),
):
    pdf_bytes = fetch_resume(request.s3_key)
    resume_text = extract_text(pdf_bytes)
    redacted_text = redact_pii(resume_text)
    print(f"Redacted resume text for analysis_id {request.analysis_id}:\n{redacted_text}")
    analysis = llm.analyze(ANALYZE_SYSTEM_PROMPT, redacted_text, ResumeAnalysis)
    return resumeResponse(**analysis.model_dump(), model=llm.model)
