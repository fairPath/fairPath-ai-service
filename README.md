# fairPath AI Service

FastAPI microservice handling resume analysis for PathAI. Stateless — never writes to Postgres; Spring Boot (`fairPath-backend`) is the sole DB writer and the only caller (never called directly by the frontend).

## Endpoints

- `POST /resume` — fetches a resume PDF from S3 by key, extracts text, redacts person names and direct contact details with Presidio, then analyzes the redacted text. Requires `X-Internal-Token` header (shared secret with `fairPath-backend`).
- `GET /health` — health check.

## Running locally

```
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env   # fill in values
uvicorn main:app --reload --app-dir src
```

## Environment variables

See `.env.example`. `OPENAI_BASE_URL`/`OPENAI_MODEL` point at LM Studio in dev, OpenAI in prod — swappable via env var, no code change.

## Deployment

Docker image via the included `Dockerfile`, deployed to Railway. The image installs spaCy's `en_core_web_sm` model. The endpoint redacts names found as standalone lines near the beginning or end of the resume, plus emails, phone numbers, URLs, and US-style street addresses, before passing the text to the configured AI model. It does not request organization or general location entities, so employer and school names are retained. PII detection is automated and can miss sensitive text. Configure `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` for the intended AI provider.

## Origin

Extracted from the `fastapi-course` learning workspace (Lessons 12-15) once the resume-analysis endpoint was feature-complete. That workspace remains as reference/teaching material and is not the deployed source going forward — this repo is.

## Tests

```
pip install -r requirements-dev.txt
pytest
```

Endpoint tests drive `POST /resume` through FastAPI's test client with the LLM gateway (`llm.py`) and the S3 fetch (`storage.py`) faked via dependency overrides. They use synthetic PDFs generated at test time; no real resume data belongs in this repo.
