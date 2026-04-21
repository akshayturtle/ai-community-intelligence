"""Web3.career job scraper — free public API, no auth required."""

import hashlib
from datetime import datetime, timezone

import httpx

from scrapers.base_scraper import BaseScraper

API_URL = "https://web3.career/api/v1"
USER_AGENT = "Mozilla/5.0 (compatible; CommunityMindMirror/1.0)"

TAGS = [
    "solidity", "rust", "web3", "blockchain", "smart-contract",
    "defi", "ethereum", "solana", "crypto", "ai", "machine-learning",
    "backend", "fullstack", "typescript",
]


class Web3CareerScraper(BaseScraper):
    """Scrapes Web3/crypto/blockchain/AI jobs from web3.career's free API."""

    def __init__(self):
        super().__init__(scraper_name="web3career_scraper", request_delay=1.5)

    async def scrape(self, **kwargs):
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for tag in TAGS:
                await self.rate_limit()
                url = f"{API_URL}?page=1&tag={tag}"
                try:
                    resp = await client.get(
                        url, headers={"User-Agent": USER_AGENT}
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.log.warning("web3career_fetch_failed", tag=tag, error=str(e))
                    continue

                # API returns {"jobs": [...]} or just [...]
                jobs = data.get("jobs", data) if isinstance(data, dict) else data
                if not isinstance(jobs, list):
                    continue

                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    job_id = str(job.get("id") or job.get("job_id") or "")
                    if not job_id:
                        key = f"{job.get('title','')}{job.get('company','')}"
                        job_id = hashlib.md5(key.encode()).hexdigest()[:12]
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    await self._store_job(job, job_id, tag)

    async def _store_job(self, job: dict, job_id: str, tag: str):
        title   = job.get("title") or job.get("job_title") or ""
        company = job.get("company") or job.get("company_name") or ""
        if not title or not company:
            return

        location    = job.get("location") or "Remote"
        url         = job.get("url") or job.get("job_url") or ""
        description = job.get("description") or job.get("body") or ""
        salary      = job.get("salary") or ""

        created_raw = job.get("created_at") or job.get("date") or ""
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
            platform_name="web3career",
            platform_user_id=f"co_{company.lower().replace(' ', '_')[:40]}",
            username=company,
            display_name=company,
        )

        await self.upsert_post(
            platform_name="web3career",
            platform_post_id=f"web3career_{job_id}",
            author_id=author,
            title=title,
            content=content[:4000],
            url=url,
            created_at=created_at,
            raw_metadata={
                "source": "web3career",
                "company": company,
                "location": location,
                "salary": salary,
                "tag": tag,
                "job_type": job.get("job_type") or job.get("type") or "full-time",
                "remote": True,
            },
        )
