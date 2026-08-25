import os
import json
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx
from dotenv import load_dotenv

from database import init_db, get_db, JobRecord
from telegram import send_telegram_alert

load_dotenv()
init_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobpilot")

app = FastAPI(
    title="JobPilot AI",
    description="AI-powered Job Analysis & Career Assistant Platform",
    version="1.0.0",
)

# Mount static directory for Frontend Dashboard
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class JobInput(BaseModel):
    id: Optional[int] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    description: str
    salary: Optional[str] = None
    publication_date: Optional[str] = None
    job_type: Optional[str] = None


class JobAnalysisRequest(BaseModel):
    job: JobInput
    user_profile: Optional[str] = (
        "Python Developer with experience in FastAPI, Docker, PostgreSQL, REST APIs, and AI integrations."
    )


class JobAnalysisResponse(BaseModel):
    id: Optional[int] = None
    job_id: Optional[int] = None
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    match_score: int
    seniority_level: str
    required_skills: List[str] = []
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    recommendation: str
    summary: str
    ai_status: str


@app.get("/")
def read_root():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to JobPilot AI Backend API. Visit /docs for OpenAPI specifications."}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "gemini_key_set": bool(os.getenv("GEMINI_API_KEY")),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
    }


@app.get("/jobs", response_model=List[JobAnalysisResponse])
def get_jobs(min_score: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    records = (
        db.query(JobRecord)
        .filter(JobRecord.match_score >= min_score)
        .order_by(JobRecord.match_score.desc(), JobRecord.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        JobAnalysisResponse(
            id=rec.id,
            job_id=rec.id,
            title=rec.title,
            company=rec.company,
            location=rec.location,
            url=rec.url,
            match_score=rec.match_score,
            seniority_level=rec.seniority_level,
            required_skills=rec.required_skills or [],
            matching_skills=rec.matching_skills or [],
            missing_skills=rec.missing_skills or [],
            recommendation=rec.recommendation,
            summary=rec.summary,
            ai_status="STORED",
        )
        for rec in records
    ]


@app.post("/analyze", response_model=JobAnalysisResponse)
async def analyze_job(request: JobAnalysisRequest, db: Session = Depends(get_db)):
    job = request.job
    user_profile = request.user_profile
    api_key = os.getenv("GEMINI_API_KEY")

    # Default fallback values if AI is not available
    match_score = 65
    seniority_level = "Middle"
    required_skills = ["Python", "FastAPI", "REST API"]
    matching_skills = ["Python", "FastAPI"]
    missing_skills = ["PostgreSQL"]
    recommendation = "CONSIDER"
    summary = "Базовый анализ: Вакансия частично совпадает с профилем (Python/FastAPI). Добавьте GEMINI_API_KEY для полного ИИ-скоринга."
    ai_status = "MOCK_FALLBACK"

    if api_key:
        prompt = f"""
You are an expert AI Career Coach and Recruiter. Analyze the following job description against the user's profile.

### User Profile:
{user_profile}

### Job Details:
- Title: {job.title}
- Company: {job.company or 'N/A'}
- Location: {job.location or 'N/A'}
- Description: {job.description}

### Task:
Analyze the match and respond with ONLY a valid JSON object with the following fields:
- "match_score": integer between 0 and 100 indicating how well the user fits this job.
- "seniority_level": string (e.g. "Junior", "Middle", "Senior", "Lead", "Unknown").
- "required_skills": list of key technical and soft skills required by the job.
- "matching_skills": list of skills the user possesses based on profile.
- "missing_skills": list of required skills the user seems to lack or should learn.
- "recommendation": string ("HIGHLY_RECOMMENDED" if match_score >= 75, "CONSIDER" if 50-74, "NOT_RECOMMENDED" if < 50).
- "summary": string (2-3 sentences in Russian explaining why this job matches or what is missing).
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed_ai = json.loads(raw_text)

                    match_score = parsed_ai.get("match_score", 0)
                    seniority_level = parsed_ai.get("seniority_level", "Unknown")
                    required_skills = parsed_ai.get("required_skills", [])
                    matching_skills = parsed_ai.get("matching_skills", [])
                    missing_skills = parsed_ai.get("missing_skills", [])
                    recommendation = parsed_ai.get("recommendation", "CONSIDER")
                    summary = parsed_ai.get("summary", "")
                    ai_status = "SUCCESS"
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            ai_status = "ERROR"

    # Save to Database
    db_job = JobRecord(
        title=job.title,
        company=job.company,
        location=job.location,
        url=job.url,
        description=job.description,
        salary=job.salary,
        publication_date=job.publication_date,
        job_type=job.job_type,
        match_score=match_score,
        seniority_level=seniority_level,
        required_skills=required_skills,
        matching_skills=matching_skills,
        missing_skills=missing_skills,
        recommendation=recommendation,
        summary=summary,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    # Trigger Telegram Alert if high match score
    if match_score >= 70:
        await send_telegram_alert(
            title=job.title,
            company=job.company or "",
            location=job.location or "",
            match_score=match_score,
            seniority=seniority_level,
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            recommendation=recommendation,
            summary=summary,
            url=job.url,
        )

    return JobAnalysisResponse(
        id=db_job.id,
        job_id=db_job.id,
        title=db_job.title,
        company=db_job.company,
        location=db_job.location,
        url=db_job.url,
        match_score=db_job.match_score,
        seniority_level=db_job.seniority_level,
        required_skills=db_job.required_skills,
        matching_skills=db_job.matching_skills,
        missing_skills=db_job.missing_skills,
        recommendation=db_job.recommendation,
        summary=db_job.summary,
        ai_status=ai_status,
    )


@app.post("/import/remotive")
async def import_remotive_jobs(limit: int = 5, db: Session = Depends(get_db)):
    remotive_url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=10"
    imported_count = 0

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(remotive_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to fetch jobs from Remotive API")

            jobs_data = resp.json().get("jobs", [])[:limit]

            for item in jobs_data:
                job_input = JobInput(
                    title=item.get("title", "Remote Developer"),
                    company=item.get("company_name"),
                    location=item.get("candidate_required_location", "Remote"),
                    url=item.get("url"),
                    description=item.get("description", "")[:2000],  # truncate html description
                    publication_date=item.get("publication_date"),
                    job_type=item.get("job_type"),
                )

                # Process via analyze logic
                await analyze_job(JobAnalysisRequest(job=job_input), db=db)
                imported_count += 1

            return {"status": "ok", "imported_count": imported_count}
    except Exception as e:
        logger.error(f"Remotive import error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "job_id": job_id}
