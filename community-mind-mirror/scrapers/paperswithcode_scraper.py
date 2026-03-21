"""Papers With Code scraper — fetches recent papers, implementations, and trending methods. No API key needed."""

import asyncio
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.sources import PWC_SCRAPE_CONFIG
from database.connection import async_session, GithubRepo
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

PWC_API_BASE = "https://paperswithcode.com/api/v1"


class PapersWithCodeScraper(BaseScraper):
    """Scrapes Papers With Code for recent papers, their GitHub implementations, and trending methods."""

    def __init__(self):
        super().__init__(
            scraper_name="paperswithcode_scraper",
            request_delay=PWC_SCRAPE_CONFIG["request_delay"],
        )

    async def scrape(
        self,
        papers_limit: int | None = None,
        trending_methods_limit: int | None = None,
        **kwargs,
    ):
        """Scrape recent papers with implementations and trending methods."""
        p_limit = papers_limit or PWC_SCRAPE_CONFIG["papers_limit"]
        m_limit = trending_methods_limit or PWC_SCRAPE_CONFIG["trending_methods_limit"]

        self.log.info("pwc_scrape_start", papers_limit=p_limit, methods_limit=m_limit)

        async with httpx.AsyncClient(timeout=60.0) as client:
            await self._scrape_recent_papers(client, p_limit)
            await self._scrape_trending_methods(client, m_limit)

        self.log.info(
            "pwc_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    # ------------------------------------------------------------------
    # Recent papers + implementations
    # ------------------------------------------------------------------

    async def _scrape_recent_papers(self, client: httpx.AsyncClient, limit: int):
        """Fetch recent papers ordered by publication date and their code repos."""
        self.log.info("fetching_recent_papers", limit=limit)

        url = f"{PWC_API_BASE}/papers/?ordering=-paper_published&items_per_page={limit}"

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("pwc_papers_fetch_failed", error=str(e))
            return

        data = response.json()
        papers = data.get("results", [])

        for paper in papers:
            await self._process_paper(client, paper)
            await self.rate_limit()

        self.log.info("recent_papers_done", count=len(papers))

    async def _process_paper(self, client: httpx.AsyncClient, paper: dict):
        """Process a single paper: store as news event, fetch implementations."""
        paper_id = paper.get("id")
        title = (paper.get("title") or "").strip()
        if not title or not paper_id:
            return

        abstract = (paper.get("abstract") or "").strip()
        paper_url = paper.get("url_abs") or paper.get("url_pdf") or ""
        if not paper_url and paper_id:
            paper_url = f"https://paperswithcode.com/paper/{paper_id}"

        # Parse authors
        authors_raw = paper.get("authors") or []
        authors = [a.strip() for a in authors_raw if isinstance(a, str) and a.strip()]

        # Parse published date
        published_at = None
        pub_str = paper.get("published")
        if pub_str:
            try:
                published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Fetch code implementations for this paper
        implementations = await self._fetch_implementations(client, paper_id)

        # Store GitHub repos from implementations
        for impl in implementations:
            await self._upsert_github_repo(impl)

        await self.upsert_news_event(
            source_type="papers_with_code",
            source_name="Papers With Code",
            title=title,
            body=abstract if abstract else None,
            url=paper_url,
            authors=authors if authors else None,
            published_at=published_at,
            categories=paper.get("tasks") or None,
            raw_metadata={
                "paper_id": paper_id,
                "arxiv_id": paper.get("arxiv_id"),
                "url_abs": paper.get("url_abs"),
                "url_pdf": paper.get("url_pdf"),
                "proceeding": paper.get("proceeding"),
                "implementations": implementations,
                "implementation_count": len(implementations),
            },
        )
        self.records_fetched += 1

    async def _fetch_implementations(
        self, client: httpx.AsyncClient, paper_id: str
    ) -> list[dict]:
        """Fetch code repositories linked to a paper."""
        url = f"{PWC_API_BASE}/papers/{paper_id}/repositories/"

        try:
            response = await self.fetch_url(client, url)
            await self.rate_limit()
        except Exception as e:
            self.log.debug("pwc_repos_fetch_failed", paper_id=paper_id, error=str(e))
            return []

        data = response.json()
        return data.get("results", [])

    async def _upsert_github_repo(self, impl: dict):
        """Upsert a GitHub repo discovered from a paper implementation."""
        repo_url = impl.get("url") or ""
        if "github.com" not in repo_url:
            return

        # Extract owner/repo from URL
        parts = repo_url.rstrip("/").split("github.com/")
        if len(parts) < 2:
            return
        repo_full_name = parts[1].strip("/")
        if "/" not in repo_full_name:
            return
        # Take only owner/repo, drop any extra path segments
        segments = repo_full_name.split("/")
        repo_full_name = f"{segments[0]}/{segments[1]}"

        now = _utc_naive()
        async with async_session() as session:
            stmt = pg_insert(GithubRepo).values(
                repo_full_name=repo_full_name,
                name=segments[1],
                description=impl.get("description"),
                stars=impl.get("stars") or 0,
                owner_username=segments[0],
                language=impl.get("framework"),
                raw_metadata={"source": "papers_with_code", "is_official": impl.get("is_official")},
                first_scraped_at=now,
                last_scraped_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["repo_full_name"],
                set_={
                    "stars": stmt.excluded.stars,
                    "description": stmt.excluded.description,
                    "last_scraped_at": now,
                },
            )
            await session.execute(stmt)
            await session.commit()

    # ------------------------------------------------------------------
    # Trending methods
    # ------------------------------------------------------------------

    async def _scrape_trending_methods(self, client: httpx.AsyncClient, limit: int):
        """Fetch trending methods ordered by paper count."""
        self.log.info("fetching_trending_methods", limit=limit)

        url = f"{PWC_API_BASE}/methods/?ordering=-paper_count&items_per_page={limit}"

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("pwc_methods_fetch_failed", error=str(e))
            return

        data = response.json()
        methods = data.get("results", [])

        for method in methods:
            await self._process_method(method)

        self.log.info("trending_methods_done", count=len(methods))

    async def _process_method(self, method: dict):
        """Store a trending method as a news event."""
        name = (method.get("name") or "").strip()
        if not name:
            return

        description = (method.get("description") or "").strip()
        method_url = method.get("url") or ""
        if not method_url and method.get("id"):
            method_url = f"https://paperswithcode.com/method/{method['id']}"

        # Build categories from the method's collection info
        categories = []
        if method.get("collection"):
            col = method["collection"]
            if isinstance(col, dict) and col.get("name"):
                categories.append(col["name"])
            elif isinstance(col, str):
                categories.append(col)

        await self.upsert_news_event(
            source_type="pwc_trending_method",
            source_name="Papers With Code",
            title=f"Trending Method: {name}",
            body=description if description else None,
            url=method_url,
            categories=categories if categories else None,
            raw_metadata={
                "method_id": method.get("id"),
                "paper_count": method.get("paper_count"),
                "introduced_year": method.get("introduced_year"),
                "collection": method.get("collection"),
                "full_name": method.get("full_name"),
            },
        )
        self.records_fetched += 1
