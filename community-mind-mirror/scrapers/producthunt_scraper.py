"""Product Hunt scraper — uses GraphQL API to fetch launches and comments."""

from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.settings import PH_ACCESS_TOKEN
from config.sources import PH_SCRAPE_CONFIG, PH_TOPICS_TO_TRACK
from database.connection import async_session, PHLaunch
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"


class ProductHuntScraper(BaseScraper):
    """Scrapes Product Hunt launches and comments via the GraphQL API."""

    PLATFORM = "producthunt"

    def __init__(self):
        super().__init__(
            scraper_name="producthunt_scraper",
            request_delay=1.0,
        )

    # ------------------------------------------------------------------
    # Main scrape logic
    # ------------------------------------------------------------------

    async def scrape(self, **kwargs):
        """Fetch today's top launches, AI-specific launches, and comments."""
        if not PH_ACCESS_TOKEN:
            self.log.error("ph_access_token_missing")
            raise ValueError("PH_ACCESS_TOKEN is not configured")

        headers = {
            "Authorization": f"Bearer {PH_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

        vote_threshold = PH_SCRAPE_CONFIG["top_launches_vote_threshold"]
        ai_limit = PH_SCRAPE_CONFIG["ai_launches_limit"]

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Fetch today's top launches
            today_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
            self.log.info("ph_fetching_top_launches", posted_after=today_iso)
            top_launches = await self._fetch_top_launches(client, headers, today_iso)
            self.log.info("ph_top_launches_fetched", count=len(top_launches))

            # Phase 2: Fetch AI-specific launches (last 30 days)
            thirty_days_ago = (
                datetime.now(tz=timezone.utc) - timedelta(days=30)
            ).strftime("%Y-%m-%dT00:00:00Z")
            self.log.info("ph_fetching_ai_launches", posted_after=thirty_days_ago)
            ai_launches = await self._fetch_ai_launches(
                client, headers, thirty_days_ago, ai_limit
            )
            self.log.info("ph_ai_launches_fetched", count=len(ai_launches))

            # Deduplicate by ph_id
            seen_ids: set[str] = set()
            all_launches: list[dict] = []
            for launch in top_launches + ai_launches:
                ph_id = launch.get("id", "")
                if ph_id and ph_id not in seen_ids:
                    seen_ids.add(ph_id)
                    all_launches.append(launch)

            # Phase 3: Upsert launches into ph_launches
            for launch in all_launches:
                await self._upsert_launch(launch)

            # Phase 4: Fetch comments for high-vote launches
            high_vote_launches = [
                l for l in all_launches
                if (l.get("votesCount") or 0) >= vote_threshold
            ]
            self.log.info(
                "ph_fetching_comments",
                launches_with_comments=len(high_vote_launches),
                vote_threshold=vote_threshold,
            )
            for launch in high_vote_launches:
                await self._fetch_and_store_comments(client, headers, launch)
                await self.rate_limit()

        self.log.info(
            "ph_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
        )

    # ------------------------------------------------------------------
    # GraphQL helpers
    # ------------------------------------------------------------------

    async def _graphql_request(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        query: str,
        variables: dict | None = None,
    ) -> dict | None:
        """Execute a GraphQL request and return the data payload."""
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = await client.post(PH_GRAPHQL_URL, headers=headers, json=payload)
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "60"))
                self.log.warning("ph_rate_limited", retry_after=retry_after)
                import asyncio
                await asyncio.sleep(retry_after)
                return None
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            self.log.error(
                "ph_graphql_http_error",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            return None
        except httpx.HTTPError as exc:
            self.log.error("ph_graphql_request_error", error=str(exc))
            return None

        result = response.json()
        if "errors" in result:
            self.log.error("ph_graphql_errors", errors=result["errors"])
            return None

        return result.get("data")

    # ------------------------------------------------------------------
    # Fetching launches
    # ------------------------------------------------------------------

    async def _fetch_top_launches(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        posted_after: str,
    ) -> list[dict]:
        """Fetch today's top-ranked launches."""
        query = """
        query TopLaunches($postedAfter: DateTime!) {
          posts(order: RANKING, postedAfter: $postedAfter) {
            edges {
              node {
                id
                name
                tagline
                description
                votesCount
                commentsCount
                website
                createdAt
                topics {
                  edges {
                    node { name }
                  }
                }
                makers {
                  name
                  username
                }
              }
            }
          }
        }
        """
        await self.rate_limit()
        data = await self._graphql_request(
            client, headers, query, variables={"postedAfter": posted_after}
        )
        if not data:
            return []
        return self._extract_nodes(data, "posts")

    async def _fetch_ai_launches(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        posted_after: str,
        limit: int,
    ) -> list[dict]:
        """Fetch AI-specific launches from the last 30 days."""
        query = """
        query AILaunches($topic: String!, $postedAfter: DateTime!, $first: Int!) {
          posts(topic: $topic, order: VOTES, postedAfter: $postedAfter, first: $first) {
            edges {
              node {
                id
                name
                tagline
                description
                votesCount
                commentsCount
                website
                createdAt
                topics {
                  edges {
                    node { name }
                  }
                }
                makers {
                  name
                  username
                }
              }
            }
          }
        }
        """
        all_nodes: list[dict] = []
        seen_ids: set[str] = set()

        for topic in PH_TOPICS_TO_TRACK:
            await self.rate_limit()
            data = await self._graphql_request(
                client,
                headers,
                query,
                variables={
                    "topic": topic,
                    "postedAfter": posted_after,
                    "first": limit,
                },
            )
            if not data:
                continue
            for node in self._extract_nodes(data, "posts"):
                ph_id = node.get("id", "")
                if ph_id and ph_id not in seen_ids:
                    seen_ids.add(ph_id)
                    all_nodes.append(node)

        return all_nodes

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    async def _fetch_and_store_comments(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        launch: dict,
    ):
        """Fetch comments for a launch and store them as posts."""
        ph_id = launch.get("id", "")
        query = """
        query PostComments($postId: ID!) {
          post(id: $postId) {
            comments(first: 50) {
              edges {
                node {
                  id
                  body
                  createdAt
                  user {
                    name
                    username
                  }
                }
              }
            }
          }
        }
        """
        await self.rate_limit()
        data = await self._graphql_request(
            client, headers, query, variables={"postId": ph_id}
        )
        if not data or not data.get("post"):
            return

        comment_edges = (
            data.get("post", {}).get("comments", {}).get("edges", [])
        )
        launch_name = launch.get("name", "")

        for edge in comment_edges:
            node = edge.get("node", {})
            if not node:
                continue

            comment_id = node.get("id", "")
            body = node.get("body", "")
            if not body or not body.strip():
                continue

            # Upsert the comment author
            user_info = node.get("user") or {}
            username = user_info.get("username", "")
            user_id = None
            if username:
                user_id = await self.upsert_user(
                    platform_name=self.PLATFORM,
                    platform_user_id=username,
                    username=user_info.get("name") or username,
                    profile_url=f"https://www.producthunt.com/@{username}",
                )

            posted_at = None
            created_at_str = node.get("createdAt")
            if created_at_str:
                try:
                    posted_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            await self.upsert_post(
                user_id=user_id,
                platform_name=self.PLATFORM,
                post_type="comment",
                platform_post_id=f"ph_comment_{comment_id}",
                body=body,
                title=f"Comment on: {launch_name}",
                url=f"https://www.producthunt.com/posts/{ph_id}",
                posted_at=posted_at,
                raw_metadata={
                    "ph_post_id": ph_id,
                    "ph_comment_id": comment_id,
                    "launch_name": launch_name,
                },
            )

    # ------------------------------------------------------------------
    # Database upsert for ph_launches
    # ------------------------------------------------------------------

    async def _upsert_launch(self, launch: dict):
        """Upsert a launch into the ph_launches table."""
        ph_id = launch.get("id", "")
        if not ph_id:
            return

        topics = [
            edge["node"]["name"]
            for edge in launch.get("topics", {}).get("edges", [])
            if edge.get("node")
        ]
        makers = [
            {"name": m.get("name", ""), "username": m.get("username", "")}
            for m in launch.get("makers") or []
        ]

        launched_at = None
        created_at_str = launch.get("createdAt")
        if created_at_str:
            try:
                launched_at = _utc_naive(
                    datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                )
            except ValueError:
                pass

        values = {
            "ph_id": ph_id,
            "name": launch.get("name", ""),
            "tagline": launch.get("tagline"),
            "description": launch.get("description"),
            "votes_count": launch.get("votesCount", 0),
            "comments_count": launch.get("commentsCount", 0),
            "website": launch.get("website"),
            "topics": topics,
            "makers": makers,
            "launched_at": launched_at,
            "raw_metadata": {
                "ph_id": ph_id,
                "source": "graphql_api",
            },
        }

        async with async_session() as session:
            stmt = pg_insert(PHLaunch).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ph_id"],
                set_={
                    "name": stmt.excluded.name,
                    "tagline": stmt.excluded.tagline,
                    "description": stmt.excluded.description,
                    "votes_count": stmt.excluded.votes_count,
                    "comments_count": stmt.excluded.comments_count,
                    "website": stmt.excluded.website,
                    "topics": stmt.excluded.topics,
                    "makers": stmt.excluded.makers,
                    "launched_at": stmt.excluded.launched_at,
                    "raw_metadata": stmt.excluded.raw_metadata,
                },
            )
            await session.execute(stmt)
            await session.commit()

        self.records_fetched += 1
        self.log.debug("ph_launch_upserted", ph_id=ph_id, name=launch.get("name"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_nodes(data: dict, field: str) -> list[dict]:
        """Extract nodes from a GraphQL connection response."""
        edges = data.get(field, {}).get("edges", [])
        return [edge["node"] for edge in edges if edge.get("node")]
