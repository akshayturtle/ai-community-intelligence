"""News RSS scraper — aggregates tech/AI news from RSS feeds. No API key needed."""

import re
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx
import structlog

from config.settings import USER_AGENT
from config.sources import NEWS_RSS_FEEDS, NEWS_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()


def _parse_feed_date(entry) -> datetime | None:
    """Parse date from a feedparser entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    # Fallback: try string parsing
    for field in ("published", "updated"):
        val = entry.get(field, "")
        if val:
            try:
                import email.utils
                dt = email.utils.parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                continue
    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags and unescape entities."""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class NewsScraper(BaseScraper):
    """Scrapes tech/AI news from RSS feeds."""

    def __init__(self):
        super().__init__(scraper_name="news_scraper", request_delay=1.0)

    async def scrape(
        self,
        feeds: list[dict] | None = None,
        **kwargs,
    ):
        """Scrape all configured RSS feeds."""
        targets = feeds or NEWS_RSS_FEEDS

        self.log.info("news_scrape_start", feeds=len(targets))

        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for feed_config in targets:
                await self._scrape_feed(client, headers, feed_config)

        self.log.info(
            "news_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_feed(
        self, client: httpx.AsyncClient, headers: dict, feed_config: dict
    ):
        """Scrape a single RSS feed."""
        feed_name = feed_config["name"]
        feed_url = feed_config["url"]
        category = feed_config.get("category", "tech_news")

        self.log.info("scraping_feed", feed=feed_name)

        try:
            response = await self.fetch_url(client, feed_url, headers=headers)
        except Exception as e:
            self.log.warning("feed_fetch_failed", feed=feed_name, error=str(e))
            return

        await self.rate_limit()

        feed = feedparser.parse(response.text)

        for entry in feed.entries:
            title = _clean_html(entry.get("title", ""))
            if not title:
                continue

            link = entry.get("link", "")
            if not link:
                continue

            # Extract body/summary
            summary = ""
            if entry.get("summary"):
                summary = _clean_html(entry["summary"])
            elif entry.get("content"):
                for content_block in entry["content"]:
                    summary = _clean_html(content_block.get("value", ""))
                    if summary:
                        break
            elif entry.get("description"):
                summary = _clean_html(entry["description"])

            published_at = _parse_feed_date(entry)

            # Extract authors
            authors = []
            if entry.get("author"):
                authors = [entry["author"]]
            elif entry.get("authors"):
                authors = [a.get("name", "") for a in entry["authors"] if a.get("name")]

            # Store as news event (deduplicates by URL inside upsert_news_event)
            await self.upsert_news_event(
                source_type="news",
                source_name=feed_name,
                title=title,
                body=summary,
                url=link,
                authors=authors if authors else None,
                published_at=published_at,
                categories=[category],
                raw_metadata={
                    "feed_url": feed_url,
                    "entry_id": entry.get("id", ""),
                    "tags": [t.get("term", "") for t in entry.get("tags", [])],
                },
            )

        self.log.info("feed_done", feed=feed_name, entries=len(feed.entries))
