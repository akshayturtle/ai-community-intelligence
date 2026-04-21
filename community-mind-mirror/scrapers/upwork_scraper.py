"""Contract/freelance job scraper — uses python-jobspy (Indeed + LinkedIn).

Since Upwork's public RSS feed was shut down (410 Gone) and their search page
requires authentication, we use python-jobspy to scrape equivalent contract/
freelance job demand from Indeed and LinkedIn. This captures the same market
signal: what skills clients are paying for, budget ranges, remote work trends.

No credentials required for Indeed. LinkedIn may require cookies for high volume.

Stored under platform="upwork" for continuity; raw_metadata.source="indeed"
or "linkedin" indicates the actual source.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from functools import partial

import structlog

from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

# Search terms focused on AI/tech freelance/contract demand
SEARCH_QUERIES = [
    "AI agent developer",
    "LLM fine tuning",
    "machine learning engineer",
    "Python automation",
    "web scraping developer",
    "React developer contract",
    "FastAPI backend",
    "data pipeline engineer",
    "chatbot developer",
    "computer vision engineer",
    "RAG system developer",
    "blockchain developer",
    "Flutter mobile developer",
    "DevOps AWS contract",
    "data analyst contract",
    "n8n automation",
    "AI integration developer",
    "prompt engineer",
    "vector database developer",
    "MLOps engineer",
]

SITES = ["indeed", "linkedin"]


def _sync_scrape(search_term: str, sites: list[str]) -> list[dict]:
    """Run jobspy synchronously (called from executor)."""
    try:
        from jobspy import scrape_jobs
        df = scrape_jobs(
            site_name=sites,
            search_term=search_term,
            location="remote",
            results_wanted=30,
            hours_old=72,                 # Last 3 days only
            job_type="contract",          # Contract/freelance only
            is_remote=True,
            description_format="markdown",
        )
        if df is None or df.empty:
            return []
        return df.to_dict("records")
    except Exception as e:
        logger.warning("jobspy_scrape_failed", query=search_term, error=str(e))
        return []


class UpworkScraper(BaseScraper):
    """
    Scrapes contract/freelance job demand from Indeed and LinkedIn via python-jobspy.
    Captures: title, description, budget/salary, skills, company, remote status.

    Note: stored under platform="upwork" for historical continuity but sources
    from Indeed/LinkedIn since Upwork's public RSS endpoint was shut down.
    """

    def __init__(self):
        super().__init__(scraper_name="upwork_scraper", request_delay=2.0)

    async def scrape(self, **kwargs):
        seen_ids: set[str] = set()
        loop = asyncio.get_event_loop()

        for query in SEARCH_QUERIES:
            await self.rate_limit()
            try:
                jobs = await loop.run_in_executor(
                    None, partial(_sync_scrape, query, SITES)
                )
                for job in jobs:
                    jid = self._job_id(job)
                    if not jid or jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    await self._store_job(job, query)
            except Exception as e:
                self.log.warning("upwork_scraper_error", query=query, error=str(e))

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _job_id(self, job: dict) -> str:
        """Stable unique ID: prefer job URL hash, fallback to title+company."""
        url = str(job.get("job_url") or job.get("job_url_direct") or "")
        if url:
            return hashlib.md5(url.encode()).hexdigest()[:16]
        key = f"{job.get('title','')}_{job.get('company','')}_{job.get('location','')}"
        return hashlib.md5(key.encode()).hexdigest()[:16]

    async def _store_job(self, job: dict, query: str):
        title = str(job.get("title") or "").strip()
        if not title:
            return

        site       = str(job.get("site") or "indeed")
        company    = str(job.get("company") or "")
        location   = str(job.get("location") or "remote")
        job_url    = str(job.get("job_url") or job.get("job_url_direct") or "")
        description = str(job.get("description") or "")[:3000]
        is_remote  = job.get("is_remote") or True
        job_type   = str(job.get("job_type") or "contract")
        job_level  = str(job.get("job_level") or "")

        # Salary/budget
        min_amt  = job.get("min_amount")
        max_amt  = job.get("max_amount")
        currency = str(job.get("currency") or "USD")
        interval = str(job.get("interval") or "")
        if min_amt and max_amt:
            budget_str = f"{currency} {min_amt:,.0f}–{max_amt:,.0f}/{interval}" if interval else f"{currency} {min_amt:,.0f}–{max_amt:,.0f}"
        elif min_amt:
            budget_str = f"{currency} {min_amt:,.0f}+/{interval}" if interval else f"{currency} {min_amt:,.0f}+"
        else:
            budget_str = ""

        # Date
        date_posted = job.get("date_posted")
        try:
            if hasattr(date_posted, "isoformat"):
                created_at = datetime.combine(date_posted, datetime.min.time()).replace(tzinfo=timezone.utc)
            else:
                created_at = datetime.now(timezone.utc)
        except Exception:
            created_at = datetime.now(timezone.utc)

        jid = self._job_id(job)
        body = (
            f"{title}\n\n"
            f"Company: {company} | Location: {location} | Remote: {is_remote}\n"
            f"Type: {job_type} | Level: {job_level}\n"
            f"Budget/Rate: {budget_str}\n"
            f"Source: {site}\n\n"
            f"{description}"
        )[:4000]

        author = await self.upsert_user(
            platform_name="upwork",
            platform_user_id=f"client_{jid}",
            username=company[:80] if company else "employer",
        )

        await self.upsert_post(
            user_id=author,
            platform_name="upwork",
            post_type="post",
            platform_post_id=f"upwork_{jid}",
            body=body,
            title=title,
            url=job_url,
            posted_at=created_at,
            raw_metadata={
                "source": site,           # "indeed" or "linkedin"
                "job_id": jid,
                "company": company,
                "budget": budget_str,
                "job_type": job_type,
                "job_level": job_level,
                "is_remote": is_remote,
                "location": location,
                "query": query,
                "via": "jobspy",
            },
        )
