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
    from backend.scrapers import scrape_hh_jobs, scrape_hh_kz_jobs, scrape_habr_jobs, fetch_remotive_jobs
except ModuleNotFoundError:
    from database import init_db, get_db, JobRecord
    from telegram import send_telegram_alert
    from profile_manager import load_user_profile, save_user_profile
    from scrapers import scrape_hh_jobs, scrape_hh_kz_jobs, scrape_habr_jobs, fetch_remotive_jobs


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


@app.delete("/jobs/clear_all")
def clear_all_jobs(db: Session = Depends(get_db)):
    """Delete all jobs from the database."""
    deleted_count = db.query(JobRecord).count()
    db.query(JobRecord).delete()
    db.commit()
    return {"status": "ok", "deleted_count": deleted_count}


# ---------- Keyword-based fast scorer (zero API tokens) ----------
KEYWORD_SKILLS = [
    "chatbot", "conversational ai", "nlp", "nlu", "dialogue", "intent",
    "automation", "no-code", "low-code", "n8n", "zapier", "make.com",
    "voiceflow", "botpress", "python", "fastapi", "ai", "ml", "llm",
    "openai", "gemini", "gpt", "rasa", "telegram bot", "support automation",
    "workflow", "crm", "api", "remote", "удаленно", "чат-бот", "автоматизация",
]

def keyword_score(text: str) -> tuple[int, list, list]:
    """Return (score 0-100, matching_keywords, missing_keywords) using pure keyword matching."""
    text_lower = (text or "").lower()
    matched = [kw for kw in KEYWORD_SKILLS if kw in text_lower]
    score = min(100, int(len(matched) / max(len(KEYWORD_SKILLS), 1) * 100) + 30)
    missing = [kw for kw in ["python", "automation", "chatbot", "nlp"] if kw not in text_lower]
    return score, matched, missing
# ------------------------------------------------------------------


@app.post("/analyze", response_model=JobAnalysisResponse)
async def analyze_job(request: JobAnalysisRequest, db: Session = Depends(get_db)):
    job = request.job

    # ── 1. URL deduplication — skip already stored jobs ──
    if job.url:
        existing = db.query(JobRecord).filter(JobRecord.url == job.url).first()
        if existing:
            return JobAnalysisResponse(
                id=existing.id, job_id=existing.id,
                title=existing.title, company=existing.company,
                location=existing.location, url=existing.url,
                match_score=existing.match_score,
                seniority_level=existing.seniority_level,
                required_skills=existing.required_skills,
                matching_skills=existing.matching_skills,
                missing_skills=existing.missing_skills,
                recommendation=existing.recommendation,
                summary=existing.summary,
                ai_status="CACHED",
            )

    # ── 2. Fast keyword pre-score (0 tokens) ──
    combined_text = f"{job.title} {job.description or ''}"
    kw_score, kw_matched, kw_missing = keyword_score(combined_text)

    profile_data = load_user_profile()
    user_profile = request.user_profile or profile_data.get("resume", "")
    min_score_threshold = profile_data.get("min_score", 70)
    api_key = os.getenv("GEMINI_API_KEY")

    # Defaults from keyword scoring
    match_score = kw_score
    seniority_level = "Unknown"
    required_skills = kw_matched[:8]
    matching_skills = kw_matched[:5]
    missing_skills = kw_missing
    recommendation = "HIGHLY_RECOMMENDED" if kw_score >= 75 else "CONSIDER" if kw_score >= 50 else "NOT_RECOMMENDED"
    summary = f"Keyword-анализ: совпало {len(kw_matched)} ключевых слов. Скор: {kw_score}/100."
    ai_status = "KEYWORD_ONLY"

    # ── 3. Gemini AI only if keyword score ≥ 40 (promising job) AND API key available ──
    if api_key and kw_score >= 40:
        # Trim description to max 800 chars to save tokens
        short_desc = (job.description or "")[:800]
        # Trim resume to first 1200 chars to save tokens
        short_resume = (user_profile or "")[:1200]

        prompt = f"""You are an AI Career Coach. Analyze the job vs candidate profile. Respond ONLY with valid JSON.

Profile (excerpt):
{short_resume}

Job:
- Title: {job.title}
- Location: {job.location or 'N/A'}
- Description: {short_desc}

JSON fields required:
{{"match_score": 0-100, "seniority_level": "Junior|Middle|Senior|Lead", "required_skills": [...], "matching_skills": [...], "missing_skills": [...], "recommendation": "HIGHLY_RECOMMENDED|CONSIDER|NOT_RECOMMENDED", "summary": "2 sentences in Russian"}}"""

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 512},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(gemini_url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    parsed_ai = json.loads(raw_text)
                    match_score = parsed_ai.get("match_score", kw_score)
                    seniority_level = parsed_ai.get("seniority_level", "Unknown")
                    required_skills = parsed_ai.get("required_skills", [])
                    matching_skills = parsed_ai.get("matching_skills", [])
                    missing_skills = parsed_ai.get("missing_skills", [])
                    recommendation = parsed_ai.get("recommendation", recommendation)
                    summary = parsed_ai.get("summary", summary)
                    ai_status = "AI_SUCCESS"
                elif res.status_code == 429:
                    logger.warning("Gemini quota exhausted — falling back to keyword scoring")
                    ai_status = "QUOTA_EXCEEDED_KEYWORD_FALLBACK"
                else:
                    logger.warning(f"Gemini returned {res.status_code}")
                    ai_status = f"GEMINI_ERROR_{res.status_code}"
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            ai_status = "ERROR_KEYWORD_FALLBACK"
    elif kw_score < 40:
        # Job didn't pass keyword filter — skip Gemini, save tokens
        ai_status = "SKIPPED_LOW_KW_SCORE"


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
async def import_all_sites(
    days: int = 7,
    limit_per_site: int = 3,
    location_mode: str = "kz_all",
    db: Session = Depends(get_db)
):
    """
    Imports jobs from all sources filtered for Kazakhstan availability:
    - HH.kz: Remote / Astana office / Almaty office (based on location_mode)
    - HH.ru: Remote only (accessible from Kazakhstan)
    - Habr Career: Remote (СНГ-friendly)
    - Remotive: Worldwide remote
    location_mode options: kz_all | kz_remote | astana | almaty
    """
    imported_count = 0
    all_jobs = []

    # HH.kz — remote + Astana + Almaty (or filtered by mode)
    hh_kz_jobs = await scrape_hh_kz_jobs(
        query="Python AI Automation", location_mode=location_mode, days=days, limit=limit_per_site
    )
    all_jobs.extend(hh_kz_jobs)

    # Habr Career — remote СНГ (always accessible from Kazakhstan)
    habr_jobs = await scrape_habr_jobs(query="Python AI", limit=limit_per_site)
    all_jobs.extend(habr_jobs)

    # HH.ru — remote only (accessible from Kazakhstan)
    hh_jobs = await scrape_hh_jobs(query="Python AI", days=days, limit=limit_per_site)
    all_jobs.extend(hh_jobs)

    # Remotive — worldwide remote
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

    return {
        "status": "ok",
        "imported_count": imported_count,
        "days_filter": days,
        "location_mode": location_mode,
        "sources": ["HH.kz (Казахстан)", "Habr Career", "HH.ru Remote", "Remotive Worldwide"],
    }


@app.post("/import/hh_kz")
async def import_hh_kz_endpoint(
    days: int = 7,
    limit: int = 5,
    location_mode: str = "kz_all",
    db: Session = Depends(get_db)
):
    """
    Imports from HH.kz with Kazakhstan location filter:
    location_mode: kz_all | kz_remote | astana | almaty
    """
    jobs = await scrape_hh_kz_jobs(
        query="Python AI Automation", location_mode=location_mode, days=days, limit=limit
    )
    for item in jobs:
        job_input = JobInput(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            url=item["url"],
            description=item["description"],
        )
        await analyze_job(JobAnalysisRequest(job=job_input), db=db)
    return {"status": "ok", "imported_count": len(jobs), "days_filter": days, "location_mode": location_mode}



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
