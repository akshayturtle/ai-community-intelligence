"""Freelancer.com project scraper — public API, no auth required.

Scrapes active freelance projects to analyze market demand for tech skills.
Useful for understanding what clients are building and what they're willing to pay.
"""

import re
from datetime import datetime, timezone

import httpx
import structlog

from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

BASE_URL = "https://www.freelancer.com/api/projects/0.1"

# Tech search queries — each becomes a separate API call
TECH_QUERIES = [
    "AI agent", "machine learning", "LLM", "ChatGPT", "OpenAI",
    "Python automation", "data science", "web scraping",
    "React developer", "FastAPI", "blockchain smart contract",
    "mobile app Flutter", "computer vision", "NLP model",
    "RAG chatbot", "fine tuning", "vector database",
    "n8n automation", "Zapier workflow",
]

# Skills that classify a project as tech-related (post-filter)
TECH_SKILLS = {
    "python", "javascript", "typescript", "react", "node.js", "php", "java",
    "c++", "rust", "golang", "swift", "flutter", "kotlin", "django", "fastapi",
    "machine learning", "artificial intelligence", "data science", "deep learning",
    "nlp", "computer vision", "llm", "openai", "tensorflow", "pytorch",
    "blockchain", "solidity", "web3", "ethereum", "smart contract",
    "sql", "mongodb", "postgresql", "mysql", "redis", "elasticsearch",
    "aws", "gcp", "azure", "docker", "kubernetes", "devops",
    "api", "scraping", "automation", "chatbot", "mobile app development",
    "android", "ios", "full stack development",
}


def _is_tech_project(skills: list[str]) -> bool:
    skills_lower = {s.lower() for s in skills}
    return bool(skills_lower & TECH_SKILLS)


class FreelancerScraper(BaseScraper):
    """
    Scrapes tech project listings from Freelancer.com's public API.
    Captures: project title, description, budget, bid count, required skills.
    Great for analyzing what types of AI/tech projects clients are posting.
    """

    def __init__(self):
        super().__init__(scraper_name="freelancer_scraper", request_delay=2.0)

    async def scrape(self, **kwargs):
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for query in TECH_QUERIES:
                await self.rate_limit()
                try:
                    resp = await client.get(
                        f"{BASE_URL}/projects/active/",
                        params={
                            "q": query,
                            "limit": 50,
                            "job_details": "true",
                            "full_description": "true",
                            "compact": "true",
                        },
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.log.warning("freelancer_fetch_failed", query=query, error=str(e))
                    continue

                projects = data.get("result", {}).get("projects", [])
                for project in projects:
                    pid = str(project.get("id", ""))
                    if not pid or pid in seen_ids:
                        continue

                    skills = [j.get("name", "") for j in (project.get("jobs") or [])]
                    if not _is_tech_project(skills):
                        continue

                    seen_ids.add(pid)
                    await self._store_project(project, skills, query)

    async def _store_project(self, p: dict, skills: list[str], query: str):
        title = p.get("title") or ""
        if not title:
            return

        pid = p.get("id")
        seo_url = p.get("seo_url") or ""
        url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else ""

        desc = p.get("description") or ""

        # Budget
        budget = p.get("budget") or {}
        budget_min = budget.get("minimum")
        budget_max = budget.get("maximum")
        currency = (p.get("currency") or {}).get("code") or "USD"
        budget_str = ""
        if budget_min and budget_max:
            budget_str = f"{currency} {budget_min}–{budget_max}"
        elif budget_min:
            budget_str = f"{currency} {budget_min}+"

        bid_stats = p.get("bid_stats") or {}
        bid_count = bid_stats.get("bid_count") or 0
        avg_bid = bid_stats.get("bid_avg")

        submitted_ts = p.get("submitdate")
        try:
            created_at = datetime.fromtimestamp(int(submitted_ts), tz=timezone.utc)
        except Exception:
            created_at = datetime.now(timezone.utc)

        content = (
            f"{title}\n\n"
            f"Budget: {budget_str}\n"
            f"Bids: {bid_count}" + (f" | Avg bid: {currency} {avg_bid:.0f}" if avg_bid else "") + "\n"
            f"Skills: {', '.join(skills)}\n\n"
            f"{desc}"
        )

        author = await self.upsert_user(
            platform_name="freelancer",
            platform_user_id=f"project_{pid}",
            username=f"client_{pid}",
        )

        await self.upsert_post(
            user_id=author,
            platform_name="freelancer",
            post_type="post",
            platform_post_id=f"freelancer_{pid}",
            body=content[:4000],
            title=title,
            url=url,
            posted_at=created_at,
            raw_metadata={
                "source": "freelancer",
                "project_id": pid,
                "budget_min": budget_min,
                "budget_max": budget_max,
                "currency": currency,
                "bid_count": bid_count,
                "avg_bid": avg_bid,
                "skills": skills,
                "query": query,
                "project_type": p.get("type"),
                "status": p.get("status"),
            },
        )
