"""Topic detector — uses LLM to identify discussion topics from recent posts."""

import asyncio
import json
import re
from datetime import timedelta

import structlog
from sqlalchemy import select, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import async_session, Post, Topic, TopicMention, Platform
from processors.llm_client import call_llm, TokenUsage
from scrapers.base_scraper import _utc_naive

logger = structlog.get_logger()

TOPIC_SYSTEM_MESSAGE = (
    "You extract discussion topics from social media posts about AI and technology. "
    "Always respond with valid JSON only, no additional text or markdown."
)

TOPIC_PROMPT_TEMPLATE = """Analyze these {N} recent social media posts from AI/tech communities and extract the main discussion topics.

Posts:
{posts_json}

For each distinct topic found, return JSON:
{{
  "topics": [
    {{
      "name": "Topic Name",
      "slug": "topic-name-slug",
      "description": "One sentence description",
      "keywords": ["keyword1", "keyword2", "keyword3"],
      "post_indices": [0, 3, 7],
      "sentiment_distribution": {{"positive": 0.4, "negative": 0.3, "neutral": 0.3}},
      "opinion_camps": [
        {{"name": "Camp A", "stance": "Brief description of this camp's position", "estimated_share": 0.6}},
        {{"name": "Camp B", "stance": "Brief description of this camp's position", "estimated_share": 0.4}}
      ]
    }}
  ]
}}

Return 5-10 distinct topics. Each post can belong to multiple topics."""


class TopicDetector:
    """Detects and tracks discussion topics across platforms."""

    BATCH_SIZE = 50  # Posts per LLM call
    LOOKBACK_DAYS = 7
    LLM_DELAY = 1.0

    def __init__(self):
        self.log = logger.bind(processor="topic_detector")
        self.usage = TokenUsage()
        self.processed = 0
        self.topics_found = 0
        self.mentions_created = 0
        self.errors = 0

    async def run(self) -> dict:
        """Main entry: extract topics from recent posts, update topic table."""
        self.log.info("topic_detection_start")

        offset = 0
        while True:
            async with async_session() as session:
                posts = await self._get_recent_posts(session, offset, self.BATCH_SIZE)

            if not posts:
                break

            post_dicts = [
                {
                    "index": i,
                    "id": p[0],
                    "title": (p[1] or "")[:200],
                    "body": (p[2] or "")[:300],
                    "subreddit": p[3] or "",
                    "score": p[4] or 0,
                    "platform_id": p[5],
                }
                for i, p in enumerate(posts)
            ]

            topics = await self._extract_topics_from_batch(post_dicts)
            if topics:
                async with async_session() as session:
                    await self._save_topics(session, topics, post_dicts)
                    await session.commit()

            self.processed += len(posts)
            offset += self.BATCH_SIZE
            await asyncio.sleep(self.LLM_DELAY)

            self.log.info(
                "topic_batch_done",
                posts_processed=self.processed,
                topics_found=self.topics_found,
            )

        # Recalculate velocity for all active topics
        async with async_session() as session:
            await self._update_velocity(session)
            await session.commit()

        self.log.info(
            "topic_detection_complete",
            processed=self.processed,
            topics_found=self.topics_found,
            mentions_created=self.mentions_created,
            tokens=self.usage.total_tokens,
            cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {
            "processed": self.processed,
            "topics_found": self.topics_found,
            "mentions_created": self.mentions_created,
            "errors": self.errors,
            "total_tokens": self.usage.total_tokens,
        }

    async def _get_recent_posts(self, session, offset: int, limit: int) -> list:
        """Fetch posts from the last LOOKBACK_DAYS days."""
        cutoff = _utc_naive() - timedelta(days=self.LOOKBACK_DAYS)
        result = await session.execute(
            select(Post.id, Post.title, Post.body, Post.subreddit, Post.score, Post.platform_id)
            .where(Post.posted_at >= cutoff)
            .order_by(Post.posted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.all()

    async def _extract_topics_from_batch(self, posts: list[dict]) -> list[dict] | None:
        """Call LLM to extract topics from a batch of posts."""
        # Build simplified post list for the prompt
        prompt_posts = [
            {"index": p["index"], "title": p["title"], "body": p["body"], "score": p["score"]}
            for p in posts
        ]
        posts_json = json.dumps(prompt_posts, indent=2, default=str)
        prompt = TOPIC_PROMPT_TEMPLATE.format(N=len(posts), posts_json=posts_json)

        try:
            result = await call_llm(
                prompt=prompt,
                system_message=TOPIC_SYSTEM_MESSAGE,
                model="mini",
                temperature=0.3,
                max_tokens=3000,
                parse_json=True,
                usage_tracker=self.usage,
            )
            return result.get("topics", []) if isinstance(result, dict) else None
        except Exception as e:
            self.errors += 1
            self.log.warning("topic_llm_failed", error=str(e))
            return None

    async def _save_topics(self, session, topics: list[dict], posts: list[dict]) -> None:
        """Upsert topics and create topic_mentions."""
        # Build a map from post index to post id
        index_to_id = {p["index"]: p["id"] for p in posts}
        index_to_platform = {p["index"]: p["platform_id"] for p in posts}

        for topic_data in topics:
            try:
                slug = topic_data.get("slug", "")
                if not slug:
                    slug = re.sub(r"[^a-z0-9-]", "-", topic_data.get("name", "").lower().strip())
                    slug = re.sub(r"-+", "-", slug).strip("-")

                if not slug:
                    continue

                # Upsert topic
                topic_id = await self._upsert_topic(session, topic_data, slug)
                self.topics_found += 1

                # Create topic_mentions for linked posts
                post_indices = topic_data.get("post_indices", [])
                sentiment_dist = topic_data.get("sentiment_distribution", {})
                avg_sentiment = (sentiment_dist.get("positive", 0) - sentiment_dist.get("negative", 0))

                for idx in post_indices:
                    post_id = index_to_id.get(idx)
                    if post_id is not None:
                        await self._create_topic_mention(session, topic_id, post_id, 0.8, avg_sentiment)

                # Update platforms_active
                platform_ids = set()
                for idx in post_indices:
                    pid = index_to_platform.get(idx)
                    if pid:
                        platform_ids.add(pid)
                if platform_ids:
                    await self._update_platforms_active(session, topic_id, platform_ids)

            except Exception as e:
                self.errors += 1
                self.log.warning("topic_save_failed", topic=topic_data.get("name"), error=str(e))

    async def _upsert_topic(self, session, topic_data: dict, slug: str) -> int:
        """Insert or update a topic, returns topic ID."""
        now = _utc_naive()

        stmt = pg_insert(Topic).values(
            name=topic_data.get("name", slug),
            slug=slug,
            description=topic_data.get("description", ""),
            keywords=topic_data.get("keywords", []),
            first_seen_at=now,
            last_seen_at=now,
            total_mentions=len(topic_data.get("post_indices", [])),
            sentiment_distribution=topic_data.get("sentiment_distribution"),
            opinion_camps=topic_data.get("opinion_camps"),
            status="active",
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Topic.slug],
            set_={
                "last_seen_at": now,
                "total_mentions": Topic.total_mentions + len(topic_data.get("post_indices", [])),
                "sentiment_distribution": stmt.excluded.sentiment_distribution,
                "opinion_camps": stmt.excluded.opinion_camps,
                "updated_at": now,
            },
        )
        await session.execute(stmt)

        # Get the topic ID
        result = await session.execute(select(Topic.id).where(Topic.slug == slug))
        return result.scalar_one()

    async def _create_topic_mention(
        self, session, topic_id: int, post_id: int, relevance_score: float, sentiment: float
    ) -> None:
        """Create a topic_mention if it doesn't already exist."""
        existing = await session.execute(
            select(TopicMention.id).where(
                TopicMention.topic_id == topic_id,
                TopicMention.post_id == post_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        mention = TopicMention(
            topic_id=topic_id,
            post_id=post_id,
            relevance_score=relevance_score,
            sentiment=sentiment,
            created_at=_utc_naive(),
        )
        session.add(mention)
        self.mentions_created += 1

    async def _update_velocity(self, session) -> None:
        """Recalculate velocity for all topics based on recent mention rates."""
        now = _utc_naive()
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)

        topics = (await session.execute(select(Topic))).scalars().all()

        for topic in topics:
            # Count mentions in last 24h
            recent_count = (
                await session.execute(
                    select(func.count(TopicMention.id)).where(
                        TopicMention.topic_id == topic.id,
                        TopicMention.created_at >= one_day_ago,
                    )
                )
            ).scalar() or 0

            # Count mentions in prior 6 days
            prior_count = (
                await session.execute(
                    select(func.count(TopicMention.id)).where(
                        TopicMention.topic_id == topic.id,
                        TopicMention.created_at >= seven_days_ago,
                        TopicMention.created_at < one_day_ago,
                    )
                )
            ).scalar() or 0

            avg_daily_prior = max(prior_count / 6.0, 1.0)
            velocity = recent_count / avg_daily_prior

            # Determine status
            if topic.first_seen_at and (now - topic.first_seen_at).days <= 2 and velocity > 1:
                status = "emerging"
            elif velocity > 2.0:
                status = "peaking"
            elif velocity > 0.5:
                status = "active"
            elif velocity > 0.1:
                status = "declining"
            else:
                status = "declining"

            topic.velocity = round(velocity, 4)
            topic.status = status
            topic.updated_at = now

    async def _update_platforms_active(self, session, topic_id: int, platform_ids: set) -> None:
        """Update the platforms_active JSONB for a topic."""
        # Load platform names
        platforms = {}
        for pid in platform_ids:
            result = await session.execute(select(Platform.name).where(Platform.id == pid))
            name = result.scalar_one_or_none()
            if name:
                # Count mentions for this platform + topic
                count = (
                    await session.execute(
                        select(func.count(TopicMention.id))
                        .join(Post, TopicMention.post_id == Post.id)
                        .where(
                            TopicMention.topic_id == topic_id,
                            Post.platform_id == pid,
                        )
                    )
                ).scalar() or 0
                platforms[name] = count

        if platforms:
            topic = await session.get(Topic, topic_id)
            if topic:
                existing = topic.platforms_active or {}
                existing.update(platforms)
                topic.platforms_active = existing
