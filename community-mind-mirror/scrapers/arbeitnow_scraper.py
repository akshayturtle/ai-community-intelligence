"""Arbeitnow job scraper — free JSON API, no auth, paginated."""

import re
from datetime import datetime

import httpx
import structlog

from config.sources import ARBEITNOW_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

TECH_KEYWORDS = {
    "engineer", "developer", "software", "data", "machine learning", "ml", "ai",
    "backend", "frontend", "fullstack", "full-stack", "devops", "cloud", "platform",
    "infrastructure", "sre", "python", "javascript", "typescript", "rust", "golang",
    "java", "scala", "react", "node", "api", "database", "analytics", "scientist",
    "architect", "security", "blockchain", "web3", "crypto", "solidity",
    "product manager", "ux", "ui", "design", "research", "nlp", "llm", "gpu",
    "kubernetes", "docker", "aws", "gcp", "azure", "mobile", "ios", "android",
}


def _is_tech(title: str, tags: list) -> bool:
    text = title.lower() + " " + " ".join(str(t).lower() for t in (tags or []))
    return any(kw in text for kw in TECH_KEYWORDS)


class ArbeitnowScraper(BaseScraper):
    """Scrapes job listings from Arbeitnow's public API."""

    def __init__(self):
        super().__init__(
            scraper_name="arbeitnow_scraper",
            request_delay=ARBEITNOW_SCRAPE_CONFIG.get("request_delay", 1.5),
        )

    async def scrape(self, **kwargs):
        api_url = ARBEITNOW_SCRAPE_CONFIG["api_url"]
        max_pages = ARBEITNOW_SCRAPE_CONFIG.get("max_pages", 10)
        self.log.info("arbeitnow_scrape_start", max_pages=max_pages)

        async with httpx.AsyncClient(timeout=30.0) as client:
            for page in range(1, max_pages + 1):
                self.log.debug("arbeitnow_page", page=page)

                try:
                    response = await client.get(
                        api_url,
                        params={"page": page},
                        headers={"User-Agent": USER_AGENT},
                    )
                    response.raise_for_status()
                except Exception as e:
                    self.log.warning("arbeitnow_fetch_failed", page=page, error=str(e))
                    break

                data = response.json()
                jobs = data.get("data", [])
                if not jobs:
                    break

                for job in jobs:
                    title_raw = job.get("title", "")
                    company = job.get("company_name", "")
                    if not title_raw:
                        continue

                    job_url = job.get("url", "")
                    if not job_url:
                        slug = job.get("slug", "")
                        if slug:
                            job_url = f"https://www.arbeitnow.com/view/{slug}"
                        else:
                            continue

                    published_at = None
                    created_at = job.get("created_at")
                    if created_at:
                        try:
                            if isinstance(created_at, (int, float)):
                                published_at = datetime.utcfromtimestamp(created_at)
                            else:
                                published_at = datetime.fromisoformat(
                                    str(created_at).replace("Z", "+00:00")
                                )
                        except (ValueError, TypeError):
                            pass

                    is_remote = bool(job.get("remote", False))
                    tags = job.get("tags", []) or []

                    # Skip non-tech jobs
                    if not _is_tech(title_raw, tags):
                        continue

                    job_types = job.get("job_types", []) or []
                    job_type = job_types[0].replace(" ", "_").lower() if job_types else ""
                    location = job.get("location", "")

                    description = job.get("description", "")
                    if description:
                        description = re.sub(r"<[^>]+>", " ", description)
                        description = re.sub(r"\s+", " ", description).strip()

                    title = f"{title_raw} at {company}" if company else title_raw

                    await self.upsert_job_listing(
                        source="arbeitnow",
                        title=title,
                        url=job_url,
                        company=company,
                        location=location if location else ("Remote" if is_remote else ""),
                        job_type=job_type,
                        remote=is_remote,
                        tags=tags if tags else None,
                        description=description,
                        apply_url=job_url,
                        published_at=published_at,
                    )
                    self.records_fetched += 1

                # Check if there's a next page
                links = data.get("links", {})
                if not links.get("next"):
                    break
                await self.rate_limit()

        self.log.info(
            "arbeitnow_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )
