"""Upwork job scraper — uses public RSS feeds (no auth, no proxy needed).

Upwork exposes a public RSS feed for job searches that returns structured XML
with job title, description, budget, skills, and publication date.

No credentials or proxy required.
"""

import asyncio
import html as html_lib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import structlog

from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

RSS_URL = "https://www.upwork.com/ab/feed/jobs/rss"

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
    "n8n automation",
    "Zapier integration",
    "OpenAI API integration",
    "vector database",
    "AI assistant",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


class UpworkScraper(BaseScraper):
    """
    Scrapes Upwork job listings via public RSS feed.
    Captures: title, description, budget, skills, experience level.
    """

    def __init__(self):
        super().__init__(scraper_name="upwork_scraper", request_delay=2.5)

    async def scrape(self, **kwargs):
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
        ) as client:
            for query in SEARCH_QUERIES:
                await self.rate_limit()
                await self._scrape_query(client, query, seen_ids)

    async def _scrape_query(
        self, client: httpx.AsyncClient, query: str, seen_ids: set[str]
    ):
        url = f"{RSS_URL}?q={quote(query)}&sort=recency&paging=0;50&api_params=1"
        try:
            resp = await client.get(url, headers=_HEADERS)
            if resp.status_code != 200:
                self.log.warning(
                    "upwork_rss_failed", query=query, status=resp.status_code
                )
                return

            items = self._parse_rss(resp.text)
            for item in items:
                jid = item.get("jid", "")
                if not jid or jid in seen_ids:
                    continue
                seen_ids.add(jid)
                await self._store_item(item, query)

        except Exception as e:
            self.log.warning("upwork_scrape_failed", query=query, error=str(e))

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_rss(self, text: str) -> list[dict]:
        """Parse Upwork RSS XML and return list of job dicts."""
        items = []
        try:
            # Strip XML declaration issues that can occur
            text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)([^;]{1,20};?)', r'&amp;\1', text)
            root = ET.fromstring(text)
        except ET.ParseError:
            try:
                # Fallback: strip problematic characters
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
                root = ET.fromstring(text)
            except Exception:
                return items

        channel = root.find("channel")
        if channel is None:
            return items

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link") or "").strip()
            desc  = (item.findtext("description") or "")
            pub   = (item.findtext("pubDate") or "").strip()
            guid  = (item.findtext("guid") or link).strip()

            if not title:
                continue

            # Job ID from guid/link  (/job/_~01abc123...)
            jid_m = re.search(r'~([0-9a-f]{16,})', guid + link)
            jid = jid_m.group(1) if jid_m else re.sub(r'[^a-z0-9]', '', guid.lower())[:32]
            if not jid:
                continue

            # Clean HTML from description
            desc_clean = html_lib.unescape(re.sub(r'<[^>]+>', ' ', desc))
            desc_clean = re.sub(r'\s+', ' ', desc_clean).strip()

            # Extract structured fields from description text
            budget_m = re.search(
                r'Budget[:\s]+\$?([\d,]+(?:\.\d+)?(?:\s*[-–]\s*\$?[\d,]+(?:\.\d+)?)?)',
                desc_clean, re.I
            )
            budget_str = budget_m.group(0).strip() if budget_m else ""

            hourly_m = re.search(r'Hourly Range[:\s]+\$?([\d.]+\s*[-–]\s*\$?[\d.]+)', desc_clean, re.I)
            if hourly_m and not budget_str:
                budget_str = f"${hourly_m.group(1)}/hr"

            skills_m = re.search(r'Skills?[:\s]+([^\n]{5,200})', desc_clean, re.I)
            skills = (
                [s.strip() for s in skills_m.group(1).split(",") if s.strip()]
                if skills_m else []
            )

            exp_m = re.search(r'Experience Level[:\s]+([^\n,]+)', desc_clean, re.I)
            exp_level = exp_m.group(1).strip() if exp_m else ""

            # Parse date
            try:
                created_at = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S +0000").replace(
                    tzinfo=timezone.utc
                )
            except Exception:
                created_at = datetime.now(timezone.utc)

            items.append(
                dict(
                    title=title,
                    link=link,
                    desc=desc_clean,
                    jid=jid,
                    budget=budget_str,
                    skills=skills,
                    exp_level=exp_level,
                    created_at=created_at,
                )
            )

        return items

    # ── Storage ──────────────────────────────────────────────────────────────

    async def _store_item(self, item: dict, query: str):
        author = await self.upsert_user(
            platform_name="upwork",
            platform_user_id=f"upwork_job_{item['jid']}",
            username="upwork_client",
        )

        body = f"{item['title']}\n\n{item['desc']}"[:4000]

        await self.upsert_post(
            user_id=author,
            platform_name="upwork",
            post_type="post",
            platform_post_id=f"upwork_{item['jid']}",
            body=body,
            title=item["title"],
            url=item["link"],
            posted_at=item["created_at"],
            raw_metadata={
                "source": "upwork",
                "job_id": item["jid"],
                "budget": item["budget"],
                "experience_level": item["exp_level"],
                "skills": item["skills"],
                "query": query,
            },
        )
