"""ATS job scrapers — Greenhouse, Lever, Ashby. Free APIs, no auth."""

import re
from datetime import datetime, timezone

import httpx
import structlog

from config.sources import ATS_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slugify_company(slug: str) -> str:
    """Convert board slug to a readable company name."""
    return slug.replace("-", " ").title()


# ============================================
# Greenhouse
# ============================================
class GreenhouseJobScraper(BaseScraper):
    """Scrapes job listings from Greenhouse board API."""

    def __init__(self):
        super().__init__(
            scraper_name="greenhouse_job_scraper",
            request_delay=ATS_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        slugs = ATS_SCRAPE_CONFIG.get("greenhouse_slugs", [])
        self.log.info("greenhouse_scrape_start", companies=len(slugs))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for slug in slugs:
                await self._scrape_board(client, slug)
                await self.rate_limit()

        self.log.info(
            "greenhouse_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_board(self, client: httpx.AsyncClient, slug: str):
        url = f"https://api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        try:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            if response.status_code == 404:
                self.log.debug("greenhouse_board_not_found", slug=slug)
                return
            response.raise_for_status()
        except httpx.HTTPStatusError:
            self.log.debug("greenhouse_board_error", slug=slug)
            return
        except Exception as e:
            self.log.warning("greenhouse_fetch_failed", slug=slug, error=str(e))
            return

        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return

        company = _slugify_company(slug)
        self.log.info("greenhouse_jobs", slug=slug, count=len(jobs))

        for job in jobs:
            title_raw = job.get("title", "")
            if not title_raw:
                continue

            job_url = job.get("absolute_url", "")
            if not job_url:
                continue

            published_at = None
            updated = job.get("updated_at", "")
            if updated:
                try:
                    published_at = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            location_obj = job.get("location", {}) or {}
            location = location_obj.get("name", "") if isinstance(location_obj, dict) else str(location_obj)

            departments = job.get("departments", []) or []
            department = departments[0].get("name", "") if departments else ""

            description = _strip_html(job.get("content", ""))

            title = f"{title_raw} at {company}"

            await self.upsert_job_listing(
                source="greenhouse",
                title=title,
                url=job_url,
                company=company,
                location=location,
                department=department,
                description=description,
                apply_url=job_url,
                published_at=published_at,
                raw_metadata={"board_slug": slug, "gh_id": job.get("id")},
            )
            self.records_fetched += 1


# ============================================
# Lever
# ============================================
class LeverJobScraper(BaseScraper):
    """Scrapes job listings from Lever postings API."""

    def __init__(self):
        super().__init__(
            scraper_name="lever_job_scraper",
            request_delay=ATS_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        slugs = ATS_SCRAPE_CONFIG.get("lever_slugs", [])
        self.log.info("lever_scrape_start", companies=len(slugs))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for slug in slugs:
                await self._scrape_board(client, slug)
                await self.rate_limit()

        self.log.info(
            "lever_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_board(self, client: httpx.AsyncClient, slug: str):
        url = f"https://api.lever.co/v0/postings/{slug}"
        try:
            response = await client.get(url, headers={"User-Agent": USER_AGENT})
            if response.status_code == 404:
                self.log.debug("lever_board_not_found", slug=slug)
                return
            response.raise_for_status()
        except httpx.HTTPStatusError:
            self.log.debug("lever_board_error", slug=slug)
            return
        except Exception as e:
            self.log.warning("lever_fetch_failed", slug=slug, error=str(e))
            return

        jobs = response.json()
        if not isinstance(jobs, list) or not jobs:
            return

        company = _slugify_company(slug)
        self.log.info("lever_jobs", slug=slug, count=len(jobs))

        for job in jobs:
            title_raw = job.get("text", "")
            if not title_raw:
                continue

            job_url = job.get("hostedUrl", "")
            if not job_url:
                continue

            published_at = None
            created_ms = job.get("createdAt")
            if created_ms:
                try:
                    published_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
                except (ValueError, TypeError, OSError):
                    pass

            cats = job.get("categories", {}) or {}
            location = cats.get("location", "")
            department = cats.get("team", "")
            commitment = cats.get("commitment", "")

            job_type = ""
            if commitment:
                ct = commitment.lower()
                if "full" in ct:
                    job_type = "full_time"
                elif "part" in ct:
                    job_type = "part_time"
                elif "contract" in ct or "freelance" in ct:
                    job_type = "contract"
                elif "intern" in ct:
                    job_type = "internship"

            description = _strip_html(job.get("descriptionPlain", "") or job.get("description", ""))

            title = f"{title_raw} at {company}"

            await self.upsert_job_listing(
                source="lever",
                title=title,
                url=job_url,
                company=company,
                location=location,
                department=department,
                job_type=job_type,
                description=description,
                apply_url=job.get("applyUrl", job_url),
                published_at=published_at,
                raw_metadata={"board_slug": slug, "lever_id": job.get("id")},
            )
            self.records_fetched += 1


# ============================================
# Ashby
# ============================================
class AshbyJobScraper(BaseScraper):
    """Scrapes job listings from Ashby job board API."""

    def __init__(self):
        super().__init__(
            scraper_name="ashby_job_scraper",
            request_delay=ATS_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        slugs = ATS_SCRAPE_CONFIG.get("ashby_slugs", [])
        self.log.info("ashby_scrape_start", companies=len(slugs))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for slug in slugs:
                await self._scrape_board(client, slug)
                await self.rate_limit()

        self.log.info(
            "ashby_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_board(self, client: httpx.AsyncClient, slug: str):
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        try:
            response = await client.get(
                url,
                params={"includeCompensation": "true"},
                headers={"User-Agent": USER_AGENT},
            )
            if response.status_code == 404:
                self.log.debug("ashby_board_not_found", slug=slug)
                return
            response.raise_for_status()
        except httpx.HTTPStatusError:
            self.log.debug("ashby_board_error", slug=slug)
            return
        except Exception as e:
            self.log.warning("ashby_fetch_failed", slug=slug, error=str(e))
            return

        data = response.json()
        jobs = data.get("jobs", [])
        if not jobs:
            return

        company = _slugify_company(slug)
        self.log.info("ashby_jobs", slug=slug, count=len(jobs))

        for job in jobs:
            title_raw = job.get("title", "")
            if not title_raw:
                continue

            job_url = job.get("jobUrl", "") or job.get("hostedUrl", "")
            if not job_url:
                continue

            published_at = None
            pub_date = job.get("publishedDate", "") or job.get("publishedAt", "")
            if pub_date:
                try:
                    published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            location = job.get("location", "")
            if isinstance(location, dict):
                location = location.get("name", "")
            department = job.get("department", "")
            if isinstance(department, dict):
                department = department.get("name", "")

            # Compensation
            salary_min = None
            salary_max = None
            salary_currency = ""
            comp = job.get("compensation")
            if comp and isinstance(comp, dict):
                salary_currency = comp.get("currency", "")
                ranges = comp.get("ranges", [])
                if ranges and isinstance(ranges, list):
                    r = ranges[0]
                    salary_min = r.get("min")
                    salary_max = r.get("max")

            description = _strip_html(job.get("descriptionHtml", "") or job.get("description", ""))

            title = f"{title_raw} at {company}"

            await self.upsert_job_listing(
                source="ashby",
                title=title,
                url=job_url,
                company=company,
                location=location,
                department=department,
                salary_min=float(salary_min) if salary_min else None,
                salary_max=float(salary_max) if salary_max else None,
                salary_currency=salary_currency,
                description=description,
                apply_url=job_url,
                published_at=published_at,
                raw_metadata={"board_slug": slug, "ashby_id": job.get("id")},
            )
            self.records_fetched += 1
