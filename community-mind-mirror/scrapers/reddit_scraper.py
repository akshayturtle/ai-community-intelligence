"""Reddit scraper — uses RSS feeds (JSON API is blocked on AWS IPs).

Fetches posts via RSS (top/hot/new) + individual post comment feeds.
RSS returns ~25 items per feed, so we query multiple sorts to maximize coverage.
Comments are fetched per-post via the post's RSS comment feed.
"""

import asyncio
import re
from datetime import datetime, timezone
from html import unescape

import feedparser
import httpx
import structlog

from config.settings import REDDIT_REQUEST_DELAY
from config.sources import REDDIT_SUBREDDITS, REDDIT_SCRAPE_CONFIG, GIG_SUBREDDITS, GIG_SEARCH_TERMS, GIG_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

REDDIT_BASE = "https://www.reddit.com"

# Browser-like UA (required for Reddit RSS on AWS)
REDDIT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

POST_ID_RE = re.compile(r"/comments/([a-z0-9]+)/")
AUTHOR_RE = re.compile(r"/u(?:ser)?/([^/\s]+)")
SCORE_RE = re.compile(r"\[score[:\s]+(\d+)\]", re.IGNORECASE)


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_rss_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        import email.utils
        parsed = email.utils.parsedate_to_datetime(date_str)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        pass
    try:
        struct = feedparser._parse_date(date_str)
        if struct:
            return datetime(*struct[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None


class RedditScraper(BaseScraper):
    """Scrapes Reddit using RSS feeds (works from AWS/cloud IPs)."""

    PLATFORM = "reddit"

    def __init__(self):
        super().__init__(
            scraper_name="reddit_scraper",
            request_delay=REDDIT_REQUEST_DELAY,
        )

    async def scrape(self, subreddits: list[str] | None = None, **kwargs):
        targets = subreddits or REDDIT_SUBREDDITS
        # Also include gig subreddits (deduplicated)
        all_targets = list(dict.fromkeys(targets + GIG_SUBREDDITS))
        cfg = REDDIT_SCRAPE_CONFIG
        sorts = cfg.get("sort_modes", ["top", "hot", "new"])
        time_filter = cfg.get("time_filter", "month")
        comments_per = cfg.get("comments_per_post", 200)

        self.log.info(
            "reddit_scrape_start",
            subreddits=len(all_targets),
            sorts=sorts,
        )

        headers = {"User-Agent": REDDIT_UA}

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=headers,
        ) as client:
            for subreddit in all_targets:
                await self._scrape_subreddit(
                    client, subreddit, sorts, time_filter, comments_per,
                )

            # Search for AI gig/hiring posts
            await self._search_gig_terms(client)

        self.log.info(
            "reddit_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    # ------------------------------------------------------------------
    # Subreddit scraping (multiple RSS sorts + per-post comments)
    # ------------------------------------------------------------------

    async def _scrape_subreddit(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
        sorts: list[str],
        time_filter: str,
        comments_per: int,
    ):
        self.log.info("scraping_subreddit", subreddit=subreddit)
        seen_ids: set[str] = set()
        post_ids_for_comments: list[tuple[str, str]] = []  # (post_id, subreddit)
        discovered_users: set[str] = set()

        # Fetch posts from multiple sort modes
        for sort in sorts:
            url = f"{REDDIT_BASE}/r/{subreddit}/{sort}/.rss?limit=100"
            if sort == "top":
                url += f"&t={time_filter}"

            try:
                resp = await self.fetch_url(client, url)
                await self.rate_limit()
            except Exception as e:
                self.log.warning(
                    "rss_fetch_failed",
                    subreddit=subreddit, sort=sort, error=str(e),
                )
                continue

            feed = feedparser.parse(resp.text)

            for entry in feed.entries:
                post_id = self._extract_post_id(entry)
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)

                author = self._extract_author(entry)
                if author:
                    discovered_users.add(author)

                body = strip_html(
                    entry.get("summary", "")
                    or entry.get("content", [{}])[0].get("value", "")
                )
                title = entry.get("title", "")
                if not body and title:
                    body = title

                posted_at = parse_rss_date(
                    entry.get("published") or entry.get("updated")
                )

                # Upsert user
                user_id = None
                if author:
                    user_id = await self.upsert_user(
                        platform_name=self.PLATFORM,
                        platform_user_id=author,
                        username=author,
                        profile_url=f"https://www.reddit.com/user/{author}",
                    )

                link = entry.get("link", "")
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
                        "feed_id": entry.get("id", ""),
                        "sort": sort,
                    },
                )

                post_ids_for_comments.append((post_id, subreddit))

        self.log.info(
            "subreddit_posts_fetched",
            subreddit=subreddit,
            unique_posts=len(seen_ids),
        )

        # Fetch subreddit-level comments feed (catches recent comments across all posts)
        await self._fetch_subreddit_comments(client, subreddit, discovered_users)

        # Fetch per-post comment feeds for top posts
        max_comment_posts = REDDIT_SCRAPE_CONFIG.get("max_comment_posts_per_sub", 20)
        for post_id, sr in post_ids_for_comments[:max_comment_posts]:
            await self._fetch_post_comments(client, sr, post_id, discovered_users)

        # Scrape discovered user activity
        max_users = REDDIT_SCRAPE_CONFIG.get("max_users_per_subreddit", 50)
        for username in list(discovered_users)[:max_users]:
            if await self.was_recently_scraped(self.PLATFORM, username, hours=48):
                continue
            await self._scrape_user(client, username)

        self.log.info(
            "subreddit_done",
            subreddit=subreddit,
            posts=len(seen_ids),
            users_discovered=len(discovered_users),
        )

    # ------------------------------------------------------------------
    # Comment fetching
    # ------------------------------------------------------------------

    async def _fetch_subreddit_comments(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
        discovered_users: set[str],
    ):
        """Fetch the subreddit's recent comments feed."""
        url = f"{REDDIT_BASE}/r/{subreddit}/comments/.rss?limit=100"
        try:
            resp = await self.fetch_url(client, url)
            await self.rate_limit()
        except Exception as e:
            self.log.warning("sub_comments_fetch_failed", subreddit=subreddit, error=str(e))
            return

        feed = feedparser.parse(resp.text)
        await self._process_comment_feed(feed, subreddit, discovered_users)

    async def _fetch_post_comments(
        self,
        client: httpx.AsyncClient,
        subreddit: str,
        post_id: str,
        discovered_users: set[str],
    ):
        """Fetch comments for a specific post via its RSS feed."""
        url = f"{REDDIT_BASE}/r/{subreddit}/comments/{post_id}/.rss?limit=200"
        try:
            resp = await self.fetch_url(client, url)
            await self.rate_limit()
        except Exception as e:
            self.log.debug("post_comments_fetch_failed", post_id=post_id, error=str(e))
            return

        feed = feedparser.parse(resp.text)
        await self._process_comment_feed(feed, subreddit, discovered_users)

    async def _process_comment_feed(
        self,
        feed,
        subreddit: str,
        discovered_users: set[str],
    ):
        """Process comment entries from an RSS feed."""
        for entry in feed.entries:
            author = self._extract_author(entry)
            if author:
                discovered_users.add(author)

            body = strip_html(
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
            if not body:
                continue

            comment_id = entry.get("id", "")
            posted_at = parse_rss_date(
                entry.get("published") or entry.get("updated")
            )

            user_id = None
            if author:
                user_id = await self.upsert_user(
                    platform_name=self.PLATFORM,
                    platform_user_id=author,
                    username=author,
                    profile_url=f"https://www.reddit.com/user/{author}",
                )

            # Extract parent post ID from comment link
            link = entry.get("link", "")
            parent_post_id_match = POST_ID_RE.search(link)
            parent_meta = {}
            if parent_post_id_match:
                parent_meta["parent_post_id"] = parent_post_id_match.group(1)

            await self.upsert_post(
                user_id=user_id,
                platform_name=self.PLATFORM,
                post_type="comment",
                platform_post_id=f"reddit_comment_{comment_id}",
                body=body,
                url=link,
                subreddit=subreddit,
                posted_at=posted_at,
                raw_metadata=parent_meta,
            )

    # ------------------------------------------------------------------
    # User activity scraping
    # ------------------------------------------------------------------

    async def _scrape_user(self, client: httpx.AsyncClient, username: str):
        """Scrape a user's recent posts and comments via RSS."""
        self.log.debug("scraping_user", username=username)

        # User overview feed
        user_url = f"{REDDIT_BASE}/user/{username}/.rss?limit=100"
        try:
            resp = await self.fetch_url(client, user_url)
            await self.rate_limit()
        except Exception as e:
            self.log.debug("user_fetch_failed", username=username, error=str(e))
            return

        user_id = await self.upsert_user(
            platform_name=self.PLATFORM,
            platform_user_id=username,
            username=username,
            profile_url=f"https://www.reddit.com/user/{username}",
        )

        feed = feedparser.parse(resp.text)
        for entry in feed.entries:
            body = strip_html(
                entry.get("summary", "")
                or entry.get("content", [{}])[0].get("value", "")
            )
            title = entry.get("title", "")
            if not body and title:
                body = title
            if not body:
                continue

            entry_id = entry.get("id", "")
            post_id = self._extract_post_id(entry)
            link = entry.get("link", "")
            is_comment = "/comments/" in link and link.count("/") > 6
            post_type = "comment" if is_comment else "submission"

            subreddit = None
            sr_match = re.search(r"/r/([^/]+)/", link)
            if sr_match:
                subreddit = sr_match.group(1)

            platform_post_id = (
                f"reddit_{post_id}" if post_id and not is_comment
                else f"reddit_comment_{entry_id}"
            )

            posted_at = parse_rss_date(
                entry.get("published") or entry.get("updated")
            )

            await self.upsert_post(
                user_id=user_id,
                platform_name=self.PLATFORM,
                post_type=post_type,
                platform_post_id=platform_post_id,
                title=title if post_type == "submission" else None,
                body=body,
                url=link,
                subreddit=subreddit,
                posted_at=posted_at,
            )

        # Also fetch comments-only feed
        comments_url = f"{REDDIT_BASE}/user/{username}/comments/.rss?limit=100"
        try:
            resp = await self.fetch_url(client, comments_url)
            await self.rate_limit()

            comment_feed = feedparser.parse(resp.text)
            for entry in comment_feed.entries:
                body = strip_html(
                    entry.get("summary", "")
                    or entry.get("content", [{}])[0].get("value", "")
                )
                if not body:
                    continue

                entry_id = entry.get("id", "")
                link = entry.get("link", "")
                subreddit = None
                sr_match = re.search(r"/r/([^/]+)/", link)
                if sr_match:
                    subreddit = sr_match.group(1)

                posted_at = parse_rss_date(
                    entry.get("published") or entry.get("updated")
                )

                await self.upsert_post(
                    user_id=user_id,
                    platform_name=self.PLATFORM,
                    post_type="comment",
                    platform_post_id=f"reddit_comment_{entry_id}",
                    body=body,
                    url=link,
                    subreddit=subreddit,
                    posted_at=posted_at,
                )
        except Exception as e:
            self.log.debug("user_comments_fetch_failed", username=username, error=str(e))

    # ------------------------------------------------------------------
    # Gig / hiring post search
    # ------------------------------------------------------------------

    async def _search_gig_terms(self, client: httpx.AsyncClient):
        """Search Reddit for AI gig/hiring posts using configured search terms."""
        from urllib.parse import quote

        cfg = GIG_SCRAPE_CONFIG
        sort = cfg.get("search_sort", "new")
        time_filter = cfg.get("search_time_filter", "month")
        limit = cfg.get("search_limit", 100)
        delay = cfg.get("request_delay", 3.0)

        self.log.info("gig_search_start", terms=len(GIG_SEARCH_TERMS))

        # Subreddits that are relevant for gig/hiring posts — skip noise from unrelated subs
        relevant_subs = {
            "forhire", "remotejobs", "freelance", "machinelearningjobs",
            "jobbit", "hireadev", "startups", "saas", "entrepreneur",
            "indiehackers", "freelance_forhire", "remotework", "workonline",
            "slavelabour", "softwareengineerJobs", "webdev", "cscareerquestions",
            "sideproject", "buildinpublic", "cofounderhunt", "jobnetworking",
            "developers", "developersIndia", "aidevelopernews", "aiautomations",
            "machinelearningjobs", "ai_agents", "mlops", "hireahuman",
            "freelanceprogramming", "gamedevclassifieds", "hungryartists",
            "artcommissions", "samplesize", "indiajobs", "nocode",
            "webdevjobs", "dataengineering", "datascience",
        }
        relevant_subs_lower = {s.lower() for s in relevant_subs}

        for term in GIG_SEARCH_TERMS:
            # Wrap in quotes for exact phrase matching
            exact_term = f'"{term}"'
            encoded = quote(exact_term)
            url = f"{REDDIT_BASE}/search/.rss?q={encoded}&sort={sort}&t={time_filter}&limit={limit}"

            try:
                resp = await self.fetch_url(client, url)
                # Use slower rate limit for search
                await asyncio.sleep(delay)
            except Exception as e:
                self.log.warning("gig_search_failed", term=term, error=str(e))
                continue

            feed = feedparser.parse(resp.text)
            count = 0

            for entry in feed.entries:
                post_id = self._extract_post_id(entry)
                if not post_id:
                    continue

                # Extract subreddit early to filter irrelevant subs
                link = entry.get("link", "")
                subreddit = None
                sr_match = re.search(r"/r/([^/]+)/", link)
                if sr_match:
                    subreddit = sr_match.group(1)

                # Skip posts from irrelevant subreddits
                if subreddit and subreddit.lower() not in relevant_subs_lower:
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
                        "source": "gig_search",
                        "search_query": term,
                        "sort": sort,
                    },
                )
                count += 1

            if count > 0:
                self.log.debug("gig_search_results", term=term, posts=count)

        self.log.info("gig_search_complete")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
