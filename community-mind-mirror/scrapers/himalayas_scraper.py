"""Himalayas job scraper — free JSON API, no auth, paginated."""

import re
from datetime import datetime

import httpx
import structlog

from config.sources import HIMALAYAS_SCRAPE_CONFIG
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


def _is_tech(title: str, categories: list) -> bool:
    text = title.lower() + " " + " ".join(str(c).lower() for c in (categories or []))
    return any(kw in text for kw in TECH_KEYWORDS)


class HimalayasScraper(BaseScraper):
    """Scrapes remote job listings from Himalayas' public API."""

    def __init__(self):
        super().__init__(
            scraper_name="himalayas_scraper",
            request_delay=HIMALAYAS_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        api_url = HIMALAYAS_SCRAPE_CONFIG["api_url"]
        max_pages = HIMALAYAS_SCRAPE_CONFIG.get("max_pages", 50)
        self.log.info("himalayas_scrape_start", max_pages=max_pages)

        async with httpx.AsyncClient(timeout=30.0) as client:
            offset = 0
            page = 0
            while page < max_pages:
                page += 1
                self.log.debug("himalayas_page", page=page, offset=offset)

                try:
                    response = await client.get(
                        api_url,
                        params={"limit": 20, "offset": offset},
                        headers={"User-Agent": USER_AGENT},
                    )
                    response.raise_for_status()
                except Exception as e:
                    self.log.warning("himalayas_fetch_failed", page=page, error=str(e))
                    break

                data = response.json()
                jobs = data if isinstance(data, list) else data.get("jobs", data.get("data", []))
                if not jobs:
                    break

                for job in jobs:
                    if not isinstance(job, dict):
                        continue

                    title_raw = job.get("title", "")
                    company = job.get("companyName", "") or job.get("company_name", "")
                    if not title_raw:
                        continue

                    job_url = job.get("applicationLink", "") or job.get("url", "")
                    if not job_url:
                        continue

                    published_at = None
                    pub_date = job.get("publishedDate") or job.get("pubDate")
                    if pub_date:
                        try:
                            if isinstance(pub_date, (int, float)):
                                published_at = datetime.utcfromtimestamp(pub_date)
                            else:
                                published_at = datetime.fromisoformat(
                                    str(pub_date).replace("Z", "+00:00")
                                )
                        except (ValueError, TypeError, OSError):
                            pass

                    salary_min = None
                    salary_max = None
                    try:
                        sal_min = job.get("salaryCurrencyMin") or job.get("salaryMin")
                        if sal_min is not None:
                            salary_min = float(sal_min)
                        sal_max = job.get("salaryCurrencyMax") or job.get("salaryMax")
                        if sal_max is not None:
                            salary_max = float(sal_max)
                    except (ValueError, TypeError):
                        pass

                    categories = job.get("categories", []) or []
                    tags = categories if isinstance(categories, list) else []

                    # Skip non-tech jobs
                    if not _is_tech(title_raw, tags):
                        continue

                    description = job.get("description", "")
                    if description:
                        description = re.sub(r"<[^>]+>", " ", description)
                        description = re.sub(r"\s+", " ", description).strip()

                    location = job.get("location", "") or "Remote"
                    title = f"{title_raw} at {company}" if company else title_raw

                    await self.upsert_job_listing(
                        source="himalayas",
                        title=title,
                        url=job_url,
                        company=company,
                        location=location,
                        salary_min=salary_min,
                        salary_max=salary_max,
                        salary_currency=job.get("salaryCurrency", "USD"),
                        remote=True,
                        tags=tags if tags else None,
                        description=description,
                        apply_url=job_url,
                        published_at=published_at,
                    )
                    self.records_fetched += 1

                if len(jobs) < 20:
                    break
                offset += 20
                await self.rate_limit()

        self.log.info(
            "himalayas_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )
