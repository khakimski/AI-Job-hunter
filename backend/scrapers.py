import re
import logging
import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def scrape_habr_jobs(query: str = "Python", limit: int = 5) -> list:
    url = f"https://career.habr.com/vacancies?q={query}&type=all"
    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
            if resp.status_code == 200:
                matches = re.findall(
                    r'<a class="vacancy-card__title-link" href="([^"]+)">([^<]+)</a>', resp.text
                )
                for link, title in matches[:limit]:
                    full_url = f"https://career.habr.com{link}"
                    jobs.append({
                        "title": title.strip(),
                        "company": "Habr Career",
                        "location": "Remote / Россия",
                        "url": full_url,
                        "description": f"Вакансия с Хабр Карьера: {title.strip()}. Кликай по ссылке для подробностей.",
                        "source": "Habr Career"
                    })
    except Exception as e:
        logger.error(f"Error scraping Habr Career: {e}")
    return jobs


async def scrape_hh_jobs(query: str = "Python", limit: int = 5) -> list:
    url = f"https://hh.ru/search/vacancy?text={query}&schedule=remote"
    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
            if resp.status_code == 200:
                vids = list(set(re.findall(r'/vacancy/(\d+)', resp.text)))[:limit]
                for vid in vids:
                    jobs.append({
                        "title": f"Python Developer (HH.ru #{vid})",
                        "company": "HeadHunter Vacancy",
                        "location": "Удаленно / Россия",
                        "url": f"https://hh.ru/vacancy/{vid}",
                        "description": f"Вакансия с HeadHunter (HH.ru) ID: {vid}. Позиция Python / IT разработка. Кликай ссылку для просмотра на HH.ru.",
                        "source": "HeadHunter (HH.ru)"
                    })
    except Exception as e:
        logger.error(f"Error scraping HH.ru: {e}")
    return jobs


async def fetch_remotive_jobs(limit: int = 5) -> list:
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=10"
    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json().get("jobs", [])[:limit]
                for item in data:
                    jobs.append({
                        "title": item.get("title", "Remote Developer"),
                        "company": item.get("company_name", "Remotive"),
                        "location": item.get("candidate_required_location", "Remote"),
                        "url": item.get("url"),
                        "description": item.get("description", "")[:2000],
                        "source": "Remotive"
                    })
    except Exception as e:
        logger.error(f"Error fetching Remotive: {e}")
    return jobs
