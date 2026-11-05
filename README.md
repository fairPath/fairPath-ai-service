# fairPath AI Service

FastAPI microservice handling resume analysis for PathAI. Stateless — never writes to Postgres; Spring Boot (`fairPath-backend`) is the sole DB writer and the only caller (never called directly by the frontend).

## Endpoints

- `POST /resume` — fetches a resume PDF from S3 by key, extracts text, runs LLM-based ATS analysis, returns structured JSON. Requires `X-Internal-Token` header (shared secret with `fairPath-backend`).
- `GET /health` — health check.

## Running locally

```
pip install -r requirements.txt
cp .env.example .env   # fill in values
uvicorn main:app --reload --app-dir src
```

## Environment variables

See `.env.example`. `OPENAI_BASE_URL`/`OPENAI_MODEL` point at LM Studio in dev, OpenAI in prod — swappable via env var, no code change.

## Deployment

Docker image via the included `Dockerfile`, deployed to Railway.

## Origin

Extracted from the `fastapi-course` learning workspace (Lessons 12-15) once the resume-analysis endpoint was feature-complete. That workspace remains as reference/teaching material and is not the deployed source going forward — this repo is.
