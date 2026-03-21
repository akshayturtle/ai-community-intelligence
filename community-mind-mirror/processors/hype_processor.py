"""Hype vs Reality Index — compares press/VC sentiment vs builder sentiment.

Layer 1+2 only — NO LLM needed.
Dynamically derives sectors from topics with mentions across both news AND community.
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, and_, text

from database.connection import (
    async_session,
    Topic,
    TopicMention,
    Post,
    NewsEvent,
    HypeIndex,
    Platform,
)

logger = structlog.get_logger()

SEED_SECTORS = {
    "AI agents": ["AI agent", "agentic", "multi-agent", "autonomous agent"],
    "Humanoid robots": ["humanoid", "humanoid robot", "home robot"],
    "AI coding tools": ["AI coding", "Cursor", "Copilot", "Claude Code", "vibe coding"],
    "Open source models": ["open source model", "open weight", "Llama", "Mistral", "local LLM"],
    "AI infrastructure": ["AI infra", "GPU cloud", "inference", "training compute"],
}


class HypeProcessor:
    """Calculates hype vs reality gap per sector/topic."""

    def __init__(self):
        self.log = logger.bind(processor="hype_processor")
        self.sectors_analyzed = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("hype_processor_start")

        # Step 1: Get sectors (topics with cross-source mentions)
        sectors = await self._get_sectors()
        self.log.info("sectors_found", count=len(sectors))

        # Step 2: Calculate hype index for each sector
        for sector_name, keywords in sectors.items():
            await self._calculate_hype(sector_name, keywords)

        self.log.info(
            "hype_processor_complete",
            sectors=self.sectors_analyzed,
            errors=self.errors,
        )
        return {"sectors_analyzed": self.sectors_analyzed, "errors": self.errors}

    async def _get_sectors(self) -> dict[str, list[str]]:
        """Derive sectors from active topics that exist in both press AND community."""
        async with async_session() as session:
            # Get topics with decent mention counts
            result = await session.execute(
                select(Topic.id, Topic.name, Topic.keywords)
                .where(Topic.status.in_(["emerging", "active", "peaking"]))
                .where(Topic.total_mentions > 10)
                .order_by(Topic.velocity.desc())
                .limit(20)
            )
            topics = result.all()

        sectors = {}
        for topic_id, name, keywords in topics:
            kw = keywords if isinstance(keywords, list) else [name]
            sectors[name] = kw

        # If not enough dynamic sectors, use seeds
        if len(sectors) < 5:
            for name, kw in SEED_SECTORS.items():
                if name not in sectors:
                    sectors[name] = kw

        return sectors

    async def _calculate_hype(self, sector_name: str, keywords: list[str]):
        """Calculate press vs builder sentiment gap for a sector."""
        try:
            cutoff = datetime.utcnow() - timedelta(days=30)

            async with async_session() as session:
                # Get community platform IDs (reddit, hackernews)
                platform_result = await session.execute(
                    select(Platform.id).where(Platform.name.in_(["reddit", "hackernews"]))
                )
                community_platform_ids = [r.id for r in platform_result.all()]

                # Build keyword search condition
                keyword_conditions = []
                for kw in keywords[:5]:
                    keyword_conditions.append(Post.body.ilike(f"%{kw}%"))

                if not keyword_conditions:
                    return

                from sqlalchemy import or_
                kw_filter = or_(*keyword_conditions)

            async with async_session() as session:
                # Get posts matching keywords, compute sentiment in Python
                builder_posts = await session.execute(
                    select(Post.raw_metadata)
                    .where(Post.posted_at >= cutoff)
                    .where(Post.platform_id.in_(community_platform_ids))
                    .where(Post.raw_metadata.isnot(None))
                    .where(Post.raw_metadata.has_key("sentiment"))
                    .where(kw_filter)
                    .limit(200)
                )
                b_rows = builder_posts.all()

                builder_sentiments = []
                for (metadata,) in b_rows:
                    if metadata and "sentiment" in metadata:
                        s = metadata["sentiment"].get("compound")
                        if s is not None:
                            builder_sentiments.append(float(s))

                # Press/VC sentiment (news events)
                # Search both title AND body so short headlines don't cause misses
                news_kw_conditions = []
                for kw in keywords[:5]:
                    news_kw_conditions.append(NewsEvent.title.ilike(f"%{kw}%"))
                    news_kw_conditions.append(NewsEvent.body.ilike(f"%{kw}%"))

                news_filter = or_(*news_kw_conditions)

                press_result = await session.execute(
                    select(NewsEvent.sentiment)
                    .where(NewsEvent.published_at >= cutoff)
                    .where(NewsEvent.source_type == "news")
                    .where(NewsEvent.sentiment.isnot(None))
                    .where(news_filter)
                    .limit(200)
                )
                press_sentiments = [float(r.sentiment) for r in press_result.all() if r.sentiment is not None]

            # Calculate averages — use None when no data so we can skip
            builder_avg = sum(builder_sentiments) / len(builder_sentiments) if builder_sentiments else None
            press_avg = sum(press_sentiments) / len(press_sentiments) if press_sentiments else None

            # Need at least one side with meaningful data (3+ posts)
            if (not builder_sentiments or len(builder_sentiments) < 3) and \
               (not press_sentiments or len(press_sentiments) < 3):
                return

            # Default missing side to neutral (0.0) rather than skipping
            if builder_avg is None:
                builder_avg = 0.0
            if press_avg is None:
                press_avg = 0.0

            gap = abs(press_avg - builder_avg)

            if gap < 0.15:
                status = "aligned"
            elif press_avg > builder_avg + 0.15:
                status = "overhyped"
            elif builder_avg > press_avg + 0.15:
                status = "underhyped"
            else:
                status = "gap_widening"

            async with async_session() as session:
                # Upsert
                existing = await session.execute(
                    select(HypeIndex.id).where(HypeIndex.sector_name == sector_name)
                )
                row = existing.scalar()

                if row:
                    from sqlalchemy import update
                    await session.execute(
                        update(HypeIndex)
                        .where(HypeIndex.id == row)
                        .values(
                            builder_sentiment=round(builder_avg, 4),
                            vc_sentiment=round(press_avg, 4),
                            gap=round(gap, 4),
                            status=status,
                            builder_post_count=len(builder_sentiments),
                            vc_post_count=len(press_sentiments),
                            calculated_at=datetime.utcnow(),
                        )
                    )
                else:
                    session.add(HypeIndex(
                        sector_name=sector_name,
                        builder_sentiment=round(builder_avg, 4),
                        vc_sentiment=round(press_avg, 4),
                        gap=round(gap, 4),
                        status=status,
                        builder_post_count=len(builder_sentiments),
                        vc_post_count=len(press_sentiments),
                    ))

                await session.commit()
                self.sectors_analyzed += 1

        except Exception as e:
            self.errors += 1
            self.log.warning("hype_calc_failed", sector=sector_name, error=str(e))
