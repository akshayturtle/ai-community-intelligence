"""Platform Tone Analyzer — how each platform discusses a topic differently.

Layer 3: LLM analyzes tone differences across platforms for trending topics.
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, func

from database.connection import (
    async_session,
    Topic,
    TopicMention,
    Post,
    Platform,
    PlatformTone,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()


class PlatformToneProcessor:
    """Analyzes how each platform discusses trending topics differently."""

    def __init__(self):
        self.log = logger.bind(processor="platform_tone_processor")
        self.usage = TokenUsage()
        self.topics_analyzed = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("platform_tone_start")

        # Get top trending topics
        topics = await self._get_trending_topics()
        self.log.info("topics_to_analyze", count=len(topics))

        for topic in topics:
            await self._analyze_topic(topic)

        self.log.info(
            "platform_tone_complete",
            topics=self.topics_analyzed,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"topics_analyzed": self.topics_analyzed, "errors": self.errors}

    async def _get_trending_topics(self) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(Topic.id, Topic.name, Topic.keywords)
                .where(Topic.status.in_(["emerging", "active", "peaking"]))
                .order_by(Topic.velocity.desc())
                .limit(5)
            )
            return [{"id": r.id, "name": r.name, "keywords": r.keywords or [r.name]} for r in result.all()]

    async def _analyze_topic(self, topic: dict):
        """Get posts per platform and ask LLM to describe tone differences."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=14)

            async with async_session() as session:
                # Get platform map
                platforms_result = await session.execute(select(Platform.id, Platform.name))
                platform_map = {r.id: r.name for r in platforms_result.all()}

                # Get posts linked to this topic via topic_mentions
                result = await session.execute(
                    select(Post.body, Post.platform_id, Post.score, Post.raw_metadata)
                    .join(TopicMention, TopicMention.post_id == Post.id)
                    .where(TopicMention.topic_id == topic["id"])
                    .where(Post.posted_at >= cutoff)
                    .order_by(Post.score.desc())
                    .limit(60)
                )
                posts = result.all()

            if len(posts) < 5:
                return

            # Group by platform and collect sentiments
            by_platform: dict[str, list[str]] = {}
            platform_sentiments: dict[str, list[float]] = {}
            for body, platform_id, score, raw_metadata in posts:
                pname = platform_map.get(platform_id, "unknown")
                by_platform.setdefault(pname, [])
                platform_sentiments.setdefault(pname, [])
                if body:
                    by_platform[pname].append(body[:200])
                # Extract sentiment compound score
                if raw_metadata and "sentiment" in raw_metadata:
                    compound = raw_metadata["sentiment"].get("compound")
                    if compound is not None:
                        platform_sentiments[pname].append(float(compound))

            if len(by_platform) < 2:
                return  # Need at least 2 platforms for comparison

            # Build prompt
            platform_sections = []
            for pname, ppost_texts in by_platform.items():
                sample = "\n".join(f"  - {t}" for t in ppost_texts[:10])
                platform_sections.append(f"**{pname.title()}** ({len(ppost_texts)} posts):\n{sample}")

            prompt = f"""Topic: "{topic['name']}"

Here are community posts about this topic from different platforms:

{chr(10).join(platform_sections)}

For each platform, write 2-3 sentences describing the TONE and FOCUS of discussion.
How does each platform discuss this topic differently?

Return JSON object with platform names as keys and tone descriptions as values.
Example: {{"reddit": "Excited but practical...", "hackernews": "Technical and contrarian..."}}"""

            result = await call_llm(
                prompt=prompt,
                system_message="You are a community intelligence analyst comparing discussion cultures.",
                model="mini",
                parse_json=True,
                usage_tracker=self.usage,
                max_tokens=600,
            )

            if not isinstance(result, dict):
                return

            async with async_session() as session:
                for platform_name, tone_desc in result.items():
                    if not isinstance(tone_desc, str):
                        continue

                    pname_lower = platform_name.lower()
                    post_count = len(by_platform.get(pname_lower, []))

                    # Compute avg_sentiment from collected sentiments
                    sents = platform_sentiments.get(pname_lower, [])
                    avg_sent = round(sum(sents) / len(sents), 4) if sents else None

                    # Upsert
                    existing = await session.execute(
                        select(PlatformTone.id)
                        .where(PlatformTone.topic_id == topic["id"])
                        .where(PlatformTone.platform_name == pname_lower)
                    )
                    row_id = existing.scalar()

                    if row_id:
                        from sqlalchemy import update
                        await session.execute(
                            update(PlatformTone)
                            .where(PlatformTone.id == row_id)
                            .values(
                                tone_description=tone_desc,
                                post_count=post_count,
                                avg_sentiment=avg_sent,
                                analyzed_at=datetime.utcnow(),
                            )
                        )
                    else:
                        session.add(PlatformTone(
                            topic_id=topic["id"],
                            platform_name=pname_lower,
                            tone_description=tone_desc,
                            post_count=post_count,
                            avg_sentiment=avg_sent,
                        ))

                await session.commit()
                self.topics_analyzed += 1

        except Exception as e:
            self.errors += 1
            self.log.warning("platform_tone_failed", topic=topic["name"], error=str(e))
