import logging
import os
from typing import Callable

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

load_dotenv(override=True)

from analysis_config import PIPELINE_VERSION  # noqa: E402
from contract import AnalyzeRequest, AnalyzeResponse  # noqa: E402
from errors import ExtractionError, error_response  # noqa: E402
from extraction import extract_resume_text  # noqa: E402
from pipeline import analyze_text  # noqa: E402
from storage import fetch_resume_bytes  # noqa: E402

logger = logging.getLogger(__name__)

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


@router.post("/resume", response_model=AnalyzeResponse)
def resume_endpoint(
    request: AnalyzeRequest,
    fetch_resume: Callable[[str], bytes] = Depends(get_resume_fetcher),
):
    # Walking skeleton: Checks and the Scorer only, no LLM call, so nothing is
    # redacted yet. `known_pii` is accepted for the redaction deny-list to come.
    pdf_bytes = fetch_resume(request.s3_key)
    try:
        extracted_text = extract_resume_text(pdf_bytes, request.correlation_id)
    except ExtractionError as e:
        logger.info("analysis rejected correlation_id=%s error_code=%s", request.correlation_id, e.error_code)
        return error_response(e.status_code, request.correlation_id, e.error_code, e.retryable)
    scores, issues = analyze_text(extracted_text)
    # Never log Resume text, raw or redacted.
    logger.info(
        "analysis completed correlation_id=%s issues=%d overall=%d",
        request.correlation_id,
        len(issues),
        scores.overall,
    )
    return AnalyzeResponse(
        correlation_id=request.correlation_id,
        scores=scores,
        issues=issues,
        model=None,
        pipeline_version=PIPELINE_VERSION,
    )
