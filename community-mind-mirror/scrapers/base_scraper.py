"""Abstract base scraper with common patterns for all scrapers."""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select, func as sa_func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from database.connection import async_session, User, Post, ScraperRun, Platform, NewsEvent, JobListing

logger = structlog.get_logger()


def _utc_naive(dt: datetime | None = None) -> datetime:
    """Return a timezone-naive UTC datetime (for TIMESTAMP WITHOUT TIME ZONE columns)."""
    if dt is None:
        return datetime.utcnow()
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class BaseScraper(ABC):
    """Abstract base class for all Community Mind Mirror scrapers."""

    def __init__(self, scraper_name: str, request_delay: float = 1.0):
        self.scraper_name = scraper_name
        self.request_delay = request_delay
        self.run_id: int | None = None
        self.records_fetched = 0
        self.records_new = 0
        self.records_updated = 0
        self._platform_id_cache: dict[str, int] = {}
        self.log = logger.bind(scraper=scraper_name)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self, **kwargs):
        """Main entry point. Starts a scraper run, executes scrape(), then finalizes."""
        await self._start_run()
        try:
            await self.scrape(**kwargs)
            await self._complete_run("completed")
        except Exception as e:
            self.log.error("scraper_failed", error=str(e))
            await self._complete_run("failed", error_message=str(e))
            raise

    @abstractmethod
    async def scrape(self, **kwargs):
        """Override this with the actual scraping logic."""
        ...

    # ------------------------------------------------------------------
    # Scraper run tracking
    # ------------------------------------------------------------------

    async def _start_run(self):
        async with async_session() as session:
            run = ScraperRun(scraper_name=self.scraper_name, status="running")
            session.add(run)
            await session.commit()
            await session.refresh(run)
            self.run_id = run.id
        self.log.info("scraper_run_started", run_id=self.run_id)

    async def _complete_run(self, status: str, error_message: str | None = None):
        async with async_session() as session:
            run = await session.get(ScraperRun, self.run_id)
            if run:
                run.status = status
                run.records_fetched = self.records_fetched
                run.records_new = self.records_new
                run.records_updated = self.records_updated
                run.error_message = error_message
                run.completed_at = _utc_naive()
                await session.commit()
        self.log.info(
            "scraper_run_completed",
            run_id=self.run_id,
            status=status,
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
        )

    # ------------------------------------------------------------------
    # Platform ID helper
    # ------------------------------------------------------------------

    async def get_platform_id(self, platform_name: str) -> int:
        if platform_name in self._platform_id_cache:
            return self._platform_id_cache[platform_name]

        async with async_session() as session:
            result = await session.execute(
                select(Platform.id).where(Platform.name == platform_name)
            )
            platform_id = result.scalar_one()
            self._platform_id_cache[platform_name] = platform_id
            return platform_id

    # ------------------------------------------------------------------
    # User upsert
    # ------------------------------------------------------------------

    async def upsert_user(
        self,
        platform_name: str,
        platform_user_id: str,
        username: str | None = None,
        bio: str | None = None,
        profile_url: str | None = None,
        karma_score: int | None = None,
        account_created_at: datetime | None = None,
        raw_metadata: dict | None = None,
    ) -> int:
        """Insert or update a user. Returns the user ID."""
        platform_id = await self.get_platform_id(platform_name)

        async with async_session() as session:
            stmt = pg_insert(User).values(
                platform_id=platform_id,
                platform_user_id=platform_user_id,
                username=username or platform_user_id,
                bio=bio,
                profile_url=profile_url,
                karma_score=karma_score,
                account_created_at=_utc_naive(account_created_at) if account_created_at else None,
                raw_metadata=raw_metadata,
                last_scraped_at=_utc_naive(),
            )
            stmt = stmt.on_conflict_do_update(
                constraint="users_platform_id_platform_user_id_key",
                set_={
                    "username": stmt.excluded.username,
                    "bio": stmt.excluded.bio,
                    "profile_url": stmt.excluded.profile_url,
                    "karma_score": stmt.excluded.karma_score,
                    "account_created_at": stmt.excluded.account_created_at,
                    "raw_metadata": stmt.excluded.raw_metadata,
                    "last_scraped_at": stmt.excluded.last_scraped_at,
                    "updated_at": _utc_naive(),
                },
            )
            result = await session.execute(stmt)
            await session.commit()

            # Get the user id
            user_result = await session.execute(
                select(User.id).where(
                    User.platform_id == platform_id,
                    User.platform_user_id == platform_user_id,
                )
            )
            user_id = user_result.scalar_one()

            if result.rowcount > 0:
                self.records_fetched += 1
            return user_id

    # ------------------------------------------------------------------
    # Post upsert
    # ------------------------------------------------------------------

    async def upsert_post(
        self,
        user_id: int | None,
        platform_name: str,
        post_type: str,
        platform_post_id: str,
        body: str,
        title: str | None = None,
        url: str | None = None,
        subreddit: str | None = None,
        score: int = 0,
        num_comments: int = 0,
        posted_at: datetime | None = None,
        raw_metadata: dict | None = None,
        parent_post_id: int | None = None,
    ) -> int | None:
        """Insert or update a post. Returns post ID."""
        if not body or not body.strip():
            return None

        platform_id = await self.get_platform_id(platform_name)

        async with async_session() as session:
            stmt = pg_insert(Post).values(
                user_id=user_id,
                platform_id=platform_id,
                post_type=post_type,
                platform_post_id=platform_post_id,
                parent_post_id=parent_post_id,
                title=title,
                body=body,
                url=url,
                subreddit=subreddit,
                score=score,
                num_comments=num_comments,
                posted_at=_utc_naive(posted_at) if posted_at else None,
                raw_metadata=raw_metadata,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="posts_platform_id_platform_post_id_key",
                set_={
                    "title": stmt.excluded.title,
                    "body": stmt.excluded.body,
                    "score": stmt.excluded.score,
                    "num_comments": stmt.excluded.num_comments,
                    "raw_metadata": stmt.excluded.raw_metadata,
                },
            )
            await session.execute(stmt)
            await session.commit()

            post_result = await session.execute(
                select(Post.id).where(
                    Post.platform_id == platform_id,
                    Post.platform_post_id == platform_post_id,
                )
            )
            post_id = post_result.scalar_one_or_none()
            self.records_new += 1
            return post_id

    # ------------------------------------------------------------------
    # News event upsert (for news, arxiv, youtube transcripts, jobs)
    # ------------------------------------------------------------------

    async def upsert_news_event(
        self,
        source_type: str,
        source_name: str,
        title: str,
        url: str,
        body: str | None = None,
        authors: list | None = None,
        published_at: datetime | None = None,
        categories: list | None = None,
        raw_metadata: dict | None = None,
    ) -> int | None:
        """Insert a news event, skipping duplicates by URL."""
        if not title or not title.strip():
            return None

        async with async_session() as session:
            # Deduplicate by URL
            if url:
                existing = await session.execute(
                    select(NewsEvent.id).where(NewsEvent.url == url)
                )
                if existing.scalar_one_or_none() is not None:
                    return None

            event = NewsEvent(
                source_type=source_type,
                source_name=source_name,
                title=title,
                body=body,
                url=url,
                authors=authors,
                published_at=_utc_naive(published_at) if published_at else None,
                categories=categories,
                raw_metadata=raw_metadata,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            self.records_new += 1
            return event.id

    # ------------------------------------------------------------------
    # Job listing upsert (dedicated table)
    # ------------------------------------------------------------------

    async def upsert_job_listing(
        self,
        source: str,
        title: str,
        url: str,
        company: str = "",
        location: str = "",
        job_type: str = "",
        salary_min: float | None = None,
        salary_max: float | None = None,
        salary_currency: str = "",
        remote: bool = False,
        seniority: str = "",
        department: str = "",
        tags: list | None = None,
        description: str | None = None,
        apply_url: str | None = None,
        published_at: datetime | None = None,
        raw_metadata: dict | None = None,
    ) -> int | None:
        """Insert or update a job listing. Deduplicates by URL."""
        if not title or not title.strip() or not url:
            return None

        async with async_session() as session:
            stmt = pg_insert(JobListing).values(
                source=source,
                title=title,
                company=company,
                location=location,
                job_type=job_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=salary_currency,
                remote=remote,
                seniority=seniority,
                department=department,
                tags=tags,
                description=(description[:5000] if description else None),
                url=url,
                apply_url=apply_url,
                published_at=_utc_naive(published_at) if published_at else None,
                raw_metadata=raw_metadata,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["url"],
                set_={
                    "title": stmt.excluded.title,
                    "company": stmt.excluded.company,
                    "location": stmt.excluded.location,
                    "salary_min": stmt.excluded.salary_min,
                    "salary_max": stmt.excluded.salary_max,
                    "tags": stmt.excluded.tags,
                    "description": stmt.excluded.description,
                    "raw_metadata": stmt.excluded.raw_metadata,
                },
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                self.records_new += 1

            row = await session.execute(
                select(JobListing.id).where(JobListing.url == url)
            )
            return row.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Check if user was recently scraped
    # ------------------------------------------------------------------

    async def was_recently_scraped(
        self, platform_name: str, platform_user_id: str, hours: int = 24
    ) -> bool:
        """Check if a user was scraped within the last N hours."""
        platform_id = await self.get_platform_id(platform_name)

        async with async_session() as session:
            result = await session.execute(
                select(User.last_scraped_at).where(
                    User.platform_id == platform_id,
                    User.platform_user_id == platform_user_id,
                )
            )
            last_scraped = result.scalar_one_or_none()
            if last_scraped is None:
                return False

            # Ensure both are naive for comparison
            if last_scraped.tzinfo is not None:
                last_scraped = last_scraped.replace(tzinfo=None)

            age_hours = (
                _utc_naive() - last_scraped
            ).total_seconds() / 3600
            return age_hours < hours

    # ------------------------------------------------------------------
    # HTTP with retries
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def fetch_url(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict | None = None,
    ) -> httpx.Response:
        """Fetch a URL with retry logic."""
        response = await client.get(url, headers=headers)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            self.log.warning("rate_limited", url=url, retry_after=retry_after)
            await asyncio.sleep(retry_after)
            raise httpx.HTTPStatusError(
                "Rate limited", request=response.request, response=response
            )
        response.raise_for_status()
        return response

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    async def rate_limit(self):
        """Sleep for the configured delay between requests."""
        await asyncio.sleep(self.request_delay)
