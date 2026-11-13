from fastapi import FastAPI
from resume import router as resume_router
from job_comparison import router as job_comparison_router

app = FastAPI(title="fairPath AI Service")
app.include_router(resume_router)
app.include_router(job_comparison_router)


@app.get("/")
def read_root():
    return {"message": "fairPath AI Service is running!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
