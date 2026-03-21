"""Job market scraper — uses python-jobspy library. No API key needed."""

import asyncio
import math
from datetime import datetime, timezone

import structlog

from config.sources import JOB_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()


class JobScraper(BaseScraper):
    """Scrapes job listings using python-jobspy (Indeed + Google)."""

    def __init__(self):
        super().__init__(scraper_name="job_scraper", request_delay=2.0)

    async def scrape(
        self,
        search_terms: list[str] | None = None,
        locations: list[str] | None = None,
        max_per_search: int | None = None,
        **kwargs,
    ):
        """Scrape job listings for configured search terms and locations."""
        terms = search_terms or JOB_SCRAPE_CONFIG["search_terms"]
        locs = locations or JOB_SCRAPE_CONFIG["locations"]
        limit = max_per_search or JOB_SCRAPE_CONFIG["results_per_search"]
        hours_old = JOB_SCRAPE_CONFIG["hours_old"]

        self.log.info(
            "job_scrape_start",
            search_terms=len(terms),
            locations=len(locs),
        )

        for term in terms:
            for location in locs:
                await self._scrape_jobs(term, location, limit, hours_old)

        self.log.info(
            "job_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_jobs(
        self, search_term: str, location: str, results_wanted: int, hours_old: int
    ):
        """Run a single job search query via jobspy."""
        self.log.info(
            "searching_jobs", term=search_term, location=location
        )

        try:
            # jobspy is synchronous, so run in executor
            jobs_df = await asyncio.to_thread(
                self._run_jobspy, search_term, location, results_wanted, hours_old
            )
        except Exception as e:
            self.log.warning(
                "jobspy_search_failed",
                term=search_term,
                location=location,
                error=str(e),
            )
            return

        if jobs_df is None or jobs_df.empty:
            self.log.debug("no_jobs_found", term=search_term, location=location)
            return

        for _, row in jobs_df.iterrows():
            title = str(row.get("title", "")) or ""
            if not title:
                continue

            company = self._clean_str(row.get("company_name", ""))
            job_url = self._clean_str(row.get("job_url", ""))
            description = self._clean_str(row.get("description", ""))
            job_location = self._clean_str(row.get("location", "")) or location
            job_type = self._clean_str(row.get("job_type", ""))

            # Salary (pandas can return NaN for missing numeric fields)
            salary_min = self._clean_number(row.get("min_amount"))
            salary_max = self._clean_number(row.get("max_amount"))
            salary_currency = self._clean_str(row.get("currency", ""))

            # Date posted
            date_posted = row.get("date_posted")
            published_at = None
            if date_posted is not None:
                try:
                    if hasattr(date_posted, "to_pydatetime"):
                        published_at = date_posted.to_pydatetime()
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=timezone.utc)
                    elif isinstance(date_posted, str) and date_posted:
                        published_at = datetime.fromisoformat(date_posted)
                        if published_at.tzinfo is None:
                            published_at = published_at.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            site = str(row.get("site", "")) or ""

            await self.upsert_job_listing(
                source=site or "jobspy",
                title=f"{title} at {company}" if company else title,
                url=job_url,
                company=company,
                location=job_location,
                job_type=job_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                remote="remote" in job_location.lower() if job_location else False,
                tags=[search_term],
                description=description[:5000] if description else None,
                apply_url=job_url,
                published_at=published_at,
                raw_metadata={
                    "site": site,
                    "search_term": search_term,
                    "search_location": location,
                },
            )
            self.records_fetched += 1

        self.log.info(
            "jobs_found",
            term=search_term,
            location=location,
            count=len(jobs_df),
        )

    @staticmethod
    def _clean_str(value) -> str:
        """Convert a value to string, treating pandas NaN/None as empty string."""
        if value is None:
            return ""
        s = str(value)
        if s.lower() == "nan" or s.lower() == "none":
            return ""
        return s

    @staticmethod
    def _clean_number(value) -> float | None:
        """Convert a value to float, treating pandas NaN/None as None."""
        if value is None:
            return None
        try:
            f = float(value)
            if math.isnan(f):
                return None
            return f
        except (ValueError, TypeError):
            return None

    def _run_jobspy(
        self, search_term: str, location: str, results_wanted: int, hours_old: int
    ):
        """Synchronous jobspy call (runs in thread via asyncio.to_thread)."""
        from jobspy import scrape_jobs

        return scrape_jobs(
            site_name=["indeed", "google"],
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed="USA",
        )
