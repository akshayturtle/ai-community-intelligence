"""Research processor — orchestrates the full custom market research pipeline.

Steps: keyword expansion → scraping → insight extraction → contact building.
"""

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, func, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import (
    async_session, Post, User, ResearchProject, ResearchInsight, ResearchContact,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

CONCURRENCY = 3
MIN_CONTACT_POSTS = 2


class ResearchProcessor:
    """Full pipeline for a single research project."""

    def __init__(self):
        self.usage = TokenUsage()
        self.log = logger.bind(processor="research_processor")

    async def run(self, project_id: int) -> dict:
        """Execute the full research pipeline for a project."""
        self.log.info("research_pipeline_start", project_id=project_id)

        try:
            # Load project
            async with async_session() as session:
                project = (await session.execute(
                    select(ResearchProject).where(ResearchProject.id == project_id)
                )).scalar_one_or_none()

                if not project:
                    raise ValueError(f"Project {project_id} not found")

            # Step 1: Keyword expansion
            keywords = await self._expand_keywords(project_id, project.initial_terms)

            # Step 2: Scraping
            await self._run_scraper(project_id, keywords)

            # Step 3: Insight extraction
            await self._extract_insights(project_id)

            # Step 4: Contact building
            await self._build_contacts(project_id)

            # Step 5: Finalize
            async with async_session() as session:
                await session.execute(
                    update(ResearchProject)
                    .where(ResearchProject.id == project_id)
                    .values(
                        status="complete",
                        completed_at=datetime.utcnow(),
                    )
                )
                await session.commit()

            self.log.info(
                "research_pipeline_complete",
                project_id=project_id,
                tokens=self.usage.total_tokens,
            )
            return {"status": "complete", "tokens": self.usage.total_tokens}

        except Exception as e:
            self.log.error(
                "research_pipeline_failed",
                project_id=project_id,
                error=str(e),
            )
            async with async_session() as session:
                await session.execute(
                    update(ResearchProject)
                    .where(ResearchProject.id == project_id)
                    .values(status="failed", error_message=str(e)[:2000])
                )
                await session.commit()
            return {"status": "failed", "error": str(e)}

    async def _expand_keywords(
        self, project_id: int, initial_terms: list[str],
    ) -> list[str]:
        """Use LLM to expand initial terms into 15-20 search keywords."""
        self.log.info("expanding_keywords", project_id=project_id)

        async with async_session() as session:
            await session.execute(
                update(ResearchProject)
                .where(ResearchProject.id == project_id)
                .values(status="expanding")
            )
            await session.commit()

        terms_str = ", ".join(initial_terms)
        prompt = f"""Given these seed terms about a concept/product space: [{terms_str}]

Generate 15-20 diverse Reddit search keywords that would find relevant discussions.
Include:
- Direct terms and variations
- Problem-oriented queries (e.g., "best tool for X", "how to solve X")
- Comparison queries (e.g., "X vs Y", "alternatives to X")
- Opinion queries (e.g., "what do you think about X", "experience with X")
- Pain point queries (e.g., "frustrated with X", "problems with X")

Return ONLY a JSON array of strings, no explanation."""

        result = await call_llm(
            prompt=prompt,
            system_message="You generate search keywords for Reddit market research. Return only valid JSON.",
            model="mini",
            parse_json=True,
            usage_tracker=self.usage,
            max_tokens=500,
            temperature=0.7,
        )

        keywords = result if isinstance(result, list) else initial_terms
        # Ensure initial terms are included
        all_keywords = list(dict.fromkeys(initial_terms + keywords))[:20]

        async with async_session() as session:
            await session.execute(
                update(ResearchProject)
                .where(ResearchProject.id == project_id)
                .values(expanded_keywords=all_keywords)
            )
            await session.commit()

        self.log.info("keywords_expanded", project_id=project_id, count=len(all_keywords))
        return all_keywords

    async def _run_scraper(self, project_id: int, keywords: list[str]):
        """Scrape Reddit for all keywords."""
        self.log.info("scraping_start", project_id=project_id)

        async with async_session() as session:
            await session.execute(
                update(ResearchProject)
                .where(ResearchProject.id == project_id)
                .values(status="scraping")
            )
            await session.commit()

        from scrapers.research_scraper import ResearchScraper

        scraper = ResearchScraper()
        total = await scraper.scrape_project(project_id, keywords)

        # Count actual posts in DB for this project
        async with async_session() as session:
            count = (await session.execute(
                select(func.count(Post.id)).where(
                    Post.raw_metadata["source"].astext == "custom_research",
                    Post.raw_metadata["project_id"].astext == str(project_id),
                )
            )).scalar() or 0

            await session.execute(
                update(ResearchProject)
                .where(ResearchProject.id == project_id)
                .values(post_count=count)
            )
            await session.commit()

        self.log.info("scraping_complete", project_id=project_id, posts=count)

    async def _extract_insights(self, project_id: int):
        """Run LLM analysis on collected posts."""
        self.log.info("insight_extraction_start", project_id=project_id)

        async with async_session() as session:
            await session.execute(
                update(ResearchProject)
                .where(ResearchProject.id == project_id)
                .values(status="processing")
            )
            await session.commit()

        # Load top posts by score
        async with async_session() as session:
            result = await session.execute(
                select(Post.title, Post.body, Post.score, Post.subreddit)
                .where(
                    Post.raw_metadata["source"].astext == "custom_research",
                    Post.raw_metadata["project_id"].astext == str(project_id),
                )
                .order_by(Post.score.desc().nullslast())
                .limit(50)
            )
            posts = result.all()

        if not posts:
            self.log.warning("no_posts_for_insights", project_id=project_id)
            # Create empty insight
            async with async_session() as session:
                stmt = pg_insert(ResearchInsight).values(
                    project_id=project_id,
                    discussion_summary="No posts found for this research query.",
                    overall_sentiment="neutral",
                ).on_conflict_do_update(
                    index_elements=["project_id"],
                    set_={"discussion_summary": "No posts found for this research query."},
                )
                await session.execute(stmt)
                await session.commit()
            return

        # Build snippets
        snippets = []
        for p in posts:
            title = (p.title or "")[:100]
            body = (p.body or "")[:300]
            sub = p.subreddit or "?"
            score = p.score or 0
            snippets.append(f"[r/{sub}, score:{score}] {title}\n{body}")

        posts_text = "\n---\n".join(snippets)

        prompt = f"""Analyze these {len(snippets)} Reddit posts about a specific topic/market.

POSTS:
{posts_text}

Extract a comprehensive market research report as JSON:
{{
  "discussion_summary": "2-3 paragraph summary of what people are discussing, their overall sentiment, and key takeaways",
  "overall_sentiment": "positive|negative|mixed",
  "sentiment_breakdown": {{"positive": <pct>, "negative": <pct>, "neutral": <pct>}},
  "products_mentioned": [
    {{"name": "product name", "pros": ["pro1", "pro2"], "cons": ["con1", "con2"], "mention_count": N}}
  ],
  "feature_requests": [
    {{"description": "what users want", "frequency": "common|occasional|rare", "source_count": N}}
  ],
  "unmet_needs": [
    {{"description": "problem with no good solution", "intensity": "high|medium|low", "evidence": "brief quote or summary"}}
  ],
  "key_themes": [
    {{"theme": "theme name", "post_count": N, "sentiment": "positive|negative|mixed"}}
  ]
}}

Be thorough — extract ALL products mentioned with real pros/cons from the posts.
Return ONLY valid JSON."""

        result = await call_llm(
            prompt=prompt,
            system_message="You are a market research analyst extracting structured intelligence from Reddit discussions. Return only valid JSON.",
            model="mini",
            parse_json=True,
            usage_tracker=self.usage,
            max_tokens=3000,
            temperature=0.2,
        )

        if not isinstance(result, dict):
            self.log.warning("insight_llm_parse_failed", project_id=project_id)
            result = {}

        # Upsert insight
        async with async_session() as session:
            stmt = pg_insert(ResearchInsight).values(
                project_id=project_id,
                discussion_summary=result.get("discussion_summary", ""),
                overall_sentiment=result.get("overall_sentiment", "mixed"),
                sentiment_breakdown=result.get("sentiment_breakdown"),
                products_mentioned=result.get("products_mentioned", []),
                feature_requests=result.get("feature_requests", []),
                unmet_needs=result.get("unmet_needs", []),
                key_themes=result.get("key_themes", []),
                raw_llm_response=result,
            ).on_conflict_do_update(
                index_elements=["project_id"],
                set_={
                    "discussion_summary": result.get("discussion_summary", ""),
                    "overall_sentiment": result.get("overall_sentiment", "mixed"),
                    "sentiment_breakdown": result.get("sentiment_breakdown"),
                    "products_mentioned": result.get("products_mentioned", []),
                    "feature_requests": result.get("feature_requests", []),
                    "unmet_needs": result.get("unmet_needs", []),
                    "key_themes": result.get("key_themes", []),
                    "raw_llm_response": result,
                    "calculated_at": func.now(),
                },
            )
            await session.execute(stmt)
            await session.commit()

        self.log.info(
            "insights_extracted",
            project_id=project_id,
            products=len(result.get("products_mentioned", [])),
            themes=len(result.get("key_themes", [])),
        )

    async def _build_contacts(self, project_id: int):
        """Build contact list from users who posted about this research topic."""
        self.log.info("building_contacts", project_id=project_id)

        async with async_session() as session:
            # Group posts by user, get post count and avg score
            result = await session.execute(
                text("""
                    SELECT
                        p.user_id,
                        u.username,
                        u.profile_url,
                        COUNT(*) as post_count,
                        ARRAY_AGG(DISTINCT p.subreddit) FILTER (WHERE p.subreddit IS NOT NULL) as subreddits,
                        ARRAY_AGG(p.id ORDER BY p.score DESC NULLS LAST) as post_ids
                    FROM posts p
                    LEFT JOIN users u ON u.id = p.user_id
                    WHERE p.raw_metadata->>'source' = 'custom_research'
                      AND (p.raw_metadata->>'project_id')::text = :pid
                      AND p.user_id IS NOT NULL
                    GROUP BY p.user_id, u.username, u.profile_url
                    HAVING COUNT(*) >= :min_posts
                    ORDER BY COUNT(*) DESC
                    LIMIT 200
                """),
                {"pid": str(project_id), "min_posts": MIN_CONTACT_POSTS},
            )
            rows = result.all()

        if not rows:
            self.log.info("no_contacts_found", project_id=project_id)
            return

        # Batch insert contacts
        async with async_session() as session:
            for row in rows:
                username = row.username or f"user_{row.user_id}"
                subreddits = row.subreddits or []
                post_ids = (row.post_ids or [])[:10]

                stmt = pg_insert(ResearchContact).values(
                    project_id=project_id,
                    user_id=row.user_id,
                    username=username,
                    platform="reddit",
                    post_count=row.post_count,
                    topics_discussed=subreddits,
                    sample_post_ids=post_ids,
                    profile_url=row.profile_url,
                ).on_conflict_do_update(
                    constraint="uq_rc_project_user",
                    set_={
                        "post_count": row.post_count,
                        "topics_discussed": subreddits,
                        "sample_post_ids": post_ids,
                    },
                )
                await session.execute(stmt)

            await session.commit()

        self.log.info(
            "contacts_built",
            project_id=project_id,
            contact_count=len(rows),
        )
