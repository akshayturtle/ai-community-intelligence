"""GitHub scraper — discovers trending AI/ML repos, tracks watchlist, computes star velocity."""

from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.settings import GITHUB_TOKEN
from config.sources import (
    GITHUB_SCRAPE_CONFIG,
    GITHUB_SEARCH_QUERIES,
    GITHUB_WATCHLIST_REPOS,
)
from database.connection import GithubRepo, async_session
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


def _parse_gh_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the GitHub API into a naive UTC datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _utc_naive(dt)
    except (ValueError, TypeError):
        return None


class GitHubScraper(BaseScraper):
    """Scrapes GitHub for trending AI/ML repositories and tracks a watchlist."""

    def __init__(self):
        super().__init__(
            scraper_name="github_scraper",
            request_delay=GITHUB_SCRAPE_CONFIG.get("request_delay", 1.0),
        )
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if GITHUB_TOKEN:
            self._headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    async def scrape(self, **kwargs):
        """Run full GitHub scrape: search queries + watchlist repos."""
        self.log.info("github_scrape_start")

        seen_repos: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Search for trending repos per query
            for query in GITHUB_SEARCH_QUERIES:
                repos = await self._search_repos(client, query)
                for repo_data in repos:
                    full_name = repo_data.get("full_name", "")
                    if full_name in seen_repos:
                        continue
                    seen_repos.add(full_name)
                    await self._process_repo(client, repo_data)

            # Phase 2: Track watchlist repos
            for repo_full_name in GITHUB_WATCHLIST_REPOS:
                if repo_full_name in seen_repos:
                    continue
                seen_repos.add(repo_full_name)
                repo_data = await self._fetch_repo(client, repo_full_name)
                if repo_data:
                    await self._process_repo(client, repo_data)

        self.log.info(
            "github_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
            repos_seen=len(seen_repos),
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def _search_repos(
        self, client: httpx.AsyncClient, query: str
    ) -> list[dict]:
        """Search GitHub for repos matching *query* created in the last 90 days."""
        cutoff = (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d")
        per_page = GITHUB_SCRAPE_CONFIG.get("results_per_query", 100)

        url = (
            f"{GITHUB_API_BASE}/search/repositories"
            f"?q={query}+created:>{cutoff}"
            f"&sort=stars&order=desc&per_page={per_page}"
        )

        self.log.info("github_search", query=query, cutoff=cutoff)

        try:
            response = await self.fetch_url(client, url, headers=self._headers)
            data = response.json()
            items = data.get("items", [])
            self.log.info("github_search_results", query=query, count=len(items))
            return items
        except Exception as e:
            self.log.warning("github_search_failed", query=query, error=str(e))
            return []

    # ------------------------------------------------------------------
    # Single repo fetch
    # ------------------------------------------------------------------

    async def _fetch_repo(
        self, client: httpx.AsyncClient, repo_full_name: str
    ) -> dict | None:
        """Fetch metadata for a single repo by full name (owner/repo)."""
        url = f"{GITHUB_API_BASE}/repos/{repo_full_name}"
        try:
            response = await self.fetch_url(client, url, headers=self._headers)
            await self.rate_limit()
            return response.json()
        except Exception as e:
            self.log.warning("repo_fetch_failed", repo=repo_full_name, error=str(e))
            return None

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def _process_repo(
        self, client: httpx.AsyncClient, repo_data: dict
    ) -> None:
        """Enrich a repo with contributor + star velocity data and upsert to DB."""
        full_name = repo_data.get("full_name", "")
        owner = repo_data.get("owner", {}).get("login", "")
        name = repo_data.get("name", "")

        self.log.debug("processing_repo", repo=full_name)

        # Fetch contributor stats
        contributor_count, non_founder = await self._fetch_contributor_stats(
            client, full_name, owner
        )

        # Compute star velocity (stars/week over last 4 weeks)
        star_velocity = await self._compute_star_velocity(client, full_name)

        # Upsert
        await self._upsert_repo(
            repo_data=repo_data,
            contributor_count=contributor_count,
            non_founder_contributors=non_founder,
            star_velocity=star_velocity,
        )

        self.records_fetched += 1

    # ------------------------------------------------------------------
    # Contributors
    # ------------------------------------------------------------------

    async def _fetch_contributor_stats(
        self,
        client: httpx.AsyncClient,
        repo_full_name: str,
        owner_username: str,
    ) -> tuple[int, int]:
        """Return (total_contributor_count, non_founder_contributor_count)."""
        url = f"{GITHUB_API_BASE}/repos/{repo_full_name}/contributors?per_page=100"
        try:
            response = await self.fetch_url(client, url, headers=self._headers)
            await self.rate_limit()
            contributors = response.json()

            if not isinstance(contributors, list):
                return 0, 0

            total = len(contributors)
            non_founder = sum(
                1 for c in contributors
                if c.get("login", "").lower() != owner_username.lower()
            )
            return total, non_founder
        except Exception as e:
            self.log.debug(
                "contributors_fetch_failed", repo=repo_full_name, error=str(e)
            )
            return 0, 0

    # ------------------------------------------------------------------
    # Star velocity
    # ------------------------------------------------------------------

    async def _compute_star_velocity(
        self, client: httpx.AsyncClient, repo_full_name: str
    ) -> float | None:
        """Compute stars/week over the last 4 weeks using the stargazers timeline API."""
        url = (
            f"{GITHUB_API_BASE}/repos/{repo_full_name}"
            f"/stargazers?per_page=100&page=1"
        )
        headers = {
            **self._headers,
            "Accept": "application/vnd.github.v3.star+json",
        }

        four_weeks_ago = datetime.now(tz=timezone.utc) - timedelta(weeks=4)

        try:
            response = await self.fetch_url(client, url, headers=headers)
            await self.rate_limit()
            stargazers = response.json()

            if not isinstance(stargazers, list):
                return None

            recent_stars = 0
            for sg in stargazers:
                starred_at_str = sg.get("starred_at")
                if not starred_at_str:
                    continue
                try:
                    starred_at = datetime.fromisoformat(
                        starred_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    continue
                if starred_at >= four_weeks_ago:
                    recent_stars += 1

            # stars per week over the 4-week window
            velocity = recent_stars / 4.0
            return round(velocity, 2)
        except Exception as e:
            self.log.debug(
                "star_velocity_failed", repo=repo_full_name, error=str(e)
            )
            return None

    # ------------------------------------------------------------------
    # Database upsert
    # ------------------------------------------------------------------

    async def _upsert_repo(
        self,
        repo_data: dict,
        contributor_count: int,
        non_founder_contributors: int,
        star_velocity: float | None,
    ) -> None:
        """Insert or update a github_repos row (ON CONFLICT on repo_full_name)."""
        full_name = repo_data.get("full_name", "")
        license_info = repo_data.get("license") or {}
        now = _utc_naive()

        values = {
            "repo_full_name": full_name,
            "name": repo_data.get("name"),
            "description": repo_data.get("description"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "language": repo_data.get("language"),
            "topics": repo_data.get("topics", []),
            "owner_username": repo_data.get("owner", {}).get("login"),
            "open_issues": repo_data.get("open_issues_count", 0),
            "created_at": _parse_gh_datetime(repo_data.get("created_at")),
            "updated_at": _parse_gh_datetime(repo_data.get("updated_at")),
            "pushed_at": _parse_gh_datetime(repo_data.get("pushed_at")),
            "star_velocity": star_velocity,
            "contributor_count": contributor_count,
            "non_founder_contributors": non_founder_contributors,
            "homepage_url": repo_data.get("homepage"),
            "license": license_info.get("spdx_id") if isinstance(license_info, dict) else None,
            "raw_metadata": {
                "html_url": repo_data.get("html_url"),
                "default_branch": repo_data.get("default_branch"),
                "archived": repo_data.get("archived", False),
                "disabled": repo_data.get("disabled", False),
                "size_kb": repo_data.get("size", 0),
            },
            "last_scraped_at": now,
        }

        update_values = {k: v for k, v in values.items() if k != "repo_full_name"}
        # Don't overwrite first_scraped_at on update
        update_values.pop("first_scraped_at", None)

        async with async_session() as session:
            stmt = pg_insert(GithubRepo).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["repo_full_name"],
                set_=update_values,
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                # Determine new vs. updated based on whether first_scraped_at was just set
                # A simple heuristic: count it as new if we haven't seen it before
                self.records_new += 1
                self.records_updated += 1
