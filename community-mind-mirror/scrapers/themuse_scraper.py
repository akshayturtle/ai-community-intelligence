"""The Muse job scraper — free public API v2, no auth required."""

import re
from datetime import datetime

import httpx
import structlog

from config.sources import THEMUSE_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

LEVEL_TO_SENIORITY = {
    "Internship": "intern",
    "Entry Level": "junior",
    "Mid Level": "mid",
    "Senior Level": "senior",
    "Management": "lead",
}


class TheMuseScraper(BaseScraper):
    """Scrapes job listings from The Muse's public API."""

    def __init__(self):
        super().__init__(
            scraper_name="themuse_scraper",
            request_delay=THEMUSE_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        api_url = THEMUSE_SCRAPE_CONFIG["api_url"]
        categories = THEMUSE_SCRAPE_CONFIG.get("categories", ["Engineering"])
        levels = THEMUSE_SCRAPE_CONFIG.get("levels", ["Mid Level", "Senior Level"])
        max_pages = THEMUSE_SCRAPE_CONFIG.get("max_pages", 20)

        self.log.info(
            "themuse_scrape_start",
            categories=len(categories),
            levels=len(levels),
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            for category in categories:
                for level in levels:
                    await self._scrape_combo(client, api_url, category, level, max_pages)
                    await self.rate_limit()

        self.log.info(
            "themuse_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_combo(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        category: str,
        level: str,
        max_pages: int,
    ):
        for page in range(max_pages):
            self.log.debug("themuse_page", category=category, level=level, page=page)

            try:
                response = await client.get(
                    api_url,
                    params={
                        "category": category,
                        "level": level,
                        "page": page,
                        "api_key": "",  # No key needed for public API
                    },
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
            except Exception as e:
                self.log.warning(
                    "themuse_fetch_failed",
                    category=category,
                    level=level,
                    page=page,
                    error=str(e),
                )
                break

            data = response.json()
            results = data.get("results", [])
            if not results:
                break

            page_count = data.get("page_count", 0)

            for job in results:
                name = job.get("name", "")
                company_obj = job.get("company", {}) or {}
                company = company_obj.get("name", "")
                if not name:
                    continue

                refs = job.get("refs", {}) or {}
                job_url = refs.get("landing_page", "")
                if not job_url:
                    continue

                published_at = None
                pub_date = job.get("publication_date", "")
                if pub_date:
                    try:
                        published_at = datetime.fromisoformat(
                            pub_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                locations = job.get("locations", []) or []
                location_str = ", ".join(loc.get("name", "") for loc in locations if loc.get("name"))

                levels_list = job.get("levels", []) or []
                seniority = ""
                for lvl in levels_list:
                    lvl_name = lvl.get("name", "")
                    if lvl_name in LEVEL_TO_SENIORITY:
                        seniority = LEVEL_TO_SENIORITY[lvl_name]
                        break

                cats = job.get("categories", []) or []
                tags = [c.get("name", "") for c in cats if c.get("name")]

                description = job.get("contents", "")
                if description:
                    description = re.sub(r"<[^>]+>", " ", description)
                    description = re.sub(r"\s+", " ", description).strip()

                title = f"{name} at {company}" if company else name

                await self.upsert_job_listing(
                    source="themuse",
                    title=title,
                    url=job_url,
                    company=company,
                    location=location_str,
                    seniority=seniority,
                    tags=tags if tags else [category],
                    description=description,
                    apply_url=job_url,
                    published_at=published_at,
                    raw_metadata={"muse_id": job.get("id"), "category": category, "level": level},
                )
                self.records_fetched += 1

            if page >= page_count - 1:
                break
            await self.rate_limit()
