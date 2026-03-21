"""News processor — extracts entities, sentiment, and magnitude from news events via LLM."""

import asyncio
import json

import structlog
from sqlalchemy import select, update

from database.connection import async_session, NewsEvent, Topic, TopicMention
from processors.llm_client import call_llm, TokenUsage
from scrapers.base_scraper import _utc_naive

logger = structlog.get_logger()

NEWS_SYSTEM_MESSAGE = (
    "You extract structured entities and sentiment from news articles about AI and technology. "
    "Always respond with valid JSON only, no additional text or markdown."
)

NEWS_PROMPT_TEMPLATE = """Analyze this news article and extract structured information.

Title: {title}
Body: {body}

Return JSON:
{{
  "entities": {{
    "companies": ["company names mentioned"],
    "people": ["people mentioned"],
    "technologies": ["technologies/products mentioned"],
    "sector": "AI/robotics/funding/regulation/hardware/software/research/other"
  }},
  "sentiment": 0.0,
  "magnitude": "low",
  "related_topics": ["topic-slug-1", "topic-slug-2"]
}}

sentiment: -1.0 (very negative for tech community) to 1.0 (very positive for tech community)
magnitude: "low" (minor news), "medium" (notable), "high" (major impact), "critical" (industry-changing)"""


class NewsProcessor:
    """Extracts structured entities and metadata from news events."""

    BATCH_SIZE = 20
    LLM_DELAY = 0.3

    def __init__(self):
        self.log = logger.bind(processor="news_processor")
        self.usage = TokenUsage()
        self.processed = 0
        self.errors = 0

    async def run(self) -> dict:
        """Main entry: process news_events where entities IS NULL."""
        self.log.info("news_processing_start")

        while True:
            async with async_session() as session:
                events = await self._get_unprocessed_events(session, self.BATCH_SIZE)

            if not events:
                break

            for event in events:
                try:
                    result = await self._process_event(event)
                    if result is None:
                        self.errors += 1
                        continue

                    async with async_session() as session:
                        await self._save_results(session, event.id, result)
                        # Cross-reference with existing topics
                        related = result.get("related_topics", [])
                        if related:
                            await self._cross_reference_topics(session, event.id, related)
                        await session.commit()

                    self.processed += 1
                    await asyncio.sleep(self.LLM_DELAY)

                except Exception as e:
                    self.errors += 1
                    self.log.warning("news_item_failed", event_id=event.id, error=str(e))

            self.log.info(
                "news_batch_done",
                processed=self.processed,
                errors=self.errors,
                tokens=self.usage.total_tokens,
            )

        self.log.info(
            "news_processing_complete",
            processed=self.processed,
            errors=self.errors,
            total_tokens=self.usage.total_tokens,
            estimated_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {
            "processed": self.processed,
            "errors": self.errors,
            "total_tokens": self.usage.total_tokens,
            "estimated_cost": f"${self.usage.estimated_cost_usd:.4f}",
        }

    async def _get_unprocessed_events(self, session, limit: int) -> list:
        """Fetch news_events where entities IS NULL."""
        result = await session.execute(
            select(NewsEvent)
            .where(NewsEvent.entities.is_(None))
            .order_by(NewsEvent.published_at.desc().nullslast())
            .limit(limit)
        )
        return result.scalars().all()

    async def _process_event(self, event) -> dict | None:
        """Extract entities from a single news event via LLM."""
        body = (event.body or "")[:3000]  # Truncate for token limits
        if not body and not event.title:
            return None

        prompt = NEWS_PROMPT_TEMPLATE.format(
            title=event.title or "",
            body=body,
        )

        try:
            result = await call_llm(
                prompt=prompt,
                system_message=NEWS_SYSTEM_MESSAGE,
                model="mini",  # News extraction is straightforward
                temperature=0.2,
                max_tokens=1000,
                parse_json=True,
                usage_tracker=self.usage,
            )
            return result if isinstance(result, dict) else None
        except Exception as e:
            self.log.warning("news_llm_failed", event_id=event.id, error=str(e))
            return None

    async def _save_results(self, session, event_id: int, result: dict) -> None:
        """Update news_event with extracted entities, sentiment, magnitude."""
        entities = result.get("entities", {})
        sentiment = result.get("sentiment")
        magnitude = result.get("magnitude")

        # Ensure sentiment is a float
        if sentiment is not None:
            try:
                sentiment = float(sentiment)
            except (ValueError, TypeError):
                sentiment = None

        await session.execute(
            update(NewsEvent)
            .where(NewsEvent.id == event_id)
            .values(
                entities=entities,
                sentiment=sentiment,
                magnitude=magnitude,
            )
        )

    async def _cross_reference_topics(
        self, session, event_id: int, related_topics: list[str]
    ) -> None:
        """Link news event to existing topics via topic_mentions."""
        for slug in related_topics:
            if not slug:
                continue
            # Look up topic by slug
            result = await session.execute(
                select(Topic.id).where(Topic.slug == slug)
            )
            topic_id = result.scalar_one_or_none()
            if topic_id is None:
                continue

            # Check if mention already exists
            existing = await session.execute(
                select(TopicMention.id).where(
                    TopicMention.topic_id == topic_id,
                    TopicMention.news_event_id == event_id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            mention = TopicMention(
                topic_id=topic_id,
                news_event_id=event_id,
                relevance_score=0.7,
                created_at=_utc_naive(),
            )
            session.add(mention)
