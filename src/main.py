from fastapi import FastAPI
from contextlib import asynccontextmanager
from llm import validate_llm_config
from resume import router as resume_router
from job_comparison import router as job_comparison_router

@asynccontextmanager
async def lifespan(app):
    validate_llm_config()
    yield


app = FastAPI(title="fairPath AI Service", lifespan=lifespan)
app.include_router(resume_router)
app.include_router(job_comparison_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
