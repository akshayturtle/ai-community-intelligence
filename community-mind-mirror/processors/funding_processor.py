"""Funding Analyzer — extracts structured funding data and community reactions.

Layer 1: Regex extraction of amounts, stages, company names from news
Layer 1: Cross-reference with community posts within 7 days
Layer 3: LLM generates reaction summary
"""

import re
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, func, or_

from database.connection import (
    async_session,
    NewsEvent,
    Post,
    FundingRound,
    Platform,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

FUNDING_PATTERNS = [
    r"(?i)raised?\s+\$([\d\.]+)\s?([BMK](?:illion)?)",
    r"(?i)(series [A-F])",
    r"(?i)(seed round|pre.?seed)",
    r"(?i)(funding round)",
    r"(?i)valuation of \$([\d\.]+)\s?([BMK](?:illion)?)",
]


def extract_amount(text: str) -> str | None:
    match = re.search(r"\$([\d\.]+)\s?([BMK](?:illion)?)", text, re.IGNORECASE)
    if match:
        return f"${match.group(1)}{match.group(2)[0].upper()}"
    return None


def extract_stage(text: str) -> str | None:
    match = re.search(r"(?i)(seed|pre.?seed|series [A-F]|growth|bridge|IPO)", text)
    return match.group(0).title() if match else None


def extract_company(text: str) -> str | None:
    """Try to extract company name from news title."""
    # Common patterns: "CompanyName raises $X", "CompanyName secures $X"
    match = re.match(r"^([A-Z][a-zA-Z0-9\s\.]+?)(?:\s+raises?|\s+secures?|\s+closes?|\s+announces?)", text)
    if match:
        return match.group(1).strip()
    # Fallback: first capitalized word/phrase before a verb
    match = re.match(r"^([A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)*)", text)
    if match:
        name = match.group(1).strip()
        if len(name) > 2 and name not in ("The", "A", "An", "New", "Breaking"):
            return name
    return None


class FundingProcessor:
    """Extracts funding rounds and community reactions."""

    def __init__(self):
        self.log = logger.bind(processor="funding_processor")
        self.usage = TokenUsage()
        self.rounds_found = 0
        self.errors = 0

    async def _find_funding_news(self) -> list[dict]:
        """Find news events about funding rounds."""
        cutoff = datetime.utcnow() - timedelta(days=90)

        async with async_session() as session:
            # Get news that mention funding keywords
            result = await session.execute(
                select(NewsEvent.id, NewsEvent.title, NewsEvent.body,
                       NewsEvent.published_at, NewsEvent.sentiment,
                       NewsEvent.source_name)
                .where(NewsEvent.published_at >= cutoff)
                .where(NewsEvent.source_type == "news")
                .where(
                    or_(
                        NewsEvent.title.ilike("%raised%"),
                        NewsEvent.title.ilike("%funding%"),
                        NewsEvent.title.ilike("%series %"),
                        NewsEvent.title.ilike("%seed round%"),
                        NewsEvent.title.ilike("%valuation%"),
                        NewsEvent.title.ilike("%million%"),
                        NewsEvent.title.ilike("%billion%"),
                    )
                )
                .order_by(NewsEvent.published_at.desc())
                .limit(100)
            )
            return [
                {
                    "id": r.id,
                    "title": r.title,
                    "body": r.body or "",
                    "published_at": r.published_at,
                    "sentiment": r.sentiment,
                    "source_name": r.source_name,
                }
                for r in result.all()
            ]

    async def _extract_with_llm(self, headlines: list[dict]) -> dict:
        """Batch extract company names from headlines using LLM."""
        if not headlines:
            return {}
        items = "\n".join(f"{i+1}. {h['title']}" for i, h in enumerate(headlines))
        try:
            result = await call_llm(
                prompt=f"""Extract the company name from each funding headline.
Return a JSON object mapping the headline number to the company name.
If you can't determine the company, use null.

Headlines:
{items}

Return JSON like: {{"1": "CompanyName", "2": "AnotherCo", "3": null}}""",
                system_message="You extract company names from news headlines. Return only clean company names, not article titles.",
                model="mini",
                parse_json=True,
                usage_tracker=self.usage,
                max_tokens=500,
            )
            if isinstance(result, dict):
                return {int(k): v for k, v in result.items() if v}
        except Exception as e:
            self.log.warning("llm_extract_failed", error=str(e))
        return {}

    async def run(self) -> dict:
        self.log.info("funding_processor_start")

        funding_news = await self._find_funding_news()
        self.log.info("funding_news_found", count=len(funding_news))

        # Batch LLM extraction for headlines where regex fails
        needs_llm = []
        for news in funding_news:
            company = extract_company(news["title"])
            if not company or len(company) > 50:
                needs_llm.append(news)

        llm_names = {}
        if needs_llm:
            # Process in batches of 20
            for i in range(0, len(needs_llm), 20):
                batch = needs_llm[i:i+20]
                batch_result = await self._extract_with_llm(batch)
                for j, news in enumerate(batch):
                    if (j + 1) in batch_result:
                        llm_names[news["id"]] = batch_result[j + 1]

        for news in funding_news:
            await self._process_funding_event(news, llm_names.get(news["id"]))

        self.log.info(
            "funding_processor_complete",
            rounds=self.rounds_found,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"rounds_found": self.rounds_found, "errors": self.errors}

    async def _process_funding_event(self, news: dict, llm_company: str | None = None):
        """Process a single funding news event."""
        try:
            text = f"{news['title']} {news['body'][:500]}"
            amount = extract_amount(text)
            stage = extract_stage(text)
            company = llm_company or extract_company(news["title"])

            if not company or len(company) > 60:
                return

            # Check if already processed
            async with async_session() as session:
                existing = await session.execute(
                    select(FundingRound.id)
                    .where(FundingRound.news_event_id == news["id"])
                )
                if existing.scalar():
                    return

            # Cross-reference with community posts
            community_data = await self._get_community_reaction(company, news["published_at"])

            # Get LLM summary if we have community reactions
            reaction_summary = None
            if community_data["post_count"] > 2:
                reaction_summary = await self._get_reaction_summary(
                    company, amount or "undisclosed", stage or "unknown",
                    community_data["sample_posts"]
                )

            # Extract sector from news entities or categories
            sector = None
            if news.get("body"):
                for s in ["AI", "robotics", "fintech", "biotech", "crypto", "SaaS", "healthtech", "edtech"]:
                    if s.lower() in text.lower():
                        sector = s
                        break

            async with async_session() as session:
                session.add(FundingRound(
                    company_name=company,
                    amount=amount,
                    stage=stage,
                    sector=sector,
                    news_event_id=news["id"],
                    community_sentiment=community_data["avg_sentiment"],
                    community_post_count=community_data["post_count"],
                    reaction_summary=reaction_summary,
                    announced_at=news["published_at"],
                ))
                await session.commit()
                self.rounds_found += 1

        except Exception as e:
            self.errors += 1
            self.log.warning("funding_process_error", news_id=news["id"], error=str(e))

    async def _get_community_reaction(self, company: str, announced_at) -> dict:
        """Find community posts about a company around announcement date."""
        if not announced_at:
            return {"post_count": 0, "avg_sentiment": None, "sample_posts": []}

        window_start = announced_at - timedelta(days=1)
        window_end = announced_at + timedelta(days=7)

        async with async_session() as session:
            result = await session.execute(
                select(Post.body, Post.raw_metadata, Post.score)
                .where(Post.posted_at >= window_start)
                .where(Post.posted_at <= window_end)
                .where(Post.body.ilike(f"%{company}%"))
                .order_by(Post.score.desc())
                .limit(20)
            )
            posts = result.all()

        sentiments = []
        sample_posts = []
        for body, metadata, score in posts:
            if metadata and "sentiment" in metadata:
                s = metadata["sentiment"].get("compound")
                if s is not None:
                    sentiments.append(float(s))
            if body:
                sample_posts.append(body[:200])

        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None

        return {
            "post_count": len(posts),
            "avg_sentiment": round(avg_sentiment, 4) if avg_sentiment is not None else None,
            "sample_posts": sample_posts[:5],
        }

    async def _get_reaction_summary(
        self, company: str, amount: str, stage: str, sample_posts: list[str]
    ) -> str | None:
        """LLM generates a one-sentence reaction summary."""
        try:
            posts_text = "\n".join(f"- {p}" for p in sample_posts)
            result = await call_llm(
                prompt=f"""Company "{company}" just raised {amount} ({stage}).

Here are community posts reacting to this news:
{posts_text}

Write a one-sentence summary of the community reaction in this format:
'Community: "[dominant reaction]." Skeptics: "[main criticism]."'

Return just the summary string, nothing else.""",
                system_message="You are a community intelligence analyst.",
                model="mini",
                usage_tracker=self.usage,
                max_tokens=150,
            )
            return result.strip().strip('"') if isinstance(result, str) else None
        except Exception:
            return None
