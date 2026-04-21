"""Adzuna job scraper — free API (register at developer.adzuna.com).

Registration takes 2 minutes and gives 250 free requests/day.
Set env vars on Azure:  ADZUNA_APP_ID  and  ADZUNA_APP_KEY
"""

import os
from datetime import datetime, timezone

import httpx

from scrapers.base_scraper import BaseScraper

ADZUNA_APP_ID  = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# Adzuna country codes (each is a separate endpoint)
COUNTRIES = ["us", "gb", "ca", "au", "de", "in", "sg"]

SEARCH_TERMS = [
    "AI engineer", "machine learning engineer", "LLM engineer",
    "AI agent developer", "data scientist", "MLOps engineer",
    "AI product manager", "AI researcher", "deep learning engineer",
    "full stack developer", "backend engineer", "devops engineer",
]


class AdzunaScraper(BaseScraper):
    """
    Scrapes from Adzuna — aggregates millions of jobs across US, UK, EU, APAC.
    Free API: https://developer.adzuna.com/
    """

    def __init__(self):
        super().__init__(scraper_name="adzuna_scraper", request_delay=1.0)

    async def scrape(self, **kwargs):
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            self.log.warning(
                "adzuna_no_credentials",
                hint="Register free at https://developer.adzuna.com/ then set "
                     "ADZUNA_APP_ID and ADZUNA_APP_KEY in Azure App Service settings.",
            )
            return

        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for country in COUNTRIES:
                for term in SEARCH_TERMS:
                    await self.rate_limit()
                    url = (
                        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
                        f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
                        f"&results_per_page=50"
                        f"&what={term.replace(' ', '+')}"
                        f"&sort_by=date&max_days_old=14"
                        f"&content-type=application/json"
                    )
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as e:
                        self.log.warning(
                            "adzuna_fetch_failed",
                            country=country, term=term, error=str(e),
                        )
                        continue

                    for job in data.get("results", []):
                        job_id = str(job.get("id") or "")
                        if not job_id or job_id in seen_ids:
                            continue
                        seen_ids.add(job_id)
                        await self._store_job(job, country, term)

    async def _store_job(self, job: dict, country: str, search_term: str):
        title   = job.get("title") or ""
        company = (job.get("company") or {}).get("display_name") or "Unknown"
        if not title:
            return

        location     = (job.get("location") or {}).get("display_name") or country.upper()
        description  = job.get("description") or ""
        redirect_url = job.get("redirect_url") or ""
        salary_min   = job.get("salary_min")
        salary_max   = job.get("salary_max")
        salary = ""
        if salary_min and salary_max:
            salary = f"${int(salary_min):,} – ${int(salary_max):,}"
        elif salary_min:
            salary = f"${int(salary_min):,}+"

        created_raw = job.get("created") or ""
        try:
            created_at = datetime.fromisoformat(str(created_raw).replace("Z", "+00:00"))
        except Exception:
            created_at = datetime.now(timezone.utc)

        content = (
            f"{title} at {company}\n\n"
            f"Location: {location}\n"
            f"Salary: {salary}\n\n"
            f"{description}"
        )

        author = await self.upsert_user(
            platform_name="adzuna",
            platform_user_id=f"co_{company.lower().replace(' ', '_')[:40]}",
            username=company,
        )

        await self.upsert_post(
            user_id=author,
            platform_name="adzuna",
            post_type="post",
            platform_post_id=f"adzuna_{job.get('id')}",
            body=content[:4000],
            title=title,
            url=redirect_url,
            posted_at=created_at,
            raw_metadata={
                "source": "adzuna",
                "company": company,
                "location": location,
                "country": country,
                "salary_min": salary_min,
                "salary_max": salary_max,
                "salary_display": salary,
                "search_term": search_term,
                "category": (job.get("category") or {}).get("label"),
                "contract_type": job.get("contract_type"),
                "contract_time": job.get("contract_time"),
            },
        )
