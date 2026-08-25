# JobPilot AI 🚀

AI-powered Job Discovery & Analysis Assistant.

## 📌 Features
- **FastAPI Backend**: Fast, lightweight REST API for processing job vacancies.
- **Docker & Compose**: Fully containerized environment for seamless deployment.
- **Automated AI Scoring**: Ready for LLM integration (Gemini / OpenAI) to analyze and score job descriptions.

## 🛠 Tech Stack
- **Language:** Python 3.12
- **Framework:** FastAPI, Pydantic, Uvicorn
- **DevOps:** Docker, Docker Compose
- **Orchestration:** n8n

## 📁 Project Structure
```text
jobpilot-ai/
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── .env
├── .gitignore
├── docker-compose.yml
└── README.md
```

## 🚀 Getting Started

### 1. Run with Docker Compose
```bash
docker compose up --build
```
API docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 2. Run locally with Python
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
uvicorn backend.main:app --reload --port 8000
```
