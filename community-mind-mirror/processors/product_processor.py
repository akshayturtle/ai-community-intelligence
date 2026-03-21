"""Product Discovery & Mention Tracking processor.

Layer 1: Regex matching against discovered_products registry
Layer 2: spaCy NER for unknown entity candidates (optional, degrades gracefully)
Layer 3: LLM batch to validate unknowns and discover new products
Also classifies mention context: recommendation, complaint, comparison, mention
"""

import json
import re
from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, update, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import (
    async_session,
    Post,
    NewsEvent,
    DiscoveredProduct,
    ProductMention,
    Platform,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

# ---- Seed products (inserted on first run) ----
# Non-tech categories and terms to block from discovery
PRODUCT_BLOCKLIST = {
    # Non-tech products
    "toothbrush", "chair", "laundry", "furniture", "kitchen", "mattress",
    "pillow", "blanket", "shampoo", "soap", "candle", "perfume", "shoes",
    "jacket", "shirt", "pants", "bag", "wallet", "watch", "ring",
    # Generic terms
    "course", "tutorial", "bootcamp", "newsletter", "podcast", "blog",
    "book", "ebook", "magazine", "workshop", "webinar", "conference",
    # Too generic
    "pro", "plus", "premium", "enterprise", "studio", "cloud", "hub",
    "platform", "assistant", "agent", "copilot ai",
}

# Categories that indicate non-tech (reject these)
BLOCKED_CATEGORIES = {"other", "consumer_goods", "lifestyle", "food", "fashion"}

SEED_PRODUCTS = [
    {"name": "Cursor", "category": "ai_coding", "aliases": ["cursor ai", "cursor editor"]},
    {"name": "OpenAI", "category": "llm_provider", "aliases": ["openai", "open ai"]},
    {"name": "Claude", "category": "llm_provider", "aliases": ["claude ai", "anthropic claude"]},
    {"name": "ChatGPT", "category": "llm_provider", "aliases": ["chatgpt", "chat gpt"]},
    {"name": "CrewAI", "category": "agent_framework", "aliases": ["crewai", "crew ai"]},
    {"name": "LangChain", "category": "agent_framework", "aliases": ["langchain", "lang chain"]},
    {"name": "AutoGen", "category": "agent_framework", "aliases": ["autogen", "auto gen"]},
    {"name": "Supabase", "category": "database", "aliases": ["supabase"]},
    {"name": "Vercel", "category": "deployment", "aliases": ["vercel", "vercel v0", "v0.dev"]},
    {"name": "Hugging Face", "category": "ml_platform", "aliases": ["huggingface", "hugging face", "hf"]},
    {"name": "Ollama", "category": "local_inference", "aliases": ["ollama"]},
    {"name": "LlamaIndex", "category": "rag_framework", "aliases": ["llamaindex", "llama index"]},
    {"name": "Copilot", "category": "ai_coding", "aliases": ["github copilot", "copilot"]},
    {"name": "Midjourney", "category": "ai_image", "aliases": ["midjourney", "mid journey"]},
    {"name": "Stable Diffusion", "category": "ai_image", "aliases": ["stable diffusion", "sd", "sdxl"]},
    {"name": "GPT-4", "category": "llm_model", "aliases": ["gpt-4", "gpt4", "gpt-4o", "gpt4o"]},
    {"name": "Llama", "category": "llm_model", "aliases": ["llama", "llama 3", "llama3", "llama 4"]},
    {"name": "Mistral", "category": "llm_model", "aliases": ["mistral", "mistral ai", "mixtral"]},
    {"name": "Gemini", "category": "llm_model", "aliases": ["gemini", "google gemini"]},
    {"name": "DeepSeek", "category": "llm_model", "aliases": ["deepseek", "deep seek"]},
]

# ---- Context classification patterns ----
RECOMMENDATION_PATTERNS = [
    r"(?i)(I recommend|you should (?:try|use)|try using|go with|best .+ is|switched to .+ and love)",
    r"(?i)(highly recommend|can't recommend .+ enough|game.?changer|life.?saver)",
    r"(?i)(we use .+ in production|been using .+ for months|solved .+ with)",
    r"(?i)(loving .+ so far|impressed with|blown away by)",
    r"(?i)(10/10|chef.?s kiss|no.?brainer|must.?have)",
]

COMPLAINT_PATTERNS = [
    r"(?i)(don't use|stay away from|terrible experience|waste of (?:time|money)|overpriced|overhyped)",
    r"(?i)(switched away from|dumped|dropped .+ because|frustrated with|given up on)",
    r"(?i)(broken|buggy|unreliable|constantly (?:crashes|fails)|deal.?breaker|unusable)",
    r"(?i)(regret (?:using|buying|paying)|wish I hadn't|learned the hard way)",
    r"(?i)(worst .+ I've (?:used|tried)|save yourself|do yourself a favor and avoid)",
]

COMPARISON_PATTERNS = [
    r"(?i)(.+?) vs\.? (.+?)[\s\.\,\!\?]",
    r"(?i)compared to (.+?)[\s\.\,]",
    r"(?i)choosing between (.+?) and (.+)",
    r"(?i)(.+?) alternative",
]


class ProductProcessor:
    """Discovers products and tracks mentions across posts and news."""

    BATCH_SIZE = 200

    def __init__(self):
        self.log = logger.bind(processor="product_processor")
        self.usage = TokenUsage()
        self.products_discovered = 0
        self.mentions_recorded = 0
        self.errors = 0
        self._registry_cache: list[dict] | None = None

    async def run(self) -> dict:
        """Main entry point."""
        self.log.info("product_processor_start")

        # Step 1: Seed products if table is empty
        await self._seed_products()

        # Step 2: Load product registry
        registry = await self._load_registry()
        self.log.info("registry_loaded", products=len(registry))

        # Step 3: Scan unprocessed posts for product mentions
        await self._scan_posts(registry)

        # Step 4: Scan unprocessed news for product mentions
        await self._scan_news(registry)

        # Step 5: LLM discovery on recent posts (find new products)
        await self._llm_discover_products(registry)

        # Step 6: Update mention counts on discovered_products
        await self._update_mention_counts()

        self.log.info(
            "product_processor_complete",
            discovered=self.products_discovered,
            mentions=self.mentions_recorded,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {
            "discovered": self.products_discovered,
            "mentions": self.mentions_recorded,
            "errors": self.errors,
        }

    async def _seed_products(self):
        """Insert seed products if the table is empty."""
        async with async_session() as session:
            count = (await session.execute(
                select(func.count(DiscoveredProduct.id))
            )).scalar()

            if count > 0:
                return

            self.log.info("seeding_products", count=len(SEED_PRODUCTS))
            for p in SEED_PRODUCTS:
                session.add(DiscoveredProduct(
                    canonical_name=p["name"],
                    category=p["category"],
                    aliases=p["aliases"],
                    discovered_by="seed",
                    confidence=1.0,
                ))
            await session.commit()
            self.products_discovered += len(SEED_PRODUCTS)

    async def _load_registry(self) -> list[dict]:
        """Load all active products from DB."""
        async with async_session() as session:
            result = await session.execute(
                select(
                    DiscoveredProduct.id,
                    DiscoveredProduct.canonical_name,
                    DiscoveredProduct.aliases,
                    DiscoveredProduct.category,
                )
                .where(DiscoveredProduct.status == "active")
                .where(DiscoveredProduct.confidence >= 0.7)
            )
            rows = result.all()

        registry = []
        for row in rows:
            registry.append({
                "id": row.id,
                "canonical_name": row.canonical_name,
                "aliases": row.aliases or [],
                "category": row.category,
            })
        self._registry_cache = registry
        return registry

    def _detect_products(self, text: str, registry: list[dict]) -> list[dict]:
        """Match text against the dynamic product registry."""
        text_lower = text.lower()
        found = []
        seen_ids = set()

        for product in registry:
            if product["id"] in seen_ids:
                continue

            # Check canonical name
            name_lower = product["canonical_name"].lower()
            if name_lower in text_lower:
                found.append(product)
                seen_ids.add(product["id"])
                continue

            # Check aliases
            for alias in product.get("aliases", []):
                if alias.lower() in text_lower:
                    found.append(product)
                    seen_ids.add(product["id"])
                    break

        return found

    def _classify_context(self, text: str, product_name: str) -> str:
        """Classify how a product is being discussed."""
        # Get relevant sentences
        sentences = text.split(".")
        relevant = [s for s in sentences if product_name.lower() in s.lower()]
        context_text = " ".join(relevant) if relevant else text

        for pattern in RECOMMENDATION_PATTERNS:
            if re.search(pattern, context_text):
                return "recommendation"
        for pattern in COMPLAINT_PATTERNS:
            if re.search(pattern, context_text):
                return "complaint"
        for pattern in COMPARISON_PATTERNS:
            if re.search(pattern, context_text):
                return "comparison"
        return "mention"

    async def _scan_posts(self, registry: list[dict]):
        """Scan posts for product mentions."""
        offset = 0
        while True:
            async with async_session() as session:
                # Get posts that haven't been scanned for products yet
                result = await session.execute(
                    select(Post.id, Post.title, Post.body, Post.raw_metadata)
                    .where(
                        (Post.raw_metadata.is_(None))
                        | (~Post.raw_metadata.has_key("products_scanned"))
                    )
                    .order_by(Post.id)
                    .limit(self.BATCH_SIZE)
                )
                posts = result.all()

            if not posts:
                break

            async with async_session() as session:
                for post in posts:
                    try:
                        post_id, title, body, raw_metadata = post
                        text = f"{title or ''} {body or ''}".strip()
                        if not text:
                            continue

                        found = self._detect_products(text, registry)
                        sentiment = None
                        if raw_metadata and "sentiment" in raw_metadata:
                            sentiment = raw_metadata["sentiment"].get("compound")

                        for product in found:
                            context = self._classify_context(text, product["canonical_name"])
                            stmt = pg_insert(ProductMention).values(
                                product_id=product["id"],
                                post_id=post_id,
                                context_type=context,
                                sentiment=sentiment,
                            ).on_conflict_do_nothing()
                            await session.execute(stmt)
                            self.mentions_recorded += 1

                        # Mark post as scanned
                        metadata = dict(raw_metadata) if raw_metadata else {}
                        metadata["products_scanned"] = True
                        await session.execute(
                            update(Post).where(Post.id == post_id).values(raw_metadata=metadata)
                        )
                    except Exception as e:
                        self.errors += 1
                        self.log.warning("post_scan_error", post_id=post[0], error=str(e))

                await session.commit()

            offset += self.BATCH_SIZE
            self.log.info("posts_scanned", offset=offset, mentions=self.mentions_recorded)

    async def _scan_news(self, registry: list[dict]):
        """Scan news events for product mentions."""
        async with async_session() as session:
            result = await session.execute(
                select(NewsEvent.id, NewsEvent.title, NewsEvent.body, NewsEvent.sentiment)
                .where(
                    (NewsEvent.raw_metadata.is_(None))
                    | (~NewsEvent.raw_metadata.has_key("products_scanned"))
                )
                .order_by(NewsEvent.id)
                .limit(1000)
            )
            news_items = result.all()

        if not news_items:
            return

        async with async_session() as session:
            for item in news_items:
                try:
                    ne_id, title, body, sentiment = item
                    text = f"{title or ''} {body or ''}".strip()
                    if not text:
                        continue

                    found = self._detect_products(text, registry)
                    for product in found:
                        context = self._classify_context(text, product["canonical_name"])
                        stmt = pg_insert(ProductMention).values(
                            product_id=product["id"],
                            news_event_id=ne_id,
                            context_type=context,
                            sentiment=sentiment,
                        ).on_conflict_do_nothing()
                        await session.execute(stmt)
                        self.mentions_recorded += 1

                    # Mark as scanned
                    await session.execute(
                        text("UPDATE news_events SET raw_metadata = COALESCE(raw_metadata, '{}'::jsonb) || :patch WHERE id = :id"),
                        {"patch": json.dumps({"products_scanned": True}), "id": ne_id},
                    )
                except Exception as e:
                    self.errors += 1

            await session.commit()
            self.log.info("news_scanned", items=len(news_items))

    async def _llm_discover_products(self, registry: list[dict]):
        """Use LLM to discover new products from recent posts."""
        known_names = {p["canonical_name"] for p in registry}

        # Get recent high-engagement posts
        async with async_session() as session:
            result = await session.execute(
                select(Post.id, Post.title, Post.body)
                .where(Post.posted_at >= datetime.utcnow() - timedelta(days=7))
                .where(Post.score > 5)
                .order_by(Post.score.desc())
                .limit(50)
            )
            posts = result.all()

        if len(posts) < 10:
            self.log.info("not_enough_posts_for_discovery", count=len(posts))
            return

        posts_text = []
        for _, title, body in posts:
            snippet = f"{title or ''}: {(body or '')[:300]}"
            posts_text.append(snippet)

        known_list = ", ".join(sorted(known_names))

        prompt = f"""You are analyzing posts from AI/tech communities to discover SOFTWARE products,
developer tools, frameworks, libraries, APIs, and tech services being discussed.

Here are 50 recent posts:
{chr(10).join(f'- {p}' for p in posts_text)}

The following products are ALREADY KNOWN to us (do not include these):
{known_list}

Identify ALL NEW software products, developer tools, frameworks, libraries,
APIs, platforms, and tech services mentioned in these posts that are NOT in the known list.

For each NEW product found:
- name: the canonical name with correct casing
- category: one of [ai_coding, agent_framework, llm_provider, llm_model, vector_db,
  database, ai_builder, devtool, saas, cloud_infra, robotics, monitoring,
  auth, payments, analytics, design, testing, deployment, ml_platform,
  local_inference, rag_framework, ai_image]
- aliases: other ways people refer to it
- confidence: 0.0-1.0 how confident you are this is a real software product

STRICT RULES:
- ONLY include actual software products, tools, libraries, or tech services
- NEVER include physical products, consumer goods, courses, books, newsletters, podcasts
- NEVER include generic terms, programming languages, or company names used generically
- NEVER use category "other" — if it doesn't fit a tech category, don't include it
- If unsure whether something is a real tech product, set confidence < 0.5
- Product must have a specific, searchable name (not "AI tool" or "coding assistant")

Return JSON array. Return empty array [] if no NEW products found."""

        try:
            result = await call_llm(
                prompt=prompt,
                system_message="You are a product intelligence analyst.",
                model="mini",
                parse_json=True,
                usage_tracker=self.usage,
                max_tokens=2000,
            )

            if not isinstance(result, list):
                return

            async with async_session() as session:
                for product in result:
                    if not isinstance(product, dict):
                        continue
                    name = product.get("name", "").strip()
                    confidence = product.get("confidence", 0)
                    category = product.get("category", "other")
                    if not name or confidence < 0.7:
                        continue
                    if name in known_names:
                        continue
                    # Block non-tech products
                    if category in BLOCKED_CATEGORIES:
                        continue
                    name_lower = name.lower()
                    if any(blocked in name_lower for blocked in PRODUCT_BLOCKLIST):
                        continue

                    stmt = pg_insert(DiscoveredProduct).values(
                        canonical_name=name,
                        category=product.get("category", "other"),
                        aliases=product.get("aliases", []),
                        discovered_by="llm",
                        confidence=confidence,
                    ).on_conflict_do_nothing(index_elements=["canonical_name"])
                    await session.execute(stmt)
                    self.products_discovered += 1

                await session.commit()
                self.log.info("llm_discovery_complete", new_products=self.products_discovered)

        except Exception as e:
            self.log.error("llm_discovery_failed", error=str(e))
            self.errors += 1

    async def _update_mention_counts(self):
        """Update total_mentions on discovered_products from product_mentions table."""
        async with async_session() as session:
            await session.execute(text("""
                UPDATE discovered_products dp
                SET total_mentions = sub.cnt,
                    last_seen_at = sub.last_seen
                FROM (
                    SELECT product_id, COUNT(*) as cnt, MAX(detected_at) as last_seen
                    FROM product_mentions
                    GROUP BY product_id
                ) sub
                WHERE dp.id = sub.product_id
            """))
            await session.commit()
