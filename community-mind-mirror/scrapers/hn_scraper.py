"""Hacker News scraper — uses free Firebase API + Algolia search. No API key needed."""

import re
from datetime import datetime, timezone

import httpx
import structlog

from config.settings import HN_REQUEST_DELAY
from config.sources import HN_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

HN_FIREBASE_BASE = "https://hacker-news.firebaseio.com/v0"
HN_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"


class HNScraper(BaseScraper):
    """Scrapes Hacker News using Firebase API and Algolia search."""

    PLATFORM = "hackernews"

    def __init__(self):
        super().__init__(
            scraper_name="hn_scraper",
            request_delay=HN_REQUEST_DELAY,
        )

    async def scrape(
        self,
        max_stories: int | None = None,
        story_types: list[str] | None = None,
        **kwargs,
    ):
        """Scrape HN stories, comments, and user profiles."""
        types = story_types or HN_SCRAPE_CONFIG["story_types"]
        limit = max_stories or HN_SCRAPE_CONFIG["stories_to_fetch"]
        keywords = HN_SCRAPE_CONFIG["keyword_filter"]

        self.log.info("hn_scrape_start", story_types=types, limit=limit)

        discovered_users: set[str] = set()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Fetch story IDs from Firebase
            all_story_ids: set[int] = set()
            for story_type in types:
                ids = await self._fetch_story_ids(client, story_type, limit)
                all_story_ids.update(ids)
                self.log.info("fetched_story_ids", type=story_type, count=len(ids))

            # Phase 2: Fetch and filter stories by keyword
            matching_stories = []
            for story_id in list(all_story_ids)[:limit]:
                item = await self._fetch_item(client, story_id)
                if item and self._matches_keywords(item, keywords):
                    matching_stories.append(item)
                await self.rate_limit()

            self.log.info("keyword_filtered_stories", count=len(matching_stories))

            # Phase 3: Algolia keyword search for additional stories
            algolia_stories = await self._algolia_search_stories(client, keywords)
            self.log.info("algolia_stories_found", count=len(algolia_stories))

            # Phase 4: Process all matching stories
            for item in matching_stories:
                users = await self._process_story(client, item)
                discovered_users.update(users)

            # Process Algolia results
            for hit in algolia_stories:
                users = await self._process_algolia_hit(client, hit)
                discovered_users.update(users)

            # Phase 5: Fetch user profiles
            self.log.info("fetching_user_profiles", count=len(discovered_users))
            for username in discovered_users:
                if await self.was_recently_scraped(self.PLATFORM, username, hours=24):
                    continue
                await self._scrape_user(client, username)

        self.log.info(
            "hn_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            users=len(discovered_users),
        )

    # ------------------------------------------------------------------
    # Firebase API methods
    # ------------------------------------------------------------------

    async def _fetch_story_ids(
        self, client: httpx.AsyncClient, story_type: str, limit: int
    ) -> list[int]:
        """Fetch story IDs from Firebase (topstories, beststories, etc.)."""
        url = f"{HN_FIREBASE_BASE}/{story_type}.json"
        try:
            response = await self.fetch_url(client, url)
            ids = response.json()
            return ids[:limit] if isinstance(ids, list) else []
        except Exception as e:
            self.log.warning("story_ids_fetch_failed", type=story_type, error=str(e))
            return []

    async def _fetch_item(
        self, client: httpx.AsyncClient, item_id: int
    ) -> dict | None:
        """Fetch a single item (story/comment) from Firebase."""
        url = f"{HN_FIREBASE_BASE}/item/{item_id}.json"
        try:
            response = await self.fetch_url(client, url)
            data = response.json()
            return data if data else None
        except Exception as e:
            self.log.debug("item_fetch_failed", item_id=item_id, error=str(e))
            return None

    async def _fetch_user_profile(
        self, client: httpx.AsyncClient, username: str
    ) -> dict | None:
        """Fetch user profile from Firebase."""
        url = f"{HN_FIREBASE_BASE}/user/{username}.json"
        try:
            response = await self.fetch_url(client, url)
            data = response.json()
            return data if data else None
        except Exception as e:
            self.log.debug("user_profile_fetch_failed", username=username, error=str(e))
            return None

    # ------------------------------------------------------------------
    # Algolia search
    # ------------------------------------------------------------------

    async def _algolia_search_stories(
        self, client: httpx.AsyncClient, keywords: list[str]
    ) -> list[dict]:
        """Search HN via Algolia for keyword-matching stories."""
        all_hits: list[dict] = []
        seen_ids: set[str] = set()

        # Build a few search queries from keywords
        search_queries = [
            "AI agents",
            "LLM startup",
            "machine learning",
            "robotics autonomous",
            "open source AI",
        ]

        for query in search_queries:
            url = f"{HN_ALGOLIA_BASE}/search?query={query}&tags=story&hitsPerPage=50"
            try:
                response = await self.fetch_url(client, url)
                data = response.json()
                for hit in data.get("hits", []):
                    obj_id = hit.get("objectID", "")
                    if obj_id not in seen_ids:
                        seen_ids.add(obj_id)
                        all_hits.append(hit)
            except Exception as e:
                self.log.warning("algolia_search_failed", query=query, error=str(e))

        return all_hits

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    async def _process_story(
        self, client: httpx.AsyncClient, item: dict
    ) -> set[str]:
        """Process a Firebase story item: save it and its comments. Returns discovered usernames."""
        discovered_users: set[str] = set()

        author = item.get("by", "")
        if author:
            discovered_users.add(author)

        # Save story author
        user_id = None
        if author:
            user_id = await self.upsert_user(
                platform_name=self.PLATFORM,
                platform_user_id=author,
                username=author,
                profile_url=f"https://news.ycombinator.com/user?id={author}",
            )

        # Save story as a post
        story_id = str(item.get("id", ""))
        title = item.get("title", "")
        text = item.get("text", "") or ""
        body = text if text else title
        score = item.get("score", 0)
        num_comments = item.get("descendants", 0)
        posted_at = None
        if item.get("time"):
            posted_at = datetime.fromtimestamp(item["time"], tz=timezone.utc)

        story_url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")

        await self.upsert_post(
            user_id=user_id,
            platform_name=self.PLATFORM,
            post_type="submission",
            platform_post_id=f"hn_{story_id}",
            title=title,
            body=body,
            url=story_url,
            score=score,
            num_comments=num_comments,
            posted_at=posted_at,
            raw_metadata={
                "hn_id": story_id,
                "type": item.get("type", "story"),
            },
        )

        # Fetch comments (up to configured limit)
        kids = item.get("kids", [])
        max_comments = HN_SCRAPE_CONFIG["comments_per_story"]
        comment_users = await self._fetch_comments_recursive(
            client, kids[:max_comments], depth=0, max_depth=3
        )
        discovered_users.update(comment_users)

        return discovered_users

    async def _fetch_comments_recursive(
        self,
        client: httpx.AsyncClient,
        kid_ids: list[int],
        depth: int = 0,
        max_depth: int = 3,
    ) -> set[str]:
        """Recursively fetch comments from kid IDs. Returns usernames."""
        if depth > max_depth or not kid_ids:
            return set()

        discovered_users: set[str] = set()

        for kid_id in kid_ids:
            item = await self._fetch_item(client, kid_id)
            await self.rate_limit()

            if not item or item.get("deleted") or item.get("dead"):
                continue

            author = item.get("by", "")
            if author:
                discovered_users.add(author)

            text = item.get("text", "")
            if not text:
                continue

            # Strip HTML from comment text
            text = re.sub(r"<[^>]+>", " ", text).strip()

            user_id = None
            if author:
                user_id = await self.upsert_user(
                    platform_name=self.PLATFORM,
                    platform_user_id=author,
                    username=author,
                    profile_url=f"https://news.ycombinator.com/user?id={author}",
                )

            comment_id = str(item.get("id", ""))
            posted_at = None
            if item.get("time"):
                posted_at = datetime.fromtimestamp(item["time"], tz=timezone.utc)

            await self.upsert_post(
                user_id=user_id,
                platform_name=self.PLATFORM,
                post_type="comment",
                platform_post_id=f"hn_{comment_id}",
                body=text,
                url=f"https://news.ycombinator.com/item?id={comment_id}",
                posted_at=posted_at,
                raw_metadata={
                    "hn_id": comment_id,
                    "parent_hn_id": str(item.get("parent", "")),
                },
            )

            # Recurse into replies
            sub_kids = item.get("kids", [])
            if sub_kids:
                sub_users = await self._fetch_comments_recursive(
                    client, sub_kids[:20], depth=depth + 1, max_depth=max_depth
                )
                discovered_users.update(sub_users)

        return discovered_users

    async def _process_algolia_hit(
        self, client: httpx.AsyncClient, hit: dict
    ) -> set[str]:
        """Process an Algolia search result."""
        discovered_users: set[str] = set()

        author = hit.get("author", "")
        if author:
            discovered_users.add(author)

        user_id = None
        if author:
            user_id = await self.upsert_user(
                platform_name=self.PLATFORM,
                platform_user_id=author,
                username=author,
                profile_url=f"https://news.ycombinator.com/user?id={author}",
            )

        obj_id = hit.get("objectID", "")
        title = hit.get("title", "")
        body = hit.get("story_text", "") or title
        score = hit.get("points", 0)
        num_comments = hit.get("num_comments", 0)

        posted_at = None
        created_at_str = hit.get("created_at")
        if created_at_str:
            try:
                posted_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"

        await self.upsert_post(
            user_id=user_id,
            platform_name=self.PLATFORM,
            post_type="submission",
            platform_post_id=f"hn_{obj_id}",
            title=title,
            body=body,
            url=story_url,
            score=score,
            num_comments=num_comments,
            posted_at=posted_at,
            raw_metadata={
                "hn_id": obj_id,
                "source": "algolia",
                "tags": hit.get("_tags", []),
            },
        )

        return discovered_users

    async def _scrape_user(self, client: httpx.AsyncClient, username: str):
        """Fetch a user's profile and their recent submissions via Algolia."""
        self.log.debug("scraping_hn_user", username=username)

        # Fetch profile from Firebase
        profile = await self._fetch_user_profile(client, username)
        await self.rate_limit()

        karma = None
        bio = None
        account_created = None

        if profile:
            karma = profile.get("karma")
            bio = profile.get("about", "")
            if bio:
                bio = re.sub(r"<[^>]+>", " ", bio).strip()
            if profile.get("created"):
                account_created = datetime.fromtimestamp(
                    profile["created"], tz=timezone.utc
                )

        user_id = await self.upsert_user(
            platform_name=self.PLATFORM,
            platform_user_id=username,
            username=username,
            bio=bio,
            profile_url=f"https://news.ycombinator.com/user?id={username}",
            karma_score=karma,
            account_created_at=account_created,
        )

        # Fetch user's recent items via Algolia (much faster than Firebase submitted array)
        url = f"{HN_ALGOLIA_BASE}/search?tags=author_{username}&hitsPerPage=50"
        try:
            response = await self.fetch_url(client, url)
            data = response.json()

            for hit in data.get("hits", []):
                obj_id = hit.get("objectID", "")
                title = hit.get("title", "")
                text = hit.get("story_text", "") or hit.get("comment_text", "") or ""
                if not text and title:
                    text = title
                if not text:
                    continue

                text = re.sub(r"<[^>]+>", " ", text).strip()

                is_comment = not title
                post_type = "comment" if is_comment else "submission"

                posted_at = None
                created_at_str = hit.get("created_at")
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
                    post_type=post_type,
                    platform_post_id=f"hn_{obj_id}",
                    title=title if post_type == "submission" else None,
                    body=text,
                    url=hit.get("url", f"https://news.ycombinator.com/item?id={obj_id}"),
                    score=hit.get("points", 0) or 0,
                    num_comments=hit.get("num_comments", 0) or 0,
                    posted_at=posted_at,
                    raw_metadata={
                        "hn_id": obj_id,
                        "source": "algolia_user",
                    },
                )
        except Exception as e:
            self.log.debug("user_algolia_fetch_failed", username=username, error=str(e))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _matches_keywords(self, item: dict, keywords: list[str]) -> bool:
        """Check if a story matches any keyword."""
        title = (item.get("title") or "").lower()
        text = (item.get("text") or "").lower()
        url = (item.get("url") or "").lower()
        combined = f"{title} {text} {url}"

        for keyword in keywords:
            if keyword.lower() in combined:
                return True
        return False
