"""Stack Overflow scraper — fetches questions by tag and tracks tag trends via the SO API."""

from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.settings import SO_API_KEY
from database.connection import async_session, SOQuestion
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

SO_API_BASE = "https://api.stackexchange.com/2.3"

SO_TAGS_TO_TRACK = [
    "langchain",
    "openai-api",
    "huggingface",
    "llm",
    "chatgpt-api",
    "pytorch",
    "transformers",
    "crewai",
    "vector-database",
    "pinecone",
    "chromadb",
    "rag",
    "ai-agent",
    "mcp",
]

SO_TREND_KEYWORDS = ["llm", "agent", "rag", "embedding", "transformer", "mcp"]

SO_SCRAPE_CONFIG = {
    "questions_per_tag": 50,
    "scrape_interval_hours": 24,
    "request_delay": 1.0,
}


class StackOverflowScraper(BaseScraper):
    """Scrapes Stack Overflow questions by tag and tracks tag popularity trends."""

    def __init__(self):
        super().__init__(
            scraper_name="stackoverflow_scraper",
            request_delay=SO_SCRAPE_CONFIG["request_delay"],
        )

    # ------------------------------------------------------------------
    # Main scrape entry point
    # ------------------------------------------------------------------

    async def scrape(self, **kwargs):
        """Fetch recent questions for tracked tags, then collect tag trend data."""
        tags = kwargs.get("tags", SO_TAGS_TO_TRACK)
        questions_per_tag = kwargs.get(
            "questions_per_tag", SO_SCRAPE_CONFIG["questions_per_tag"]
        )

        self.log.info(
            "so_scrape_start",
            tag_count=len(tags),
            questions_per_tag=questions_per_tag,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Fetch questions for each tracked tag
            for tag in tags:
                await self._fetch_questions_for_tag(client, tag, questions_per_tag)
                await self.rate_limit()

            # Phase 2: Fetch tag counts for trend tracking
            for keyword in SO_TREND_KEYWORDS:
                await self._fetch_tag_trends(client, keyword)
                await self.rate_limit()

        self.log.info(
            "so_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
        )

    # ------------------------------------------------------------------
    # Question fetching
    # ------------------------------------------------------------------

    async def _fetch_questions_for_tag(
        self, client: httpx.AsyncClient, tag: str, page_size: int
    ):
        """Fetch recent questions for a single tag and upsert into so_questions."""
        params = {
            "order": "desc",
            "sort": "activity",
            "tagged": tag,
            "site": "stackoverflow",
            "pagesize": page_size,
        }
        if SO_API_KEY:
            params["key"] = SO_API_KEY

        url = f"{SO_API_BASE}/questions"

        try:
            response = await self.fetch_url(client, f"{url}?{_encode_params(params)}")
            data = response.json()
        except Exception as e:
            self.log.warning("so_questions_fetch_failed", tag=tag, error=str(e))
            return

        items = data.get("items", [])
        quota_remaining = data.get("quota_remaining")
        self.log.info(
            "so_questions_fetched",
            tag=tag,
            count=len(items),
            quota_remaining=quota_remaining,
        )

        for item in items:
            await self._upsert_question(item)
            self.records_fetched += 1

    async def _upsert_question(self, item: dict):
        """Upsert a single SO question into the database."""
        so_question_id = item.get("question_id")
        if not so_question_id:
            return

        creation_date = _timestamp_to_naive_utc(item.get("creation_date"))
        last_activity_date = _timestamp_to_naive_utc(item.get("last_activity_date"))

        values = {
            "so_question_id": so_question_id,
            "title": item.get("title"),
            "tags": item.get("tags"),
            "view_count": item.get("view_count", 0),
            "answer_count": item.get("answer_count", 0),
            "score": item.get("score", 0),
            "is_answered": item.get("is_answered", False),
            "link": item.get("link"),
            "creation_date": creation_date,
            "last_activity_date": last_activity_date,
            "raw_metadata": {
                "owner": item.get("owner"),
                "content_license": item.get("content_license"),
            },
            "created_at": _utc_naive(),
        }

        async with async_session() as session:
            stmt = pg_insert(SOQuestion).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["so_question_id"],
                set_={
                    "title": stmt.excluded.title,
                    "tags": stmt.excluded.tags,
                    "view_count": stmt.excluded.view_count,
                    "answer_count": stmt.excluded.answer_count,
                    "score": stmt.excluded.score,
                    "is_answered": stmt.excluded.is_answered,
                    "last_activity_date": stmt.excluded.last_activity_date,
                    "raw_metadata": stmt.excluded.raw_metadata,
                },
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                self.records_new += 1

    # ------------------------------------------------------------------
    # Tag trend tracking
    # ------------------------------------------------------------------

    async def _fetch_tag_trends(self, client: httpx.AsyncClient, keyword: str):
        """Fetch tag popularity for a keyword and store as a news event."""
        params = {
            "order": "desc",
            "sort": "popular",
            "inname": keyword,
            "site": "stackoverflow",
        }
        if SO_API_KEY:
            params["key"] = SO_API_KEY

        url = f"{SO_API_BASE}/tags"

        try:
            response = await self.fetch_url(client, f"{url}?{_encode_params(params)}")
            data = response.json()
        except Exception as e:
            self.log.warning("so_tag_trend_fetch_failed", keyword=keyword, error=str(e))
            return

        items = data.get("items", [])
        if not items:
            self.log.debug("so_no_tags_found", keyword=keyword)
            return

        # Aggregate counts across all matching tags
        tag_counts = {
            tag_item["name"]: tag_item.get("count", 0) for tag_item in items
        }
        total_count = sum(tag_counts.values())

        self.log.info(
            "so_tag_trend_fetched",
            keyword=keyword,
            matching_tags=len(tag_counts),
            total_count=total_count,
        )

        # Store the trend as a news event
        await self.upsert_news_event(
            source_type="stackoverflow_tag_trend",
            source_name="stackoverflow",
            title=f"SO tag trend: '{keyword}' — {total_count} total questions across {len(tag_counts)} tags",
            url=f"https://stackoverflow.com/tags?tab=popular&filter={keyword}",
            body=None,
            published_at=_utc_naive(),
            categories=[keyword],
            raw_metadata={
                "keyword": keyword,
                "tag_counts": tag_counts,
                "total_count": total_count,
                "snapshot_at": _utc_naive().isoformat(),
            },
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _timestamp_to_naive_utc(ts: int | None) -> datetime | None:
    """Convert a Unix timestamp to a timezone-naive UTC datetime."""
    if ts is None:
        return None
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return _utc_naive(dt)


def _encode_params(params: dict) -> str:
    """Encode query parameters for a URL (simple key=value pairs)."""
    from urllib.parse import urlencode

    return urlencode(params)
