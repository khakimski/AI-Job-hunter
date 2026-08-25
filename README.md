# JobPilot AI 🚀

AI-powered Job Discovery & Match Analysis Platform.

JobPilot AI — это умный ассистент по поиску и ИИ-анализу вакансий, поддерживающий автоматический парсинг, Gemini 2.5 Flash скоринг, хранение в базе данных и Telegram-уведомления.

## 📌 Основные возможности

- **🤖 AI Analysis (Gemini 2.5 Flash)**: Автоматический подсчёт Match Score (0–100%), определение грейда, совпавших и отсутствующих навыков, а также рекомендаций на русском языке.
- **📊 Web Dashboard**: Встроенный стеклянный веб-интерфейс (Glassmorphism) для управления вакансиями, поиска и мгновенного 1-click импорта.
- **⚡ 1-Click Remotive Import**: Прямой импорт и анализ IT-вакансий с международной биржи Remotive.
- **🗄️ PostgreSQL / SQLite Database**: Сохранение всех обработанных вакансий и их аналитики через SQLAlchemy.
- **📲 Telegram Alerts**: Мгновенные уведомления в Telegram при появлении подходящих вакансий (`match_score >= 70%`).
- **🔄 n8n Integration**: Готовый к импорту пресет сценария в папке `n8n/`.

## 🛠 Технологический стек

- **Backend:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, HTTPX
- **AI / LLM:** Google Gemini API (gemini-2.5-flash)
- **Database:** PostgreSQL (Docker) / SQLite (локально)
- **Orchestration:** n8n Workflow (`n8n/jobpilot_workflow.json`)
- **DevOps:** Docker, Docker Compose

## 📁 Структура проекта

```text
jobpilot-ai/
├── backend/
│   ├── static/
│   │   └── index.html        # Web Dashboard UI
│   ├── database.py           # SQLAlchemy DB models
│   ├── telegram.py           # Telegram bot notification module
│   ├── main.py               # FastAPI core application & API routes
│   ├── requirements.txt      # Python dependencies
│   └── Dockerfile            # Container definition
├── n8n/
│   └── jobpilot_workflow.json # n8n workflow export template
├── .env                      # Environment config template
├── .gitignore
├── docker-compose.yml        # Multi-container setup (Backend + PostgreSQL)
└── README.md
```

## 🚀 Быстрый запуск

### 1. Настройка окружения
Создайте или отредактируйте файл `.env`:
```env
PORT=8000
HOST=0.0.0.0
ENVIRONMENT=development

# Gemini API Key (для ИИ скоринга)
GEMINI_API_KEY=your_gemini_api_key_here

# Telegram Alerts (опционально)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 2. Запуск через Docker Compose (Рекомендуется)
```bash
docker compose up --build
```
- **Web Dashboard**: [http://localhost:8000](http://localhost:8000)
- **OpenAPI Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Локальный запуск на Python
```powershell
pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```
