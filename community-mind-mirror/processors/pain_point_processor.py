"""Pain Point Synthesizer — extracts community frustrations and unresolved problems.

Layer 1: Complaint pattern regex detection
Layer 2: Filter by negative sentiment, cluster by similarity
Layer 3: LLM synthesizes clusters into titled pain points
"""

import re
from collections import defaultdict
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import (
    async_session,
    Post,
    PainPoint,
    DiscoveredProduct,
    Platform,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

COMPLAINT_PATTERNS = [
    r"(?i)(frustrat|annoy|terrible|awful|broken|sucks|hate|worst|nightmare|impossible)",
    r"(?i)(can't figure out|no good way to|wish there was|someone needs to build)",
    r"(?i)(why is .+ so hard|why can't .+ just|there's no good .+ for)",
    r"(?i)(been struggling with|spent hours trying|gave up on)",
    r"(?i)(any alternative|better option|recommend .+ for)",
]


def is_complaint(text: str) -> bool:
    for pattern in COMPLAINT_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


class PainPointProcessor:
    """Finds and synthesizes community pain points."""

    def __init__(self):
        self.log = logger.bind(processor="pain_point_processor")
        self.usage = TokenUsage()
        self.pain_points_found = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("pain_point_processor_start")

        # Step 1: Find complaint posts from last 30 days
        complaints = await self._find_complaints()
        self.log.info("complaints_found", count=len(complaints))

        if len(complaints) < 3:
            self.log.info("not_enough_complaints")
            return {"pain_points": 0, "errors": 0}

        # Step 2: Group by rough keyword similarity
        clusters = self._cluster_complaints(complaints)
        self.log.info("clusters_formed", count=len(clusters))

        # Step 3: LLM synthesize each cluster (min 2 posts)
        for cluster_posts in clusters:
            if len(cluster_posts) < 2:
                continue
            await self._synthesize_cluster(cluster_posts)

        self.log.info(
            "pain_point_processor_complete",
            pain_points=self.pain_points_found,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"pain_points": self.pain_points_found, "errors": self.errors}

    async def _find_complaints(self) -> list[dict]:
        """Find posts matching complaint patterns with negative sentiment."""
        cutoff = datetime.utcnow() - timedelta(days=30)

        async with async_session() as session:
            # Get platform names for display
            platforms = await session.execute(select(Platform.id, Platform.name))
            platform_map = {r.id: r.name for r in platforms.all()}

            result = await session.execute(
                select(Post.id, Post.title, Post.body, Post.platform_id, Post.raw_metadata)
                .where(Post.posted_at >= cutoff)
                .where(Post.body.isnot(None))
                .order_by(Post.score.desc())
                .limit(5000)
            )
            posts = result.all()

        complaints = []
        for post_id, title, body, platform_id, raw_metadata in posts:
            text = f"{title or ''} {body or ''}".strip()
            if not text:
                continue

            # Check complaint pattern first (more inclusive)
            if not is_complaint(text):
                continue

            # Allow posts with negative or missing sentiment through
            sentiment = None
            if raw_metadata and "sentiment" in raw_metadata:
                sentiment = raw_metadata["sentiment"].get("compound", 0)
            # Skip only clearly positive posts
            if sentiment is not None and sentiment > 0.1:
                continue

            complaints.append({
                "id": post_id,
                "text": text[:500],
                "platform": platform_map.get(platform_id, "unknown"),
                "sentiment": sentiment,
            })

        return complaints

    def _cluster_complaints(self, complaints: list[dict]) -> list[list[dict]]:
        """Simple keyword-based clustering (no sklearn needed)."""
        # Extract key phrases and group by common terms
        clusters: dict[str, list[dict]] = defaultdict(list)

        for complaint in complaints:
            text_lower = complaint["text"].lower()
            assigned = False
            for keyword in [
                # Core AI frustrations
                "hallucin", "context window", "context length", "token limit",
                "rate limit", "rate_limit", "throttl",
                "pricing", "cost", "expensive", "billing",
                "latency", "slow", "timeout", "performance",
                "memory", "out of memory", "oom", "ram",
                # Quality & reliability
                "accuracy", "incorrect", "wrong answer", "unreliable",
                "inconsisten", "regression", "downgrad", "quality",
                # Development pain
                "documentation", "docs", "undocument",
                "api", "sdk", "breaking change", "deprecat",
                "deploy", "hosting", "scale", "scaling",
                "debug", "error", "crash", "bug",
                "auth", "login", "permission", "security",
                # AI/ML specific
                "fine-tun", "training", "finetuning",
                "prompt", "prompt engineer", "instruction",
                "embed", "vector", "retrieval", "rag",
                "agent", "workflow", "automat",
                "gpu", "inference", "cuda", "compute",
                "model", "weight", "checkpoint",
                # Tools & ecosystem
                "cursor", "copilot", "chatgpt", "claude",
                "langchain", "openai", "ollama",
                "integration", "plugin", "extension",
                "open source", "license", "censorship", "filter",
                # Career/industry
                "job", "hiring", "layoff", "interview", "salary",
            ]:
                if keyword in text_lower:
                    clusters[keyword].append(complaint)
                    assigned = True
                    # Don't break — let posts match multiple clusters

            if not assigned:
                clusters["other"].append(complaint)

        # Filter out small clusters and return as list
        return [posts for posts in clusters.values() if len(posts) >= 2]

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Lowercase, strip punctuation, collapse whitespace for comparison."""
        import string
        t = title.lower().strip()
        t = t.translate(str.maketrans("", "", string.punctuation))
        return " ".join(t.split())

    @staticmethod
    def _titles_are_similar(a: str, b: str) -> bool:
        """Check if two normalized titles are similar enough to be duplicates.

        Uses word-overlap ratio (Jaccard similarity on words).
        Threshold of 0.5 catches paraphrases like
        'AI content quality degradation' vs 'degradation of AI content quality'.
        """
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        intersection = words_a & words_b
        union = words_a | words_b
        jaccard = len(intersection) / len(union)
        return jaccard >= 0.5

    async def _synthesize_cluster(self, posts: list[dict]):
        """Use LLM to synthesize a cluster of complaints into a pain point."""
        posts_text = "\n".join(
            f"- [{p['platform']}] {p['text'][:200]}" for p in posts[:20]
        )
        platforms = list(set(p["platform"] for p in posts))

        prompt = f"""Here are {len(posts)} community posts that express frustration about similar problems:

{posts_text}

Synthesize these into a single pain point:
1. A clear title for the problem (in quotes, like a headline)
2. A 1-2 sentence description of the core issue
3. An intensity score from 0-100 based on: frequency of complaints × emotional intensity × lack of existing solutions
4. Whether any solution/product was mentioned in the replies

Return JSON:
{{
  "title": "...",
  "description": "...",
  "intensity_score": 0,
  "has_solution": false,
  "mentioned_products": []
}}"""

        try:
            result = await call_llm(
                prompt=prompt,
                system_message="You are a product strategist analyzing community frustrations.",
                model="mini",
                parse_json=True,
                usage_tracker=self.usage,
                max_tokens=500,
            )

            if not isinstance(result, dict) or "title" not in result:
                return

            async with async_session() as session:
                # Check if similar pain point already exists (fuzzy match)
                # Pull active pain points and compare normalized titles
                existing_result = await session.execute(
                    select(PainPoint.id, PainPoint.title)
                    .where(PainPoint.status == "active")
                )
                existing_rows = existing_result.all()
                new_title_norm = self._normalize_title(result["title"])
                for existing_id, existing_title in existing_rows:
                    if self._titles_are_similar(new_title_norm, self._normalize_title(existing_title)):
                        self.log.debug(
                            "pain_point_duplicate_skipped",
                            new_title=result["title"],
                            existing_title=existing_title,
                        )
                        return

                session.add(PainPoint(
                    title=result["title"],
                    description=result.get("description", ""),
                    intensity_score=result.get("intensity_score", 50),
                    has_solution=result.get("has_solution", False),
                    mentioned_products=result.get("mentioned_products", []),
                    platforms=platforms,
                    post_count=len(posts),
                ))
                await session.commit()
                self.pain_points_found += 1

        except Exception as e:
            self.errors += 1
            self.log.warning("pain_point_synthesis_failed", error=str(e))
