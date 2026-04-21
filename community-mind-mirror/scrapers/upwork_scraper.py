"""Upwork freelance project scraper — uses residential proxies (DataImpulse).

Scrapes Upwork job search to surface what clients are posting:
skills demanded, budget ranges, experience levels, project types.

Requires: DATAIMPULSE_HOST, DATAIMPULSE_PORT, DATAIMPULSE_USER, DATAIMPULSE_PASS
"""

import asyncio
import json
import re
from datetime import datetime, timezone

import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.proxy import proxy_client, random_headers, json_headers, is_configured

logger = structlog.get_logger()

# Upwork search queries — mix of AI, dev, data, automation
SEARCH_QUERIES = [
    "AI agent development",
    "LLM fine tuning",
    "machine learning model",
    "Python automation",
    "web scraping",
    "React developer",
    "FastAPI backend",
    "data pipeline",
    "chatbot development",
    "computer vision",
    "RAG system",
    "blockchain smart contract",
    "mobile app Flutter",
    "DevOps AWS",
    "data analyst",
]

UPWORK_SEARCH = "https://www.upwork.com/search/jobs/url"
UPWORK_API    = "https://www.upwork.com/api/graphql/v1"


class UpworkScraper(BaseScraper):
    """
    Scrapes Upwork project listings via residential proxy.
    Captures: title, description, budget, skills, experience level, proposals count.
    """

    def __init__(self):
        super().__init__(scraper_name="upwork_scraper", request_delay=4.0)

    async def scrape(self, **kwargs):
        if not is_configured():
            self.log.warning(
                "upwork_no_proxy",
                hint="Set DATAIMPULSE_HOST/PORT/USER/PASS env vars to enable Upwork scraping.",
            )
            return

        seen_ids: set[str] = set()

        for query in SEARCH_QUERIES:
            await self.rate_limit()
            await self._scrape_query(query, seen_ids)

    async def _scrape_query(self, query: str, seen_ids: set[str]):
        # Use a fresh sticky session per query so we look like a real user browsing
        session_id = re.sub(r"[^a-z0-9]", "", query.lower())[:12]

        async with proxy_client(sticky_session=session_id) as client:
            try:
                # Step 1: hit the search page to get cookies / visitor_id
                search_url = (
                    f"https://www.upwork.com/nx/search/jobs/"
                    f"?q={query.replace(' ', '+')}&sort=recency&per_page=50"
                )
                page_resp = await client.get(
                    search_url,
                    headers=random_headers(),
                )
                await asyncio.sleep(1.5)

                # Step 2: hit the internal search API (same session = same IP)
                api_url = (
                    "https://www.upwork.com/search/jobs/url"
                    f"?q={query.replace(' ', '%20')}&sort=recency&per_page=50"
                )
                resp = await client.get(
                    api_url,
                    headers=json_headers(
                        referer=search_url,
                        extra={"X-Requested-With": "XMLHttpRequest"},
                    ),
                )

                if resp.status_code != 200:
                    self.log.warning(
                        "upwork_api_failed",
                        query=query, status=resp.status_code,
                    )
                    return

                # Try parsing as JSON first, then fall back to HTML parsing
                try:
                    data = resp.json()
                    jobs = (
                        data.get("searchResults", {}).get("jobs", [])
                        or data.get("jobs", [])
                        or []
                    )
                except Exception:
                    # HTML response — extract JSON from embedded __NEXT_DATA__
                    jobs = self._extract_from_html(resp.text)

                for job in jobs:
                    jid = str(job.get("id") or job.get("uid") or "")
                    if not jid or jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    await self._store_job(job, query)

            except Exception as e:
                self.log.warning("upwork_scrape_failed", query=query, error=str(e))

    def _extract_from_html(self, html: str) -> list[dict]:
        """Extract job listings from Next.js __NEXT_DATA__ JSON embedded in HTML."""
        try:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if not m:
                return []
            data = json.loads(m.group(1))
            # Navigate the Next.js data tree
            props = data.get("props", {}).get("pageProps", {})
            results = (
                props.get("searchResults", {}).get("jobs", [])
                or props.get("jobs", [])
                or []
            )
            return results
        except Exception:
            return []

    async def _store_job(self, job: dict, query: str):
        title = job.get("title") or job.get("jobTitle") or ""
        if not title:
            return

        jid     = str(job.get("id") or job.get("uid") or "")
        snippet = job.get("snippet") or job.get("description") or ""
        url     = f"https://www.upwork.com/jobs/{jid}" if jid else ""

        # Skills
        skills = []
        for s in job.get("skills", []) or []:
            if isinstance(s, dict):
                skills.append(s.get("prettyName") or s.get("name") or "")
            elif isinstance(s, str):
                skills.append(s)
        skills = [s for s in skills if s]

        # Budget
        budget = job.get("budget") or {}
        if isinstance(budget, dict):
            b_min = budget.get("min") or budget.get("minimum")
            b_max = budget.get("max") or budget.get("maximum")
            currency = budget.get("currencyCode", "USD")
            budget_str = f"{currency} {b_min}–{b_max}" if b_min and b_max else (f"{currency} {b_min}+" if b_min else "")
        else:
            budget_str = str(budget) if budget else ""

        # Hourly rate
        hourly = job.get("hourlyBudgetMin") or job.get("hourlyRate")
        if hourly and not budget_str:
            hourly_max = job.get("hourlyBudgetMax", "")
            budget_str = f"${hourly}–${hourly_max}/hr" if hourly_max else f"${hourly}/hr"

        proposals = job.get("proposalsTier") or job.get("totalApplicants") or ""
        exp_level = job.get("experienceLevel") or job.get("contractorTier") or ""
        job_type  = job.get("jobType") or ("hourly" if hourly else "fixed")
        duration  = job.get("duration") or job.get("projectLength") or ""

        published_raw = job.get("postedDate") or job.get("publishedDate") or ""
        try:
            created_at = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
        except Exception:
            created_at = datetime.now(timezone.utc)

        content = (
            f"{title}\n\n"
            f"Budget: {budget_str}\n"
            f"Type: {job_type} | Level: {exp_level} | Duration: {duration}\n"
            f"Proposals: {proposals}\n"
            f"Skills: {', '.join(skills)}\n\n"
            f"{snippet}"
        )

        author = await self.upsert_user(
            platform_name="upwork",
            platform_user_id=f"upwork_job_{jid}",
            username="upwork_client",
            display_name="Upwork Client",
        )

        await self.upsert_post(
            platform_name="upwork",
            platform_post_id=f"upwork_{jid}",
            author_id=author,
            title=title,
            content=content[:4000],
            url=url,
            created_at=created_at,
            raw_metadata={
                "source": "upwork",
                "job_id": jid,
                "budget": budget_str,
                "job_type": job_type,
                "experience_level": exp_level,
                "duration": duration,
                "proposals_tier": str(proposals),
                "skills": skills,
                "query": query,
            },
        )
