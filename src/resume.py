from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
import io
import os
import boto3
import pdfplumber
from openai import OpenAI

load_dotenv(override=True)

API_KEY = os.environ.get("OPENAI_API_KEY", "lm-studio")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("OPENAI_MODEL", "google/gemma-4-e4b")
INTERNAL_TOKEN = os.environ.get("INTERNAL_TOKEN")

internal_token_header = APIKeyHeader(name="X-Internal-Token")

def verify_internal_token(token: str = Depends(internal_token_header)):
    if token != INTERNAL_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal token",
        )

router = APIRouter(dependencies=[Depends(verify_internal_token)])
llm_client = OpenAI(base_url=BASE_URL, api_key=API_KEY)
s3_client = boto3.client(
    "s3",
    region_name=os.environ.get("AWS_REGION"),
    
)

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
    
    

def fetch_resume_bytes(s3_key: str) -> bytes:
    obj = s3_client.get_object(Bucket=os.environ.get("AWS_BUCKET_NAME"), Key=s3_key)
    return obj['Body'].read()

def extract_text(pdf_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def analyze_resume(resume_text: str) -> ResumeAnalysis:
    completion = llm_client.responses.parse(
        model = MODEL,
        input = [
          {"role": "system", "content": 
        "You are an ATS (Applicant Tracking System) resume analyzer. "
        "Given resume text, score its ATS-parseability and flag formatting "
        "and writing issues in the document itself — do not compare it against "
        "any specific job or role, since none is provided."
        },
        {"role": "user", "content": resume_text}
        ],
        text_format = ResumeAnalysis,
    )
    
    if completion.output_parsed is None:
        raise ValueError("LLM did not return a parsed ResumeAnalysis (refused or malformed response)")
    return completion.output_parsed


    
    
@router.post("/resume", response_model=resumeResponse)
async def resume_endpoint(request: ResumeRequest):
    pdf_bytes = fetch_resume_bytes(request.s3_key)
    resume_text = extract_text(pdf_bytes)
    print(f"Extracted Resume Text for analysis_id {resume_text[:200]}...")  # Print first 200 characters for debugging
    
    analysis = analyze_resume(resume_text)
    return resumeResponse(**analysis.model_dump(), model=MODEL)

    