"""ArXiv scraper — fetches research papers via the ArXiv API. No API key needed."""

import re
from datetime import datetime, timezone

import feedparser
import httpx
import structlog

from config.sources import ARXIV_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

ARXIV_API_BASE = "https://export.arxiv.org/api/query"


class ArXivScraper(BaseScraper):
    """Scrapes ArXiv for recent research papers in AI/ML categories."""

    def __init__(self):
        # ArXiv terms of use: 1 request per 3 seconds
        super().__init__(scraper_name="arxiv_scraper", request_delay=3.0)

    async def scrape(
        self,
        categories: list[str] | None = None,
        max_results: int | None = None,
        **kwargs,
    ):
        """Scrape ArXiv for recent papers by category."""
        cats = categories or ARXIV_SCRAPE_CONFIG["categories"]
        limit = max_results or ARXIV_SCRAPE_CONFIG["max_results_per_category"]

        self.log.info("arxiv_scrape_start", categories=len(cats), max_per_cat=limit)

        async with httpx.AsyncClient(timeout=60.0) as client:
            for category in cats:
                await self._scrape_category(client, category, limit)

        self.log.info(
            "arxiv_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_category(
        self, client: httpx.AsyncClient, category: str, max_results: int
    ):
        """Scrape a single ArXiv category with pagination."""
        self.log.info("scraping_category", category=category)
        start = 0
        page_size = min(max_results, 200)  # ArXiv recommends <= 200 per request
        total_fetched = 0

        while total_fetched < max_results:
            url = (
                f"{ARXIV_API_BASE}"
                f"?search_query=cat:{category}"
                f"&sortBy=submittedDate"
                f"&sortOrder=descending"
                f"&start={start}"
                f"&max_results={page_size}"
            )

            try:
                response = await self.fetch_url(client, url)
            except Exception as e:
                self.log.warning(
                    "arxiv_fetch_failed", category=category, start=start, error=str(e)
                )
                break

            await self.rate_limit()

            feed = feedparser.parse(response.text)
            entries = feed.entries

            if not entries:
                break

            for entry in entries:
                await self._process_entry(entry, category)
                total_fetched += 1
                if total_fetched >= max_results:
                    break

            # Check if there are more results
            if len(entries) < page_size:
                break

            start += page_size

        self.log.info(
            "category_done", category=category, papers=total_fetched
        )

    async def _process_entry(self, entry, primary_category: str):
        """Process a single ArXiv entry and store as news_event."""
        # Extract arxiv ID from the entry id URL
        entry_id = entry.get("id", "")
        arxiv_id = self._extract_arxiv_id(entry_id)
        if not arxiv_id:
            return

        title = (entry.get("title", "") or "").replace("\n", " ").strip()
        if not title:
            return

        # Abstract/summary
        abstract = (entry.get("summary", "") or "").strip()

        # Authors
        authors = []
        for author in entry.get("authors", []):
            name = author.get("name", "")
            if name:
                authors.append(name)

        # Categories
        categories = [primary_category]
        for tag in entry.get("tags", []):
            term = tag.get("term", "")
            if term and term not in categories:
                categories.append(term)

        # Published date
        published_at = None
        if entry.get("published_parsed"):
            try:
                published_at = datetime(
                    *entry["published_parsed"][:6], tzinfo=timezone.utc
                )
            except Exception:
                pass

        # Updated date
        updated_at = None
        if entry.get("updated_parsed"):
            try:
                updated_at = datetime(
                    *entry["updated_parsed"][:6], tzinfo=timezone.utc
                )
            except Exception:
                pass

        # PDF link
        pdf_link = ""
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_link = link.get("href", "")
                break
        if not pdf_link:
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}"

        # URL (abstract page)
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"

        await self.upsert_news_event(
            source_type="arxiv",
            source_name="ArXiv",
            title=title,
            body=abstract,
            url=abs_url,
            authors=authors if authors else None,
            published_at=published_at,
            categories=categories,
            raw_metadata={
                "arxiv_id": arxiv_id,
                "pdf_url": pdf_link,
                "primary_category": primary_category,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "author_count": len(authors),
            },
        )
        self.records_fetched += 1

    def _extract_arxiv_id(self, url: str) -> str | None:
        """Extract arxiv ID from URL like http://arxiv.org/abs/2401.12345v1."""
        match = re.search(r"(\d{4}\.\d{4,5})(v\d+)?$", url)
        if match:
            return match.group(1)
        # Older format: cs/0601001
        match = re.search(r"([a-z-]+/\d{7})(v\d+)?$", url)
        if match:
            return match.group(1)
        return None
