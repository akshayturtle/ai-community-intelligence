"""Sentiment analyzer — uses VADER for fast, free bulk sentiment scoring."""

import json

import structlog
from sqlalchemy import select, update
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from database.connection import async_session, Post, TopicMention
from scrapers.base_scraper import _utc_naive

logger = structlog.get_logger()


class SentimentAnalyzer:
    """Scores post sentiment using VADER (no LLM, no API key needed)."""

    BATCH_SIZE = 500

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()
        self.log = logger.bind(processor="sentiment_analyzer")
        self.processed = 0
        self.errors = 0

    async def run(self) -> dict:
        """Main entry point. Returns summary stats."""
        self.log.info("sentiment_start")

        while True:
            async with async_session() as session:
                posts = await self._get_unprocessed_posts(session, self.BATCH_SIZE)

            if not posts:
                break

            await self._process_batch(posts)
            self.log.info("sentiment_batch_done", processed=self.processed, errors=self.errors)

        self.log.info("sentiment_complete", processed=self.processed, errors=self.errors)
        return {"processed": self.processed, "errors": self.errors}

    async def _get_unprocessed_posts(self, session, limit: int) -> list:
        """Fetch posts that don't have sentiment in raw_metadata yet."""
        result = await session.execute(
            select(Post.id, Post.title, Post.body, Post.raw_metadata)
            .where(
                (Post.raw_metadata.is_(None))
                | (~Post.raw_metadata.has_key("sentiment"))
            )
            .order_by(Post.id)
            .limit(limit)
        )
        return result.all()

    def _analyze(self, text: str) -> dict:
        """Run VADER on text. Returns scores + label."""
        scores = self.vader.polarity_scores(text)
        if scores["compound"] >= 0.05:
            label = "positive"
        elif scores["compound"] <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        return {
            "compound": round(scores["compound"], 4),
            "pos": round(scores["pos"], 4),
            "neg": round(scores["neg"], 4),
            "neu": round(scores["neu"], 4),
            "label": label,
        }

    async def _process_batch(self, posts: list) -> None:
        """Analyze sentiment for a batch of posts and update the database."""
        async with async_session() as session:
            for post in posts:
                try:
                    post_id, title, body, raw_metadata = post

                    # Combine title + body for analysis
                    text = ""
                    if title:
                        text += title + " "
                    if body:
                        text += body
                    text = text.strip()

                    if not text:
                        continue

                    sentiment = self._analyze(text[:5000])  # Cap very long texts

                    # Merge sentiment into existing raw_metadata
                    metadata = dict(raw_metadata) if raw_metadata else {}
                    metadata["sentiment"] = sentiment

                    await session.execute(
                        update(Post)
                        .where(Post.id == post_id)
                        .values(raw_metadata=metadata)
                    )

                    # Update topic_mentions if any exist for this post
                    await session.execute(
                        update(TopicMention)
                        .where(TopicMention.post_id == post_id)
                        .values(sentiment=sentiment["compound"])
                    )

                    self.processed += 1
                except Exception as e:
                    self.errors += 1
                    self.log.warning("sentiment_item_failed", post_id=post[0], error=str(e))
                    continue

            await session.commit()
