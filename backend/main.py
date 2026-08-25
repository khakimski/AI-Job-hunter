import os
import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="JobPilot AI",
    description="AI-powered job analysis API using Gemini",
    version="0.2.0",
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


class JobAnalysisRequest(BaseModel):
    job: Job
    user_profile: Optional[str] = (
        "Python Developer with experience in FastAPI, Docker, PostgreSQL, REST APIs, and AI integrations."
    )


class JobAnalysisResponse(BaseModel):
    job_id: Optional[int] = None
    title: str
    company: Optional[str] = None
    match_score: int
    seniority_level: str
    required_skills: List[str] = []
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    recommendation: str
    summary: str
    ai_status: str


@app.get("/health")
def health():
    return {"status": "ok", "gemini_key_set": bool(os.getenv("GEMINI_API_KEY"))}


@app.post("/analyze", response_model=JobAnalysisResponse)
async def analyze_job(request: JobAnalysisRequest):
    job = request.job
    user_profile = request.user_profile
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        # Fallback response when GEMINI_API_KEY is missing
        return JobAnalysisResponse(
            job_id=job.id,
            title=job.title,
            company=job.company,
            match_score=50,
            seniority_level="Unknown",
            required_skills=["Python", "FastAPI"],
            matching_skills=["Python"],
            missing_skills=["FastAPI"],
            recommendation="CONSIDER",
            summary="GEMINI_API_KEY not configured in .env. Returning basic mock analysis. Please set GEMINI_API_KEY to enable AI scoring.",
            ai_status="MOCK_FALLBACK",
        )

    # Gemini AI Analysis Prompt
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
            if res.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Gemini API Error ({res.status_code}): {res.text}",
                )

            data = res.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_ai = json.loads(raw_text)

            return JobAnalysisResponse(
                job_id=job.id,
                title=job.title,
                company=job.company,
                match_score=parsed_ai.get("match_score", 0),
                seniority_level=parsed_ai.get("seniority_level", "Unknown"),
                required_skills=parsed_ai.get("required_skills", []),
                matching_skills=parsed_ai.get("matching_skills", []),
                missing_skills=parsed_ai.get("missing_skills", []),
                recommendation=parsed_ai.get("recommendation", "CONSIDER"),
                summary=parsed_ai.get("summary", ""),
                ai_status="SUCCESS",
            )

    except Exception as e:
        return JobAnalysisResponse(
            job_id=job.id,
            title=job.title,
            company=job.company,
            match_score=0,
            seniority_level="Unknown",
            required_skills=[],
            matching_skills=[],
            missing_skills=[],
            recommendation="ERROR",
            summary=f"Error processing AI analysis: {str(e)}",
            ai_status="ERROR",
        )

