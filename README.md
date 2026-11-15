# fairPath AI Service

FastAPI service for resume analysis and job comparison. It is stateless with respect to application data and never reads or writes database tables. Next.js coordinates resume analysis with this service and Spring. Saved-job comparisons are queued durably in PostgreSQL and processed by a worker inside Spring. Spring is the only service that reads and writes application tables.

## Endpoints

- `POST /resume` — Analyze. Requires the `X-Internal-Token` header (shared secret with `PathAI-backend`).
  - Request: `{ correlation_id, s3_key, known_pii: { full_name, email, phone } }` (each `known_pii` field nullable; deny-list only).
  - Response: `{ correlation_id, scores: { formatting, parseability, writing, overall }, issues: [IssueDetail], model, pipeline_version }`. Models live in `src/contract.py`.
  - Fetches the PDF from S3 by key, extracts the text, runs the Checks (`src/checks.py`) and the Scorer (`src/scorer.py`). Weights, Issue types and `pipeline_version` are in `src/analysis_config.py`; bump `PIPELINE_VERSION` on any change to prompt, rubric, Checks, weights or model.
  - Walking skeleton: only the `MISSING_CONTACT` Check runs and no LLM call is made, so `model` is `null`. A Category with no components yet scores 100. The redactor and the LLM gateway (`src/redaction.py`, `src/llm.py`) are kept for the slices that add the first LLM call.
  - Never logs Resume text; only the `correlation_id` and counts.
- `POST /job-comparison` — fetches the latest active resume from its live S3 key, extracts and redacts its text with Presidio, and returns a structured resume-versus-job comparison. Requires `X-Internal-Token`. Scanned PDFs without extractable text return HTTP 422.
- `GET /health` — health check.

## Running locally

```
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env   # fill in values
uvicorn main:app --reload --app-dir src
```

## Environment variables

See `.env.example`. `OPENAI_BASE_URL`/`OPENAI_MODEL` can point at LM Studio in development or another compatible model provider in production.

## Background comparisons

Comparison requests include a UUID `correlation_id`, echoed in success and in safe error envelopes `{correlation_id, error_code, retryable}`. Deploy with the companion explicit-comparison backend/frontend changes. Configure the backend's `FAIRPATH_AI_SERVICE_URL` and `FAIRPATH_AI_INTERNAL_TOKEN` (matching this service's `INTERNAL_TOKEN`). No additional worker process is needed. See the backend README for recovery and retry behavior.

## Deployment

Docker image via the included `Dockerfile`, deployed to Railway. The image installs spaCy's `en_core_web_sm` model. The endpoint redacts names found as standalone lines near the beginning or end of the resume, plus emails, phone numbers, URLs, and US-style street addresses, before passing the text to the configured AI model. It does not request organization or general location entities, so employer and school names are retained. PII detection is automated and can miss sensitive text. Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` for the intended AI provider.

## Origin

Extracted from the `fastapi-course` learning workspace (Lessons 12-15) once the resume-analysis endpoint was feature-complete. That workspace remains as reference/teaching material and is not the deployed source going forward — this repo is.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

Endpoint tests drive `POST /resume` through FastAPI's test client with the S3 fetch (`storage.py`) faked via a dependency override; the Scorer and the Checks also have pure unit tests. They use synthetic PDFs generated at test time; no real resume data belongs in this repo.

Model requests use `store=False`. Comparisons distinguish terminal input/configuration errors from transient provider/network failures. Spring persists the error code and retryability; user JWT failures and internal AI-token failures remain separate.

Provider configuration is required at startup: set OPENAI_MODEL, OPENAI_BASE_URL and OPENAI_API_KEY explicitly (use the local provider URL/model and its dummy key for local development). OPENAI_TIMEOUT_SECONDS is optional and defaults to 90. The SDK does not retry internally; Spring owns the bounded comparison retries.

## Job match score

Comparison rubric 0.3.0 rates how competitive the resume's demonstrated experience is
for the supplied role; it is not a calibrated probability of being hired.
The rubric credits transferable engineering experience, distinguishes essential from
preferred requirements, and accounts for the limited evidence in short job snippets.
It returns skill match and relevant experience match scores. The service computes the total
from a 50/50 weighted average, rounded half up. It also returns resume advice limited
to two sentences and 400 characters, based on truthful evidence in the supplied resume.
Weights, advice limits and score bands live in
`src/job_comparison_config.py`; bump the comparison rubric version when they or the prompt change.

Scores of 75–89 indicate a strong candidate, 60–74 a credible candidate, 40–59 a stretch,
20–39 a weak fit, and 0–19 a largely unrelated background; 90–100 is exceptional fit.
Missing a preferred framework alone should not make an otherwise relevant software
engineer a single-digit match. Material specialization and seniority gaps still count.
These anchors guide the model; they have not been calibrated against real hiring outcomes.
Existing saved scores change only when the user explicitly runs another match check.

AI endpoints reuse `ai_errors.call_ai` and `AiErrorRoute` for provider-error classification
and safe correlated responses. Features supply request content and a success schema;
the comparison route only specializes its existing validation error code. The shared
`errors.error_response` forwards validated `Retry-After` seconds or HTTP dates on retryable
failures, including provider rate limits and server failures. Other provider headers and
raw error text are not forwarded. Spring schedules the later of its configured backoff
and this waiting period; attempt limits and error classifications are unchanged.
