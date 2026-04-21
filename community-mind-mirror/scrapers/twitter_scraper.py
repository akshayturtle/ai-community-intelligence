"""X.com (Twitter) scraper — Nitter instance scraping (no API key needed).

Uses public Nitter mirrors (privacy-friendly Twitter frontends that render
plain HTML). Falls back through multiple instances automatically.

No API credentials required. Set TWITTER_BEARER_TOKEN env var to use the
official Twitter API v2 instead (preferred if available).
"""

import asyncio
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.proxy import random_headers

logger = structlog.get_logger()

# Nitter instances — tried in order, first working one is used
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.mint.lgbt",
    "https://nitter.cz",
]

SEARCH_QUERIES = [
    # Freelance/hiring signals
    "looking for AI engineer freelance",
    "need Python developer DM",
    "hiring AI developer remote",
    # Product launches
    "#buildinpublic AI agent",
    "just launched AI tool",
    "shipped AI feature",
    # Market intelligence
    "AI automation tool",
    "LLM wrapper launch",
    "#indiehacker AI",
    # Tech trends
    "RAG system production",
    "fine tuning results",
    "GPT-4 vs Claude comparison",
]

# Official API v2 search endpoint
TWITTER_V2_URL = "https://api.twitter.com/2/tweets/search/recent"


class TwitterScraper(BaseScraper):
    """
    Scrapes X.com for AI/tech/freelance signals.
    Primary: official Twitter API v2 (requires TWITTER_BEARER_TOKEN env var)
    Fallback: Nitter public instances (no credentials needed)
    """

    def __init__(self):
        super().__init__(scraper_name="twitter_scraper", request_delay=2.0)
        self._bearer: str = os.getenv("TWITTER_BEARER_TOKEN", "")
        self._nitter_base: str = ""

    async def scrape(self, **kwargs):
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False,
        ) as client:
            if self._bearer:
                # Use official v2 API
                await self._scrape_v2(client, seen_ids)
            else:
                # Find a working Nitter instance then scrape
                self._nitter_base = await self._find_nitter(client)
                if not self._nitter_base:
                    self.log.warning(
                        "twitter_no_source",
                        hint=(
                            "All Nitter instances unreachable and no TWITTER_BEARER_TOKEN set. "
                            "Add TWITTER_BEARER_TOKEN to app settings for reliable scraping."
                        ),
                    )
                    return
                await self._scrape_nitter(client, seen_ids)

    # ── Official v2 API ──────────────────────────────────────────────────────

    async def _scrape_v2(self, client: httpx.AsyncClient, seen_ids: set[str]):
        headers = {
            "Authorization": f"Bearer {self._bearer}",
            "User-Agent": "v2RecentSearchPython",
        }
        for query in SEARCH_QUERIES:
            await self.rate_limit()
            try:
                resp = await client.get(
                    TWITTER_V2_URL,
                    params={
                        "query": f"{query} lang:en -is:retweet",
                        "max_results": 100,
                        "tweet.fields": "created_at,public_metrics,author_id,entities",
                        "expansions": "author_id",
                        "user.fields": "username,name,public_metrics,verified",
                    },
                    headers=headers,
                )
                if resp.status_code == 429:
                    self.log.warning("twitter_v2_rate_limit", query=query)
                    await asyncio.sleep(15)
                    continue
                if resp.status_code != 200:
                    self.log.warning("twitter_v2_failed", query=query, status=resp.status_code)
                    continue

                data = resp.json()
                users_by_id = {
                    u["id"]: u
                    for u in (data.get("includes") or {}).get("users", [])
                }
                for tweet in data.get("data") or []:
                    tid = tweet.get("id", "")
                    if not tid or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    user = users_by_id.get(tweet.get("author_id", ""), {})
                    await self._store_tweet_v2(tweet, user, query)

            except Exception as e:
                self.log.warning("twitter_v2_error", query=query, error=str(e))

    async def _store_tweet_v2(self, tweet: dict, user: dict, query: str):
        text = tweet.get("text", "")
        if not text or len(text) < 20:
            return

        tid      = tweet.get("id", "")
        username = user.get("username") or user.get("name") or "unknown"
        metrics  = tweet.get("public_metrics") or {}
        likes    = metrics.get("like_count", 0)
        retweets = metrics.get("retweet_count", 0)
        replies  = metrics.get("reply_count", 0)
        followers = (user.get("public_metrics") or {}).get("followers_count", 0)
        verified  = user.get("verified") or False

        try:
            created_at = datetime.fromisoformat(
                tweet.get("created_at", "").replace("Z", "+00:00")
            )
        except Exception:
            created_at = datetime.now(timezone.utc)

        author = await self.upsert_user(
            platform_name="twitter",
            platform_user_id=tweet.get("author_id", f"tw_{username}"),
            username=username,
            profile_url=f"https://x.com/{username}",
        )

        await self.upsert_post(
            user_id=author,
            platform_name="twitter",
            post_type="post",
            platform_post_id=f"twitter_{tid}",
            body=text,
            title=text[:120],
            url=f"https://x.com/{username}/status/{tid}",
            posted_at=created_at,
            score=likes + retweets * 3,
            raw_metadata={
                "source": "twitter",
                "tweet_id": tid,
                "username": username,
                "followers": followers,
                "verified": verified,
                "likes": likes,
                "retweets": retweets,
                "replies": replies,
                "query": query,
                "via": "api_v2",
            },
        )

    # ── Nitter fallback ──────────────────────────────────────────────────────

    async def _find_nitter(self, client: httpx.AsyncClient) -> str:
        """Return the first reachable Nitter instance."""
        for base in NITTER_INSTANCES:
            try:
                resp = await client.get(f"{base}/search?q=test&f=tweets", timeout=10.0)
                if resp.status_code == 200 and "tweet" in resp.text.lower():
                    self.log.info("nitter_instance_found", base=base)
                    return base
            except Exception:
                continue
        return ""

    async def _scrape_nitter(self, client: httpx.AsyncClient, seen_ids: set[str]):
        for query in SEARCH_QUERIES:
            await self.rate_limit()
            try:
                url = f"{self._nitter_base}/search?q={quote(query)}&f=tweets"
                resp = await client.get(url, headers=random_headers(), timeout=20.0)
                if resp.status_code != 200:
                    self.log.warning("nitter_fetch_failed", query=query, status=resp.status_code)
                    continue

                tweets = self._parse_nitter_html(resp.text)
                for tw in tweets:
                    tid = tw.get("id", "")
                    if not tid or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    await self._store_tweet_nitter(tw, query)

            except Exception as e:
                self.log.warning("nitter_scrape_error", query=query, error=str(e))

    def _parse_nitter_html(self, html: str) -> list[dict]:
        """Parse tweet cards from Nitter HTML."""
        tweets = []

        # Nitter renders: <div class="timeline-item">...</div>
        # Each contains:
        #   <a class="tweet-link" href="/@user/status/ID">
        #   <div class="tweet-content">text</div>
        #   <a class="username">@user</a>
        #   <span class="tweet-date"><a title="date">...</a></span>

        for block in re.finditer(
            r'<div class="timeline-item[^"]*">(.*?)</div>\s*</div>\s*</div>',
            html, re.S
        ):
            blk = block.group(1)

            # Tweet ID from status link
            tid_m = re.search(r'/status/(\d+)', blk)
            tid = tid_m.group(1) if tid_m else ""

            # Username
            user_m = re.search(r'<a class="username"[^>]*>@?([^<]+)</a>', blk)
            username = user_m.group(1).strip() if user_m else "unknown"

            # Tweet text
            text_m = re.search(
                r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>',
                blk, re.S
            )
            if not text_m:
                continue
            text = re.sub(r'<[^>]+>', ' ', text_m.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            if not text or len(text) < 15:
                continue

            # Date
            date_m = re.search(r'<span[^>]+title="([^"]+)"', blk)
            try:
                # Nitter date format: "Jan 1, 2024 · 12:00 PM UTC"
                date_str = (date_m.group(1) if date_m else "").replace(" · ", " ")
                created_at = datetime.strptime(date_str[:20], "%b %d, %Y %I:%M %p")
                created_at = created_at.replace(tzinfo=timezone.utc)
            except Exception:
                created_at = datetime.now(timezone.utc)

            # Stats (likes, retweets)
            likes_m    = re.search(r'class="icon-heart[^>]*>.*?<span[^>]*>(\d+)', blk, re.S)
            rt_m       = re.search(r'class="icon-retweet[^>]*>.*?<span[^>]*>(\d+)', blk, re.S)
            likes    = int(likes_m.group(1)) if likes_m else 0
            retweets = int(rt_m.group(1)) if rt_m else 0

            tweets.append(dict(
                id=tid,
                username=username,
                text=text,
                created_at=created_at,
                likes=likes,
                retweets=retweets,
            ))

        return tweets

    async def _store_tweet_nitter(self, tw: dict, query: str):
        username = tw.get("username", "unknown")
        tid      = tw.get("id", "")
        text     = tw.get("text", "")
        likes    = tw.get("likes", 0)
        retweets = tw.get("retweets", 0)

        author = await self.upsert_user(
            platform_name="twitter",
            platform_user_id=f"tw_{username}",
            username=username,
            profile_url=f"https://x.com/{username}",
        )

        await self.upsert_post(
            user_id=author,
            platform_name="twitter",
            post_type="post",
            platform_post_id=f"twitter_{tid}",
            body=text,
            title=text[:120],
            url=f"https://x.com/{username}/status/{tid}" if tid else "",
            posted_at=tw.get("created_at", datetime.now(timezone.utc)),
            score=likes + retweets * 3,
            raw_metadata={
                "source": "twitter",
                "tweet_id": tid,
                "username": username,
                "likes": likes,
                "retweets": retweets,
                "query": query,
                "via": "nitter",
            },
        )
