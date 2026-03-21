"""Product-targeted Reddit scraper — searches Reddit for specific product names.

Pulls product names from YC companies, Product Hunt launches, and discovered_products,
then searches Reddit for each to collect user reviews, opinions, and mentions.
Posts are stored in the standard `posts` table and flow through all existing processors.
"""

import asyncio
from urllib.parse import quote

import feedparser
import httpx
import structlog

from config.sources import PRODUCT_REDDIT_CONFIG
from scrapers.base_scraper import BaseScraper
from scrapers.reddit_scraper import (
    REDDIT_BASE, REDDIT_UA, POST_ID_RE, strip_html, parse_rss_date,
)

logger = structlog.get_logger()


class ProductRedditScraper(BaseScraper):
    """Searches Reddit for product names from YC, PH, and discovered products."""

    PLATFORM = "reddit"

    def __init__(self):
        super().__init__(
            scraper_name="product_reddit_scraper",
            request_delay=PRODUCT_REDDIT_CONFIG.get("request_delay", 3.0),
        )

    async def scrape(self, **kwargs):
        cfg = PRODUCT_REDDIT_CONFIG
        max_products = cfg.get("max_products_per_run", 50)
        sort = cfg.get("search_sort", "relevance")
        time_filter = cfg.get("search_time_filter", "month")
        limit = cfg.get("search_limit", 100)

        self.log.info("product_reddit_scrape_start", max_products=max_products)

        # Load product names from DB
        product_names = await self._load_product_names(cfg)
        self.log.info("products_loaded", count=len(product_names))

        if not product_names:
            self.log.info("no_products_to_search")
            return

        # Cap at max per run
        product_names = product_names[:max_products]

        headers = {"User-Agent": REDDIT_UA}
        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=headers,
        ) as client:
            for product_name in product_names:
                await self._search_product(
                    client, product_name, sort, time_filter, limit,
                )

        self.log.info(
            "product_reddit_scrape_complete",
            products_searched=len(product_names),
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _load_product_names(self, cfg: dict) -> list[str]:
        """Load and deduplicate product names from YC, PH, and discovered_products."""
        from sqlalchemy import select, text
        from database.connection import async_session, YCCompany, PHLaunch, DiscoveredProduct

        names: set[str] = set()
        min_mentions = cfg.get("min_product_mentions", 3)

        async with async_session() as session:
            # YC companies (top 200 by name)
            result = await session.execute(
                select(YCCompany.name)
                .where(YCCompany.name.isnot(None))
                .order_by(YCCompany.id.desc())
                .limit(200)
            )
            for row in result.all():
                if row.name and len(row.name) > 2:
                    names.add(row.name)

            # PH launches (top 200 by votes)
            result = await session.execute(
                select(PHLaunch.name)
                .where(PHLaunch.name.isnot(None))
                .order_by(PHLaunch.votes_count.desc())
                .limit(200)
            )
            for row in result.all():
                if row.name and len(row.name) > 2:
                    names.add(row.name)

            # Discovered products (active, enough mentions)
            result = await session.execute(
                select(DiscoveredProduct.canonical_name)
                .where(DiscoveredProduct.status == "active")
                .where(DiscoveredProduct.total_mentions >= min_mentions)
            )
            for row in result.all():
                if row.canonical_name and len(row.canonical_name) > 2:
                    names.add(row.canonical_name)

        # Filter out very short or generic names that would produce noisy results
        generic = {"AI", "ML", "API", "Pro", "App", "Hub", "Bot", "Lab", "One", "Go", "Up"}
        return sorted([n for n in names if n not in generic])

    async def _search_product(
        self,
        client: httpx.AsyncClient,
        product_name: str,
        sort: str,
        time_filter: str,
        limit: int,
    ):
        """Search Reddit for a specific product name."""
        encoded = quote(product_name)
        url = f"{REDDIT_BASE}/search/.rss?q={encoded}&sort={sort}&t={time_filter}&limit={limit}"

        try:
            resp = await self.fetch_url(client, url)
            await self.rate_limit()
        except Exception as e:
            self.log.warning("product_search_failed", product=product_name, error=str(e))
            return

        feed = feedparser.parse(resp.text)
        count = 0

        for entry in feed.entries:
            post_id = self._extract_post_id(entry)
            if not post_id:
                continue

            author = self._extract_author(entry)
            body = strip_html(
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
            title = entry.get("title", "")
            if not body and title:
                body = title
            if not body:
                continue

            posted_at = parse_rss_date(
                entry.get("published") or entry.get("updated")
            )

            # Extract subreddit from link
            link = entry.get("link", "")
            subreddit = None
            import re
            sr_match = re.search(r"/r/([^/]+)/", link)
            if sr_match:
                subreddit = sr_match.group(1)

            # Upsert user
            user_id = None
            if author:
                user_id = await self.upsert_user(
                    platform_name=self.PLATFORM,
                    platform_user_id=author,
                    username=author,
                    profile_url=f"https://www.reddit.com/user/{author}",
                )

            await self.upsert_post(
                user_id=user_id,
                platform_name=self.PLATFORM,
                post_type="submission",
                platform_post_id=f"reddit_{post_id}",
                title=title,
                body=body,
                url=link,
                subreddit=subreddit,
                posted_at=posted_at,
                raw_metadata={
                    "source": "product_search",
                    "search_query": product_name,
                    "sort": sort,
                },
            )
            count += 1

        if count > 0:
            self.log.debug("product_search_results", product=product_name, posts=count)

    def _extract_author(self, entry) -> str | None:
        author = entry.get("author", "")
        if author and author.startswith("/u/"):
            return author[3:]
        import re
        from scrapers.reddit_scraper import AUTHOR_RE
        if author:
            match = AUTHOR_RE.search(author)
            if match:
                return match.group(1)
        if author and not author.startswith("http"):
            return author.strip().lstrip("/u/")
        return None

    def _extract_post_id(self, entry) -> str | None:
        link = entry.get("link", "") or entry.get("id", "")
        match = POST_ID_RE.search(link)
        if match:
            return match.group(1)
        return None
