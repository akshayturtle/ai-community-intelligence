"""Remotive job scraper — free JSON API, no auth required."""

import re
from datetime import datetime, timezone

import httpx
import structlog

from config.sources import REMOTIVE_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

SALARY_PATTERN = re.compile(r"\$?([\d,]+)[kK]?\s*[-–]\s*\$?([\d,]+)[kK]?")


def _parse_salary(salary_text: str) -> tuple[float | None, float | None]:
    """Extract min/max salary from free-text salary string."""
    if not salary_text:
        return None, None
    m = SALARY_PATTERN.search(salary_text)
    if not m:
        return None, None
    try:
        lo = float(m.group(1).replace(",", ""))
        hi = float(m.group(2).replace(",", ""))
        # If values look like thousands (e.g. 120-180), multiply by 1000
        if lo < 1000:
            lo *= 1000
        if hi < 1000:
            hi *= 1000
        return lo, hi
    except (ValueError, TypeError):
        return None, None


class RemotiveScraper(BaseScraper):
    """Scrapes remote job listings from Remotive's public API."""

    def __init__(self):
        super().__init__(
            scraper_name="remotive_scraper",
            request_delay=REMOTIVE_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        api_url = REMOTIVE_SCRAPE_CONFIG["api_url"]
        categories = REMOTIVE_SCRAPE_CONFIG.get("categories", [])
        self.log.info("remotive_scrape_start", categories=len(categories))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for category in categories:
                await self._scrape_category(client, api_url, category)
                await self.rate_limit()

        self.log.info(
            "remotive_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_category(
        self, client: httpx.AsyncClient, api_url: str, category: str
    ):
        self.log.info("remotive_category", category=category)
        try:
            response = await client.get(
                api_url,
                params={"category": category},
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except Exception as e:
            self.log.warning("remotive_fetch_failed", category=category, error=str(e))
            return

        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return

        self.log.info("remotive_jobs_received", category=category, count=len(jobs))

        for job in jobs:
            title_raw = job.get("title", "")
            company = job.get("company_name", "")
            if not title_raw:
                continue

            job_url = job.get("url", "")
            if not job_url:
                continue

            published_at = None
            pub_date = job.get("publication_date", "")
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            salary_min, salary_max = _parse_salary(job.get("salary", ""))

            description = job.get("description", "")
            if description:
                description = re.sub(r"<[^>]+>", " ", description)
                description = re.sub(r"\s+", " ", description).strip()

            tags = job.get("tags", []) or []
            job_type = job.get("job_type", "")

            title = f"{title_raw} at {company}" if company else title_raw

            await self.upsert_job_listing(
                source="remotive",
                title=title,
                url=job_url,
                company=company,
                location=job.get("candidate_required_location", "") or "Remote",
                job_type=job_type.replace(" ", "_").lower() if job_type else "full_time",
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="USD",
                remote=True,
                tags=tags if tags else [category],
                description=description,
                apply_url=job_url,
                published_at=published_at,
                raw_metadata={"category": category, "remotive_id": job.get("id")},
            )
            self.records_fetched += 1
