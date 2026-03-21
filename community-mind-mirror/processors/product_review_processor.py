"""Product Review Processor — synthesizes Reddit posts into structured product reviews.

Groups posts by product (via product_search metadata or product_mentions),
then uses LLM to extract structured review intelligence:
pros, cons, satisfaction, use cases, feature requests, churn reasons, comparisons.
"""

import asyncio
from collections import defaultdict

import structlog
from sqlalchemy import select, func, text

from database.connection import (
    async_session,
    Post,
    ProductMention,
    ProductReview,
    DiscoveredProduct,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

MIN_POSTS_PER_PRODUCT = 5
MAX_POSTS_PER_SYNTHESIS = 30
MAX_SNIPPET_LEN = 300
CONCURRENCY = 3


class ProductReviewProcessor:
    """Synthesizes product reviews from Reddit posts."""

    def __init__(self):
        self.log = logger.bind(processor="product_review_processor")
        self.usage = TokenUsage()
        self.reviews_created = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("product_review_processor_start")

        # Step 1: Gather product-related posts
        product_posts = await self._gather_product_posts()
        self.log.info("products_with_posts", count=len(product_posts))

        # Step 2: Synthesize reviews for products with enough posts
        sem = asyncio.Semaphore(CONCURRENCY)
        tasks = []
        for product_id, data in product_posts.items():
            if len(data["posts"]) >= MIN_POSTS_PER_PRODUCT:
                tasks.append(self._synthesize_with_sem(sem, product_id, data))

        if tasks:
            await asyncio.gather(*tasks)

        self.log.info(
            "product_review_processor_complete",
            reviews=self.reviews_created,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"reviews": self.reviews_created, "errors": self.errors}

    async def _gather_product_posts(self) -> dict:
        """Gather posts by product from product_search metadata and product_mentions."""
        product_posts: dict[int, dict] = {}

        async with async_session() as session:
            # Source 1: Posts from product-targeted Reddit search
            result = await session.execute(
                text("""
                    SELECT p.id, p.title, p.body, p.subreddit, p.score,
                           p.raw_metadata->>'search_query' AS search_query,
                           dp.id AS product_id, dp.canonical_name
                    FROM posts p
                    JOIN discovered_products dp
                        ON LOWER(dp.canonical_name) = LOWER(p.raw_metadata->>'search_query')
                    WHERE p.raw_metadata->>'source' = 'product_search'
                      AND p.body IS NOT NULL
                    ORDER BY p.score DESC
                    LIMIT 5000
                """)
            )
            for row in result.all():
                pid = row.product_id
                if pid not in product_posts:
                    product_posts[pid] = {"name": row.canonical_name, "posts": []}
                product_posts[pid]["posts"].append({
                    "id": row.id,
                    "text": f"{row.title or ''} {row.body or ''}".strip()[:MAX_SNIPPET_LEN],
                    "subreddit": row.subreddit,
                    "score": row.score or 0,
                })

            # Source 2: Posts via product_mentions table
            result = await session.execute(
                text("""
                    SELECT pm.product_id, dp.canonical_name,
                           p.id, p.title, p.body, p.subreddit, p.score
                    FROM product_mentions pm
                    JOIN posts p ON p.id = pm.post_id
                    JOIN discovered_products dp ON dp.id = pm.product_id
                    WHERE p.body IS NOT NULL
                      AND pm.post_id IS NOT NULL
                    ORDER BY p.score DESC
                    LIMIT 5000
                """)
            )
            seen_post_ids: dict[int, set] = defaultdict(set)
            for row in result.all():
                pid = row.product_id
                if pid not in product_posts:
                    product_posts[pid] = {"name": row.canonical_name, "posts": []}
                # Deduplicate
                if row.id in seen_post_ids[pid]:
                    continue
                seen_post_ids[pid].add(row.id)
                product_posts[pid]["posts"].append({
                    "id": row.id,
                    "text": f"{row.title or ''} {row.body or ''}".strip()[:MAX_SNIPPET_LEN],
                    "subreddit": row.subreddit,
                    "score": row.score or 0,
                })

        return product_posts

    async def _synthesize_with_sem(self, sem: asyncio.Semaphore, product_id: int, data: dict):
        async with sem:
            await self._synthesize_review(product_id, data)

    async def _synthesize_review(self, product_id: int, data: dict):
        """Use LLM to synthesize posts into a structured product review."""
        product_name = data["name"]
        posts = sorted(data["posts"], key=lambda p: p["score"], reverse=True)[:MAX_POSTS_PER_SYNTHESIS]

        posts_text = "\n".join(
            f"- [r/{p['subreddit'] or '?'}] (score:{p['score']}) {p['text'][:200]}"
            for p in posts
        )
        subreddits = list(set(p["subreddit"] for p in posts if p["subreddit"]))

        prompt = f"""Analyze these {len(posts)} Reddit posts about "{product_name}":

{posts_text}

Extract a structured product review. Return JSON:
{{
  "overall_sentiment": "positive" | "negative" | "mixed",
  "satisfaction_score": 0-100,
  "pros": ["strength 1", "strength 2", ...],
  "cons": ["weakness 1", "weakness 2", ...],
  "common_use_cases": ["use case 1", ...],
  "feature_requests": ["requested feature 1", ...],
  "churn_reasons": ["reason people stop using it 1", ...],
  "competitor_comparisons": [{{"competitor": "name", "context": "how they compare"}}]
}}

Rules:
- Base everything on what the posts actually say, not general knowledge
- If there aren't enough signals for a field, return an empty list
- Keep each item concise (one sentence max)
- satisfaction_score: 0=terrible, 50=mixed, 100=loved"""

        try:
            result = await call_llm(
                prompt=prompt,
                system_message="You are a product review analyst extracting user sentiment from community discussions.",
                model="mini",
                parse_json=True,
                usage_tracker=self.usage,
                max_tokens=1500,
                temperature=0.2,
            )

            if not isinstance(result, dict) or "overall_sentiment" not in result:
                self.log.warning("invalid_review_response", product=product_name)
                return

            # Upsert into product_reviews
            async with async_session() as session:
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = pg_insert(ProductReview).values(
                    product_id=product_id,
                    product_name=product_name,
                    overall_sentiment=result.get("overall_sentiment", "mixed"),
                    satisfaction_score=result.get("satisfaction_score", 50),
                    pros=result.get("pros", []),
                    cons=result.get("cons", []),
                    common_use_cases=result.get("common_use_cases", []),
                    feature_requests=result.get("feature_requests", []),
                    churn_reasons=result.get("churn_reasons", []),
                    competitor_comparisons=result.get("competitor_comparisons", []),
                    post_count=len(posts),
                    sample_post_ids=[p["id"] for p in posts[:10]],
                    source_subreddits=subreddits,
                ).on_conflict_do_update(
                    index_elements=["product_id"],
                    set_={
                        "overall_sentiment": result.get("overall_sentiment", "mixed"),
                        "satisfaction_score": result.get("satisfaction_score", 50),
                        "pros": result.get("pros", []),
                        "cons": result.get("cons", []),
                        "common_use_cases": result.get("common_use_cases", []),
                        "feature_requests": result.get("feature_requests", []),
                        "churn_reasons": result.get("churn_reasons", []),
                        "competitor_comparisons": result.get("competitor_comparisons", []),
                        "post_count": len(posts),
                        "sample_post_ids": [p["id"] for p in posts[:10]],
                        "source_subreddits": subreddits,
                        "updated_at": func.now(),
                    },
                )
                await session.execute(stmt)
                await session.commit()
                self.reviews_created += 1
                self.log.debug("review_synthesized", product=product_name, posts=len(posts))

        except Exception as e:
            self.errors += 1
            self.log.warning("review_synthesis_failed", product=product_name, error=str(e))
