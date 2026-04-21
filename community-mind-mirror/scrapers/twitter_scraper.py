"""X.com (Twitter) scraper — uses residential proxies (DataImpulse).

Scrapes public search results for AI/tech project discussions, job posts,
freelance opportunities, and tool launches — without needing API auth.
Uses Twitter's internal Explore/search API endpoint.

Requires: DATAIMPULSE_HOST, DATAIMPULSE_PORT, DATAIMPULSE_USER, DATAIMPULSE_PASS
"""

import json
import re
from datetime import datetime, timezone

import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.proxy import proxy_client, random_headers, json_headers, is_configured

logger = structlog.get_logger()

# High-signal search queries for market intelligence
SEARCH_QUERIES = [
    # Freelance project signals
    "hiring developer site:x.com",
    "looking for AI engineer",
    "need Python developer DM",
    # AI product launches
    "#buildinpublic AI agent",
    "just launched AI tool",
    "new AI wrapper",
    # Market demand
    "AI automation budget",
    "LLM project scope",
    "need ML engineer freelance",
    # Tech trends
    "#AI #hiring remote",
    "building with Claude OR GPT-4 launch",
    "shipped AI feature",
]

GUEST_TOKEN_URL = "https://api.twitter.com/1.1/guest/activate.json"
SEARCH_URL = "https://twitter.com/i/api/2/search/adaptive.json"

# Twitter Bearer token (public, embedded in the web app — rotate if blocked)
_BEARER_TOKENS = [
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
]


class TwitterScraper(BaseScraper):
    """
    Scrapes X.com (Twitter) public search for AI/tech/freelance signals.
    Uses the web app's guest token flow — no developer account needed.
    """

    def __init__(self):
        super().__init__(scraper_name="twitter_scraper", request_delay=3.0)
        self._guest_token: str = ""
        self._bearer: str = _BEARER_TOKENS[0]

    async def scrape(self, **kwargs):
        if not is_configured():
            self.log.warning(
                "twitter_no_proxy",
                hint="Set DATAIMPULSE_* env vars to enable Twitter scraping.",
            )
            return

        seen_ids: set[str] = set()

        async with proxy_client(timeout=30.0) as client:
            # Acquire a guest token first
            self._guest_token = await self._get_guest_token(client)
            if not self._guest_token:
                self.log.warning("twitter_no_guest_token")
                return

            for query in SEARCH_QUERIES:
                await self.rate_limit()
                tweets = await self._search(client, query)
                for tweet in tweets:
                    tid = str(tweet.get("id_str") or tweet.get("id") or "")
                    if not tid or tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    await self._store_tweet(tweet, query)

    async def _get_guest_token(self, client) -> str:
        try:
            resp = await client.post(
                GUEST_TOKEN_URL,
                headers={
                    **json_headers(),
                    "Authorization": f"Bearer {self._bearer}",
                },
            )
            return resp.json().get("guest_token", "")
        except Exception as e:
            self.log.warning("twitter_guest_token_failed", error=str(e))
            return ""

    async def _search(self, client, query: str) -> list[dict]:
        try:
            resp = await client.get(
                SEARCH_URL,
                params={
                    "q": query,
                    "count": 40,
                    "result_filter": "Top",
                    "tweet_mode": "extended",
                },
                headers={
                    **json_headers(referer="https://twitter.com/search"),
                    "Authorization": f"Bearer {self._bearer}",
                    "x-guest-token": self._guest_token,
                    "x-twitter-client-language": "en",
                    "x-twitter-active-user": "yes",
                },
            )

            if resp.status_code != 200:
                self.log.warning("twitter_search_failed", query=query, status=resp.status_code)
                return []

            data = resp.json()
            tweets = []

            # Parse adaptive search timeline
            timeline = data.get("timeline", {})
            instructions = timeline.get("instructions", [])
            for instr in instructions:
                for entry in instr.get("addEntries", {}).get("entries", []):
                    content = entry.get("content", {})
                    item = content.get("item", {})
                    tweet_results = item.get("content", {}).get("tweet_results", {})
                    result = tweet_results.get("result", {})
                    legacy = result.get("legacy") or result.get("tweet", {}).get("legacy", {})
                    if legacy and legacy.get("full_text"):
                        legacy["id_str"] = result.get("rest_id") or legacy.get("id_str", "")
                        legacy["user"] = result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
                        tweets.append(legacy)

            # Fallback for older response format
            if not tweets:
                global_objects = data.get("globalObjects", {})
                tweets_obj = global_objects.get("tweets", {})
                users_obj  = global_objects.get("users", {})
                for tid, tw in tweets_obj.items():
                    user_id = str(tw.get("user_id_str") or tw.get("user_id") or "")
                    tw["user"] = users_obj.get(user_id, {})
                    tweets.append(tw)

            return tweets

        except Exception as e:
            self.log.warning("twitter_search_error", query=query, error=str(e))
            return []

    async def _store_tweet(self, tweet: dict, query: str):
        text = tweet.get("full_text") or tweet.get("text") or ""
        if not text or len(text) < 30:
            return

        tid      = str(tweet.get("id_str") or tweet.get("id") or "")
        user     = tweet.get("user") or {}
        username = user.get("screen_name") or user.get("name") or "unknown"
        name     = user.get("name") or username
        followers = user.get("followers_count") or 0
        verified  = user.get("verified") or user.get("is_blue_verified") or False

        likes    = tweet.get("favorite_count") or 0
        retweets = tweet.get("retweet_count") or 0
        replies  = tweet.get("reply_count") or 0

        url = f"https://x.com/{username}/status/{tid}" if tid and username != "unknown" else ""

        created_raw = tweet.get("created_at") or ""
        try:
            created_at = datetime.strptime(created_raw, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
        except Exception:
            created_at = datetime.now(timezone.utc)

        # Extract URLs from tweet
        entities = tweet.get("entities") or {}
        urls_expanded = [u.get("expanded_url", "") for u in entities.get("urls", [])]

        author = await self.upsert_user(
            platform_name="twitter",
            platform_user_id=user.get("id_str") or f"tw_{username}",
            username=username,
            display_name=name,
            profile_url=f"https://x.com/{username}",
        )

        await self.upsert_post(
            platform_name="twitter",
            platform_post_id=f"twitter_{tid}",
            author_id=author,
            title=text[:120],
            content=text,
            url=url,
            created_at=created_at,
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
                "urls": urls_expanded,
            },
        )
