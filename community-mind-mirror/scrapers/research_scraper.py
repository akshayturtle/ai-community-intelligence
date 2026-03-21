"""On-demand Reddit scraper for custom market research projects.

Searches Reddit for user-provided keywords and stores posts in the standard
`posts` table tagged with project_id for later analysis.
"""

import re
from urllib.parse import quote

import feedparser
import httpx
import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.reddit_scraper import (
    REDDIT_BASE, REDDIT_UA, POST_ID_RE, AUTHOR_RE, strip_html, parse_rss_date,
)

logger = structlog.get_logger()


class ResearchScraper(BaseScraper):
    """Searches Reddit for custom research project keywords."""

    PLATFORM = "reddit"

    def __init__(self):
        super().__init__(
            scraper_name="research_scraper",
            request_delay=3.0,
        )

    async def scrape(self, **kwargs):
        """Required by BaseScraper. Delegates to scrape_project()."""
        return await self.scrape_project(**kwargs)

    async def scrape_project(
        self,
        project_id: int,
        keywords: list[str],
        sort: str = "relevance",
        time_filter: str = "year",
        limit: int = 100,
    ) -> int:
        """Search Reddit for each keyword and store posts.

        Returns total posts collected.
        """
        self.log.info(
            "research_scrape_start",
            project_id=project_id,
            keyword_count=len(keywords),
        )

        headers = {"User-Agent": REDDIT_UA}
        total = 0

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=headers,
        ) as client:
            for keyword in keywords:
                count = await self._search_keyword(
                    client, project_id, keyword, sort, time_filter, limit,
                )
                total += count

        self.log.info(
            "research_scrape_complete",
            project_id=project_id,
            keywords_searched=len(keywords),
            total_posts=total,
            fetched=self.records_fetched,
            new=self.records_new,
        )
        return total

    async def _search_keyword(
        self,
        client: httpx.AsyncClient,
        project_id: int,
        keyword: str,
        sort: str,
        time_filter: str,
        limit: int,
    ) -> int:
        """Search Reddit for a single keyword."""
        encoded = quote(keyword)
        url = f"{REDDIT_BASE}/search/.rss?q={encoded}&sort={sort}&t={time_filter}&limit={limit}"

        try:
            resp = await self.fetch_url(client, url)
            await self.rate_limit()
        except Exception as e:
            self.log.warning(
                "research_search_failed",
                project_id=project_id,
                keyword=keyword,
                error=str(e),
            )
            return 0

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
                    "source": "custom_research",
                    "project_id": project_id,
                    "search_query": keyword,
                },
            )
            count += 1

        if count > 0:
            self.log.debug(
                "research_keyword_results",
                project_id=project_id,
                keyword=keyword,
                posts=count,
            )
        return count

    def _extract_author(self, entry) -> str | None:
        author = entry.get("author", "")
        if author and author.startswith("/u/"):
            return author[3:]
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
