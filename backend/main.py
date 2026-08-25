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

try:
    from backend.database import init_db, get_db, JobRecord
    from backend.telegram import send_telegram_alert
    from backend.profile_manager import load_user_profile, save_user_profile
    from backend.scrapers import scrape_hh_jobs, scrape_habr_jobs, fetch_remotive_jobs
except ModuleNotFoundError:
    from database import init_db, get_db, JobRecord
    from telegram import send_telegram_alert
    from profile_manager import load_user_profile, save_user_profile
    from scrapers import scrape_hh_jobs, scrape_habr_jobs, fetch_remotive_jobs

load_dotenv()
init_db()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobpilot")

app = FastAPI(
    title="JobPilot AI",
    description="AI-powered Job Analysis & Multi-Site Career Assistant Platform",
    version="1.1.0",
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
    user_profile: Optional[str] = None


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


class UserProfileSchema(BaseModel):
    target_role: Optional[str] = "Python / FastAPI / AI Developer"
    min_score: Optional[int] = 70
    resume: str


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


@app.get("/profile")
def get_profile():
    return load_user_profile()


@app.post("/profile")
def update_profile(profile: UserProfileSchema):
    updated = save_user_profile(profile.model_dump())
    return {"status": "updated", "profile": updated}


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
    
    # Load custom user resume if not provided explicitly
    profile_data = load_user_profile()
    user_profile = request.user_profile or profile_data.get("resume", "")
    min_score_threshold = profile_data.get("min_score", 70)

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
You are an expert AI Career Coach and Recruiter. Analyze the following job description against the user's custom profile and resume.

### Candidate Profile & Resume:
{user_profile}

### Job Details:
- Title: {job.title}
- Company: {job.company or 'N/A'}
- Location: {job.location or 'N/A'}
- Description: {job.description}

### Task:
Analyze the match and respond with ONLY a valid JSON object with the following fields:
- "match_score": integer between 0 and 100 indicating how well the candidate fits this job.
- "seniority_level": string (e.g. "Junior", "Middle", "Senior", "Lead", "Unknown").
- "required_skills": list of key technical and soft skills required by the job.
- "matching_skills": list of skills the candidate possesses based on profile/resume.
- "missing_skills": list of required skills the candidate seems to lack or should learn.
- "recommendation": string ("HIGHLY_RECOMMENDED" if match_score >= 75, "CONSIDER" if 50-74, "NOT_RECOMMENDED" if < 50).
- "summary": string (2-3 sentences in Russian explaining why this job matches or what is missing).
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
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

    # Trigger Telegram Alert if match_score exceeds configured threshold
    if match_score >= min_score_threshold:
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


@app.post("/import/all")
async def import_all_sites(limit_per_site: int = 3, db: Session = Depends(get_db)):
    imported_count = 0
    all_jobs = []

    # Fetch from Habr Career
    habr_jobs = await scrape_habr_jobs(query="Python", limit=limit_per_site)
    all_jobs.extend(habr_jobs)

    # Fetch from HH.ru
    hh_jobs = await scrape_hh_jobs(query="Python", limit=limit_per_site)
    all_jobs.extend(hh_jobs)

    # Fetch from Remotive
    remotive_jobs = await fetch_remotive_jobs(limit=limit_per_site)
    all_jobs.extend(remotive_jobs)

    for item in all_jobs:
        job_input = JobInput(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            url=item["url"],
            description=item["description"],
        )
        await analyze_job(JobAnalysisRequest(job=job_input), db=db)
        imported_count += 1

    return {"status": "ok", "imported_count": imported_count, "sources": ["HH.ru", "Habr Career", "Remotive"]}


@app.post("/import/remotive")
async def import_remotive_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    jobs = await fetch_remotive_jobs(limit=limit)
    for item in jobs:
        job_input = JobInput(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            url=item["url"],
            description=item["description"],
        )
        await analyze_job(JobAnalysisRequest(job=job_input), db=db)
    return {"status": "ok", "imported_count": len(jobs)}


@app.post("/import/hh")
async def import_hh_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    jobs = await scrape_hh_jobs(limit=limit)
    for item in jobs:
        job_input = JobInput(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            url=item["url"],
            description=item["description"],
        )
        await analyze_job(JobAnalysisRequest(job=job_input), db=db)
    return {"status": "ok", "imported_count": len(jobs)}


@app.post("/import/habr")
async def import_habr_endpoint(limit: int = 5, db: Session = Depends(get_db)):
    jobs = await scrape_habr_jobs(limit=limit)
    for item in jobs:
        job_input = JobInput(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            url=item["url"],
            description=item["description"],
        )
        await analyze_job(JobAnalysisRequest(job=job_input), db=db)
    return {"status": "ok", "imported_count": len(jobs)}


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobRecord).filter(JobRecord.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"status": "deleted", "job_id": job_id}
