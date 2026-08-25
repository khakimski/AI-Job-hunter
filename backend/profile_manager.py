import os
import json

PROFILE_FILE = os.path.join(os.path.dirname(__file__), "user_profile.json")

DEFAULT_PROFILE = {
    "target_role": "Python / FastAPI / AI Developer",
    "min_score": 70,
    "resume": (
        "Middle/Senior Python Developer with 3+ years of experience in Web & AI Development.\n"
        "Technical Skills: Python, FastAPI, Asyncio, Docker, Docker Compose, PostgreSQL, SQLAlchemy, REST APIs.\n"
        "AI & LLM Skills: Google Gemini API, OpenAI API, LangChain, Prompt Engineering, RAG.\n"
        "DevOps & Tools: Git, GitHub, Linux, n8n, CI/CD, Uvicorn, Pydantic.\n"
        "Languages: Russian (Native), English (Intermediate/B2)."
    )
}


def load_user_profile() -> dict:
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PROFILE.copy()


def save_user_profile(profile_data: dict) -> dict:
    current = load_user_profile()
    current.update(profile_data)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current
