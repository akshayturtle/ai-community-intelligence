"""YouTube scraper — uses RSS (free) + Data API v3 (quota) + transcript library (free)."""

from datetime import datetime, timezone

import feedparser
import httpx
import structlog

from config.settings import YOUTUBE_API_KEY
from config.sources import YOUTUBE_CHANNELS, YOUTUBE_SCRAPE_CONFIG
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

YT_API_BASE = "https://www.googleapis.com/youtube/v3"
DAILY_QUOTA_LIMIT = 9500  # Stop before hitting 10,000


class YouTubeScraper(BaseScraper):
    """Scrapes YouTube channels using RSS + API + transcript library."""

    PLATFORM = "youtube"

    def __init__(self):
        super().__init__(scraper_name="youtube_scraper", request_delay=0.5)
        self.quota_used = 0

    async def scrape(
        self,
        channels: list[dict] | None = None,
        max_videos_per_channel: int | None = None,
        **kwargs,
    ):
        """Scrape YouTube channels for videos, comments, and transcripts."""
        targets = channels or YOUTUBE_CHANNELS
        max_vids = max_videos_per_channel or YOUTUBE_SCRAPE_CONFIG["videos_per_channel"]

        if not YOUTUBE_API_KEY:
            self.log.warning("no_youtube_api_key", msg="Set YOUTUBE_API_KEY in .env")
            return

        self.log.info("youtube_scrape_start", channels=len(targets))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for channel in targets:
                if self.quota_used >= DAILY_QUOTA_LIMIT:
                    self.log.warning("quota_limit_approaching", used=self.quota_used)
                    break
                await self._scrape_channel(client, channel, max_vids)

        self.log.info(
            "youtube_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            quota_used=self.quota_used,
        )

    async def _scrape_channel(
        self, client: httpx.AsyncClient, channel: dict, max_videos: int
    ):
        """Scrape a single channel: RSS for video list, API for details + comments."""
        channel_name = channel["name"]
        channel_id = channel["channel_id"]

        self.log.info("scraping_channel", channel=channel_name)

        # Store channel as a user
        channel_user_id = await self.upsert_user(
            platform_name=self.PLATFORM,
            platform_user_id=channel_id,
            username=channel_name,
            profile_url=f"https://www.youtube.com/channel/{channel_id}",
            raw_metadata={"type": "channel"},
        )

        # Phase 1: Get video IDs from RSS (FREE — no quota)
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            response = await self.fetch_url(client, rss_url)
            feed = feedparser.parse(response.text)
        except Exception as e:
            self.log.warning("rss_fetch_failed", channel=channel_name, error=str(e))
            return

        video_ids = []
        for entry in feed.entries[:max_videos]:
            vid_id = entry.get("yt_videoid", "")
            if not vid_id:
                link = entry.get("link", "")
                if "v=" in link:
                    vid_id = link.split("v=")[-1].split("&")[0]
            if vid_id:
                video_ids.append(vid_id)

        if not video_ids:
            self.log.debug("no_videos_found", channel=channel_name)
            return

        self.log.info("rss_videos_found", channel=channel_name, count=len(video_ids))

        # Phase 2: Get video details from API (batch up to 50, 1 quota unit)
        video_details = await self._fetch_video_details(client, video_ids)

        # Phase 3: For each video — save details, fetch comments, get transcript
        for video in video_details:
            vid_id = video["id"]
            snippet = video.get("snippet", {})
            stats = video.get("statistics", {})

            title = snippet.get("title", "")
            description = snippet.get("description", "")
            published_str = snippet.get("publishedAt", "")
            published_at = self._parse_yt_date(published_str)
            view_count = int(stats.get("viewCount", 0))
            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))

            # Store video as a post by the channel
            await self.upsert_post(
                user_id=channel_user_id,
                platform_name=self.PLATFORM,
                post_type="video",
                platform_post_id=f"yt_video_{vid_id}",
                title=title,
                body=description or title,
                url=f"https://www.youtube.com/watch?v={vid_id}",
                score=like_count,
                num_comments=comment_count,
                posted_at=published_at,
                raw_metadata={
                    "video_id": vid_id,
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "view_count": view_count,
                    "like_count": like_count,
                    "tags": snippet.get("tags", []),
                },
            )

            # Fetch comments (if quota allows)
            if self.quota_used < DAILY_QUOTA_LIMIT:
                await self._fetch_video_comments(client, vid_id, channel_user_id)

            # Fetch transcript (FREE — no quota)
            await self._fetch_transcript(vid_id, channel_name, title, published_at)

    async def _fetch_video_details(
        self, client: httpx.AsyncClient, video_ids: list[str]
    ) -> list[dict]:
        """Fetch video details from YouTube API. Batches up to 50 IDs per call."""
        all_details = []

        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            ids_str = ",".join(batch)
            url = (
                f"{YT_API_BASE}/videos"
                f"?part=snippet,statistics,contentDetails"
                f"&id={ids_str}"
                f"&key={YOUTUBE_API_KEY}"
            )
            try:
                response = await self.fetch_url(client, url)
                self.quota_used += 1  # 1 unit per videos call
                data = response.json()
                all_details.extend(data.get("items", []))
                await self.rate_limit()
            except Exception as e:
                self.log.warning("video_details_failed", error=str(e))

        return all_details

    async def _fetch_video_comments(
        self, client: httpx.AsyncClient, video_id: str, channel_user_id: int
    ):
        """Fetch top comments for a video from YouTube API."""
        max_comments = YOUTUBE_SCRAPE_CONFIG["comments_per_video"]
        url = (
            f"{YT_API_BASE}/commentThreads"
            f"?part=snippet,replies"
            f"&videoId={video_id}"
            f"&maxResults={min(max_comments, 100)}"
            f"&order=relevance"
            f"&key={YOUTUBE_API_KEY}"
        )
        try:
            response = await self.fetch_url(client, url)
            self.quota_used += 1  # 1 unit per commentThreads call
            data = response.json()
            await self.rate_limit()
        except Exception as e:
            self.log.debug("comments_fetch_failed", video_id=video_id, error=str(e))
            return

        for item in data.get("items", []):
            top_comment = item.get("snippet", {}).get("topLevelComment", {})
            comment_snippet = top_comment.get("snippet", {})

            author_name = comment_snippet.get("authorDisplayName", "")
            author_channel_id = comment_snippet.get("authorChannelId", {}).get("value", "")
            comment_text = comment_snippet.get("textDisplay", "")
            like_count = comment_snippet.get("likeCount", 0)
            published_str = comment_snippet.get("publishedAt", "")

            if not comment_text or not author_channel_id:
                continue

            # Upsert commenter as user
            commenter_id = await self.upsert_user(
                platform_name=self.PLATFORM,
                platform_user_id=author_channel_id,
                username=author_name,
                profile_url=f"https://www.youtube.com/channel/{author_channel_id}",
                raw_metadata={"type": "commenter"},
            )

            # Store comment as post
            comment_id = top_comment.get("id", "")
            await self.upsert_post(
                user_id=commenter_id,
                platform_name=self.PLATFORM,
                post_type="comment",
                platform_post_id=f"yt_comment_{comment_id}",
                body=comment_text,
                url=f"https://www.youtube.com/watch?v={video_id}",
                score=like_count,
                posted_at=self._parse_yt_date(published_str),
                raw_metadata={
                    "video_id": video_id,
                    "comment_id": comment_id,
                },
            )

    async def _fetch_transcript(
        self,
        video_id: str,
        channel_name: str,
        title: str,
        published_at: datetime | None,
    ):
        """Fetch video transcript using youtube-transcript-api (FREE)."""
        if not YOUTUBE_SCRAPE_CONFIG.get("extract_transcripts"):
            return

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            ytt_api = YouTubeTranscriptApi()
            transcript_obj = ytt_api.fetch(video_id)
            # Combine all segments into one text
            full_text = " ".join(
                snippet.text for snippet in transcript_obj
            )

            if full_text.strip():
                await self.upsert_news_event(
                    source_type="youtube_transcript",
                    source_name=channel_name,
                    title=f"[Transcript] {title}",
                    body=full_text,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=published_at,
                    categories=["youtube", "transcript"],
                    raw_metadata={
                        "video_id": video_id,
                        "channel_name": channel_name,
                        "word_count": len(full_text.split()),
                    },
                )
        except Exception as e:
            self.log.debug("transcript_failed", video_id=video_id, error=str(e))

    def _parse_yt_date(self, date_str: str) -> datetime | None:
        """Parse YouTube ISO 8601 dates."""
        if not date_str:
            return None
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt
        except ValueError:
            return None
