"""PeoplePerHour project scraper — free RSS feed, no auth required.

Scrapes project/hourlie listings to surface what clients need built.
"""

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import httpx
import structlog

from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

RSS_BASE = "https://www.peopleperhour.com/feed/jobs"

SEARCH_TERMS = [
    "AI", "machine learning", "Python", "automation",
    "chatbot", "web scraping", "data science", "React",
    "API", "blockchain", "app development", "LLM",
    "OpenAI", "data analysis",
]

TECH_KEYWORDS = {
    "python", "javascript", "react", "node", "api", "sql", "database",
    "machine learning", "ai", "automation", "scraping", "data", "app",
    "backend", "frontend", "developer", "engineer", "software", "web",
    "chatbot", "bot", "integration", "blockchain", "mobile", "llm",
    "openai", "gpt", "model", "script", "code", "analysis",
}


def _is_tech(title: str, description: str = "") -> bool:
    text = (title + " " + description[:200]).lower()
    return any(kw in text for kw in TECH_KEYWORDS)


class PeoplePerHourScraper(BaseScraper):
    """Scrapes freelance project listings from PeoplePerHour via RSS."""

    def __init__(self):
        super().__init__(scraper_name="pph_scraper", request_delay=2.0)

    async def scrape(self, **kwargs):
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            for term in SEARCH_TERMS:
                await self.rate_limit()
                url = f"{RSS_BASE}?term={term.replace(' ', '+')}"
                try:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; CMM/1.0)"},
                    )
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)
                except Exception as e:
                    self.log.warning("pph_fetch_failed", term=term, error=str(e))
                    continue

                for entry in feed.entries:
                    link = entry.get("link") or ""
                    if not link or link in seen_urls:
                        continue

                    title = entry.get("title") or ""
                    summary = entry.get("summary") or entry.get("description") or ""
                    # Strip HTML
                    summary_clean = re.sub(r"<[^>]+>", " ", summary)
                    summary_clean = re.sub(r"\s+", " ", summary_clean).strip()

                    if not _is_tech(title, summary_clean):
                        continue

                    seen_urls.add(link)

                    # Parse date
                    pub = entry.get("published") or entry.get("updated") or ""
                    try:
                        created_at = parsedate_to_datetime(pub)
                    except Exception:
                        created_at = datetime.now(timezone.utc)

                    # Extract price hint from title/summary (e.g. "£50", "$200")
                    budget_match = re.search(r"[\$£€][\d,]+(?:\s*[-–]\s*[\$£€]?[\d,]+)?", title + " " + summary_clean)
                    budget_str = budget_match.group(0) if budget_match else ""

                    post_id = re.sub(r"[^a-zA-Z0-9]", "_", link[-40:])
                    content = f"{title}\n\nBudget: {budget_str}\n\n{summary_clean}"

                    author = await self.upsert_user(
                        platform_name="peopleperhour",
                        platform_user_id=f"pph_{post_id}",
                        username="pph_client",
                        display_name="PeoplePerHour Client",
                    )

                    await self.upsert_post(
                        platform_name="peopleperhour",
                        platform_post_id=f"pph_{post_id}",
                        author_id=author,
                        title=title,
                        content=content[:3000],
                        url=link,
                        created_at=created_at,
                        raw_metadata={
                            "source": "peopleperhour",
                            "budget": budget_str,
                            "search_term": term,
                        },
                    )
