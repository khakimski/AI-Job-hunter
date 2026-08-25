import re
import logging
import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# HH Kazakhstan Area IDs
ASTANA_AREA_ID = "159"
ALMATY_AREA_ID = "160"


async def scrape_hh_kz_jobs(query: str = "Python AI Automation", location_mode: str = "kz_all", days: int = 7, limit: int = 5) -> list:
    """
    Scrapes HeadHunter Kazakhstan (hh.kz) filtered by location:
    - kz_remote : Full Remote (schedule=remote)
    - astana    : Office/Hybrid in Astana (area=159)
    - almaty    : Office/Hybrid in Almaty (area=160)
    - kz_all    : Remote + Astana + Almaty combined (limit applies per sub-URL)
    """
    jobs = []
    urls_to_fetch = []

    if location_mode == "kz_remote":
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&schedule=remote&search_period={days}&order_by=publication_time",
            "Удаленно (Казахстан)"
        ))
    elif location_mode == "astana":
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&area={ASTANA_AREA_ID}&search_period={days}&order_by=publication_time",
            "Офис / Гибрид (Астана)"
        ))
    elif location_mode == "almaty":
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&area={ALMATY_AREA_ID}&search_period={days}&order_by=publication_time",
            "Офис / Гибрид (Алматы)"
        ))
    else:  # kz_all: remote + Astana + Almaty
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&schedule=remote&search_period={days}&order_by=publication_time",
            "Удаленно (Казахстан)"
        ))
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&area={ASTANA_AREA_ID}&search_period={days}&order_by=publication_time",
            "Офис / Гибрид (Астана)"
        ))
        urls_to_fetch.append((
            f"https://hh.kz/search/vacancy?text={query}&area={ALMATY_AREA_ID}&search_period={days}&order_by=publication_time",
            "Офис / Гибрид (Алматы)"
        ))

    seen_vids = set()
    # For kz_all, apply limit per URL so each city gets representation
    per_url_limit = limit if len(urls_to_fetch) == 1 else max(2, limit // len(urls_to_fetch))

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            for url, loc_label in urls_to_fetch:
                resp = await client.get(url, headers=HEADERS, follow_redirects=True)
                if resp.status_code == 200:
                    vids = list(set(re.findall(r'/vacancy/(\d+)', resp.text)))
                    added = 0
                    for vid in vids:
                        if vid not in seen_vids:
                            seen_vids.add(vid)
                            jobs.append({
                                "title": f"Vacancy #{vid} (HH.kz)",
                                "company": "HeadHunter Казахстан (hh.kz)",
                                "location": loc_label,
                                "url": f"https://hh.kz/vacancy/{vid}",
                                "description": (
                                    f"Вакансия с HeadHunter Казахстан (hh.kz) ID: {vid}. "
                                    f"Позиция: {query}. Локация: {loc_label}. "
                                    f"Опубликована за последние {days} дн."
                                ),
                                "source": "HH.kz"
                            })
                            added += 1
                            if added >= per_url_limit:
                                break
                else:
                    logger.warning(f"HH.kz returned status {resp.status_code} for {url}")
    except Exception as e:
        logger.error(f"Error scraping HH.kz: {e}")

    return jobs


async def scrape_habr_jobs(query: str = "Python AI", limit: int = 5) -> list:
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
                        "company": "Хабр Карьера",
                        "location": "Удаленно / Доступно из Казахстана",
                        "url": full_url,
                        "description": f"Удаленная вакансия с Хабр Карьера: {title.strip()}. Доступна для специалистов из СНГ/Казахстана.",
                        "source": "Habr Career"
                    })
    except Exception as e:
        logger.error(f"Error scraping Habr Career: {e}")
    return jobs


async def scrape_hh_jobs(query: str = "Python AI", days: int = 7, limit: int = 5) -> list:
    url = f"https://hh.ru/search/vacancy?text={query}&schedule=remote&search_period={days}&order_by=publication_time"
    jobs = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=HEADERS, follow_redirects=True)
            if resp.status_code == 200:
                vids = list(set(re.findall(r'/vacancy/(\d+)', resp.text)))[:limit]
                for vid in vids:
                    jobs.append({
                        "title": f"Vacancy #{vid} (HH.ru Remote)",
                        "company": "HeadHunter (Remote)",
                        "location": "Полная Удаленка",
                        "url": f"https://hh.ru/vacancy/{vid}",
                        "description": f"Удаленная вакансия с HeadHunter ID: {vid}. Позиция {query}. За последние {days} дн.",
                        "source": "HH.ru Remote"
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
                        "location": "Worldwide Full Remote",
                        "url": item.get("url"),
                        "description": item.get("description", "")[:2000],
                        "source": "Remotive"
                    })
    except Exception as e:
        logger.error(f"Error fetching Remotive: {e}")
    return jobs
