"""RemoteOK job scraper — free JSON API, no auth required."""

from datetime import datetime, timezone

import httpx
import structlog

from config.sources import REMOTEOK_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()


class RemoteOKScraper(BaseScraper):
    """Scrapes remote job listings from RemoteOK's public API."""

    def __init__(self):
        super().__init__(
            scraper_name="remoteok_scraper",
            request_delay=REMOTEOK_SCRAPE_CONFIG.get("request_delay", 2.0),
        )

    async def scrape(self, **kwargs):
        api_url = REMOTEOK_SCRAPE_CONFIG["api_url"]
        self.log.info("remoteok_scrape_start", url=api_url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(
                    api_url,
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
            except Exception as e:
                self.log.error("remoteok_fetch_failed", error=str(e))
                return

            data = response.json()

        if not isinstance(data, list) or len(data) < 2:
            self.log.warning("remoteok_empty_response")
            return

        # First element is metadata/legal notice, skip it
        jobs = data[1:]
        self.log.info("remoteok_jobs_received", count=len(jobs))

        for job in jobs:
            if not isinstance(job, dict):
                continue

            position = job.get("position", "")
            company = job.get("company", "")
            if not position:
                continue

            slug = job.get("slug", "")
            job_url = job.get("url", "") or (f"https://remoteok.com/remote-jobs/{slug}" if slug else "")
            if not job_url:
                continue

            # Parse date
            published_at = None
            date_str = job.get("date", "")
            if date_str:
                try:
                    published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            # Salary
            salary_min = None
            salary_max = None
            try:
                sal_min = job.get("salary_min")
                if sal_min and str(sal_min).isdigit():
                    salary_min = float(sal_min)
                sal_max = job.get("salary_max")
                if sal_max and str(sal_max).isdigit():
                    salary_max = float(sal_max)
            except (ValueError, TypeError):
                pass

            tags = job.get("tags", []) or []
            description = job.get("description", "")

            # Strip simple HTML tags from description
            if description:
                import re
                description = re.sub(r"<[^>]+>", " ", description)
                description = re.sub(r"\s+", " ", description).strip()

            title = f"{position} at {company}" if company else position

            await self.upsert_job_listing(
                source="remoteok",
                title=title,
                url=job_url,
                company=company,
                location=job.get("location", "") or "Remote",
                job_type="full_time",
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency="USD",
                remote=True,
                tags=tags if tags else None,
                description=description,
                apply_url=job_url,
                published_at=published_at,
                raw_metadata={"original_id": job.get("id"), "slug": slug},
            )
            self.records_fetched += 1

        self.log.info(
            "remoteok_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )
