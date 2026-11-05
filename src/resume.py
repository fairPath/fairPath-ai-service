from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
import io
import os
import re
import boto3
import pdfplumber
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
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
# Load the NLP model once per service process, not once per resume request.
nlp_engine = NlpEngineProvider(
    nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
).create_engine()
pii_analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
pii_anonymizer = AnonymizerEngine()
address_recognizer = PatternRecognizer(
    supported_entity="ADDRESS",
    patterns=[
        Pattern(
            name="us_street_address",
            regex=(
                r"(?i)\b\d{1,6}\s+(?:[NSEW]\.?,?\s+)?"
                r"(?:[A-Z0-9.'#-]+\s+){1,5}"
                r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|"
                r"Drive|Dr|Court|Ct|Way|Place|Pl|Parkway|Pkwy)\b"
                r"(?:,?\s*(?:Apt|Unit|Suite|Ste|#)\s*[\w-]+)?"
            ),
            score=0.75,
        )
    ],
)
pii_analyzer.registry.add_recognizer(address_recognizer)
PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "URL", "ADDRESS"]
NAME_TOKEN = r"(?:[A-Z][A-Za-z]*|[A-Z]{2,})(?:[-'][A-Z]?[A-Za-z]+|[-'][A-Z]+)?"
NAME_LINE_PATTERN = re.compile(
    rf"(?P<name>{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{1,5}})(?:\s*\(({NAME_TOKEN})\))?"
)
RESUME_ROLE_WORDS = {
    "engineer", "developer", "designer", "manager", "analyst", "architect",
    "consultant", "scientist", "intern", "student", "resume", "curriculum",
}
PII_OPERATORS = {
    "DEFAULT": OperatorConfig("replace"),
    "PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"}),
    "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE]"}),
    "URL": OperatorConfig("replace", {"new_value": "[URL]"}),
    "ADDRESS": OperatorConfig("replace", {"new_value": "[ADDRESS]"}),
}
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
        return "\n".join(page.extract_text() or "" for page in pdf.pages)

def redact_pii(resume_text: str) -> str:
    findings = pii_analyzer.analyze(
        text=resume_text,
        entities=PII_ENTITIES,
        language="en",
    )
    # Redact person names only when they appear as standalone lines near the
    # beginning or end of the resume. This avoids person-like terms in prose.
    findings = [
        finding
        for finding in findings
        if finding.entity_type != "PERSON"
        and not (
            finding.entity_type == "URL"
            and resume_text[finding.start:finding.end].casefold() == "java.net"
            and resume_text[max(0, finding.start - 5):finding.start].casefold().endswith("java ")
        )
    ]

    lines = resume_text.splitlines(keepends=True)
    nonempty_line_indexes = [index for index, line in enumerate(lines) if line.strip()]
    edge_line_indexes = set(nonempty_line_indexes[:5] + nonempty_line_indexes[-5:])
    offset = 0
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip("\r\n").lstrip(" \t•·-*—–")
        if index in edge_line_indexes:
            name_match = NAME_LINE_PATTERN.fullmatch(line)
            if name_match:
                candidate = name_match.group(0)
                words = set(re.findall(r"[A-Za-z]+", candidate.casefold()))
                if not (words & RESUME_ROLE_WORDS):
                    start = offset + raw_line.find(candidate)
                    findings.append(
                        RecognizerResult(
                            entity_type="PERSON",
                            start=start,
                            end=start + len(candidate),
                            score=0.95,
                        )
                    )
        offset += len(raw_line)

    return pii_anonymizer.anonymize(
        text=resume_text,
        analyzer_results=findings,
        operators=PII_OPERATORS,
    ).text

def analyze_resume(resume_text: str) -> ResumeAnalysis:
    completion = llm_client.responses.parse(
        model=MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are an ATS (Applicant Tracking System) resume analyzer. "
                    "Given resume text, score its ATS-parseability and flag formatting "
                    "and writing issues in the document itself — do not compare it against "
                    "any specific job or role, since none is provided."
                ),
            },
            {"role": "user", "content": resume_text},
        ],
        text_format=ResumeAnalysis,
    )

    if completion.output_parsed is None:
        raise ValueError("LLM did not return a parsed ResumeAnalysis (refused or malformed response)")
    return completion.output_parsed

    
@router.post("/resume", response_model=resumeResponse)
async def resume_endpoint(request: ResumeRequest):
    pdf_bytes = fetch_resume_bytes(request.s3_key)
    resume_text = extract_text(pdf_bytes)
    redacted_text = redact_pii(resume_text)
    print(f"Redacted resume text for analysis_id {request.analysis_id}:\n{redacted_text}")
    analysis = analyze_resume(redacted_text)
    return resumeResponse(**analysis.model_dump(), model=MODEL)

