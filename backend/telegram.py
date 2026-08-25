import os
import logging
import httpx

logger = logging.getLogger(__name__)


async def send_telegram_alert(
    title: str,
    company: str,
    location: str,
    match_score: int,
    seniority: str,
    matching_skills: list,
    missing_skills: list,
    recommendation: str,
    summary: str,
    url: str = None
):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.info("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False

    emoji = "🔥" if match_score >= 80 else "⚡"
    
    skills_text = ", ".join(matching_skills[:5]) if matching_skills else "N/A"
    missing_text = ", ".join(missing_skills[:3]) if missing_skills else "None"
    job_link = f'<a href="{url}">🔗 Ссылка на вакансию</a>' if url else ""

    message = (
        f"{emoji} <b>Новая подходящая вакансия!</b> ({match_score}% match)\n\n"
        f"📌 <b>Должность:</b> {title}\n"
        f"🏢 <b>Компания:</b> {company or 'Не указана'}\n"
        f"📍 <b>Локация:</b> {location or 'Удаленно / Не указана'}\n"
        f"🎯 <b>Грейд:</b> {seniority}\n"
        f"💡 <b>Рекомендация:</b> {recommendation}\n\n"
        f"✅ <b>Совпавшие навыки:</b> {skills_text}\n"
        f"⚠️ <b>Изучить:</b> {missing_text}\n\n"
        f"📝 <b>ИИ Вывод:</b> {summary}\n\n"
        f"{job_link}"
    )

    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(telegram_url, json=payload)
            if resp.status_code == 200:
                logger.info("Telegram alert sent successfully!")
                return True
            elif resp.status_code == 403 and "bot can't send messages to the bot" in resp.text:
                logger.warning("Telegram Alert Error: TELEGRAM_CHAT_ID in .env is set to the bot itself (@khakimski_bot). Please change TELEGRAM_CHAT_ID to your personal Telegram User ID (get it from @userinfobot) or your channel username.")
                return False
            else:
                logger.error(f"Failed to send Telegram alert: {resp.status_code} - {resp.text}")
                return False

    except Exception as e:
        logger.error(f"Error sending Telegram notification: {e}")
        return False
