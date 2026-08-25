from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional


app = FastAPI(
    title="JobPilot AI",
    description="AI-powered job analysis API",
    version="0.1.0",
)


class Job(BaseModel):
    id: Optional[int] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    description: str
    salary: Optional[str] = None
    publication_date: Optional[str] = None
    job_type: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze_job(job: Job):
    return {
        "job_id": job.id,
        "title": job.title,
        "company": job.company,
        "match_score": 0,
        "recommendation": "PENDING",
        "message": "Job received successfully"
    }
