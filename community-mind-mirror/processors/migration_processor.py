"""Migration Pattern Detector — detects product switches (FROM → TO).

Layer 1: Regex migration patterns + fuzzy match against product registry
Layer 3: LLM for ambiguous cases only
"""

import re
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import (
    async_session,
    Post,
    DiscoveredProduct,
    Migration,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

MIGRATION_PATTERNS = [
    r"(?i)switched from (.+?) to (.+?)[\.\,\!\s]",
    r"(?i)moved from (.+?) to (.+?)[\.\,\!\s]",
    r"(?i)migrated from (.+?) to (.+?)[\.\,\!\s]",
    r"(?i)replaced (.+?) with (.+?)[\.\,\!\s]",
    r"(?i)dropped (.+?) for (.+?)[\.\,\!\s]",
    r"(?i)ditched (.+?) and went with (.+?)[\.\,\!\s]",
    r"(?i)was using (.+?) but now (?:I |we )?use (.+?)[\.\,\!\s]",
    r"(?i)left (.+?) for (.+?)[\.\,\!\s]",
    r"(?i)went from (.+?) to (.+?)[\.\,\!\s]",
    r"(?i)used to use (.+?)[\.\,\s].+?(?:now|currently) (?:use|using) (.+?)[\.\,\!\s]",
]


class MigrationProcessor:
    """Detects product migration patterns from community posts."""

    BATCH_SIZE = 500

    def __init__(self):
        self.log = logger.bind(processor="migration_processor")
        self.usage = TokenUsage()
        self.migrations_found = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("migration_processor_start")

        registry = await self._load_registry()
        if not registry:
            self.log.info("no_products_in_registry")
            return {"migrations": 0, "errors": 0}

        await self._scan_posts(registry)

        self.log.info(
            "migration_processor_complete",
            migrations=self.migrations_found,
            errors=self.errors,
        )
        return {"migrations": self.migrations_found, "errors": self.errors}

    async def _load_registry(self) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(
                    DiscoveredProduct.id,
                    DiscoveredProduct.canonical_name,
                    DiscoveredProduct.aliases,
                )
                .where(DiscoveredProduct.status == "active")
            )
            return [
                {"id": r.id, "canonical_name": r.canonical_name, "aliases": r.aliases or []}
                for r in result.all()
            ]

    def _fuzzy_match(self, raw_text: str, registry: list[dict]) -> dict | None:
        raw_lower = raw_text.lower().strip()
        if len(raw_lower) < 2 or len(raw_lower) > 50:
            return None

        for product in registry:
            if raw_lower == product["canonical_name"].lower():
                return product
            for alias in product.get("aliases", []):
                if raw_lower == alias.lower() or alias.lower() in raw_lower:
                    return product
        return None

    def _detect_migrations(self, text: str, registry: list[dict]) -> list[dict]:
        results = []
        for pattern in MIGRATION_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                from_raw = match[0].strip()
                to_raw = match[1].strip()

                from_product = self._fuzzy_match(from_raw, registry)
                to_product = self._fuzzy_match(to_raw, registry)

                if from_product and to_product and from_product["id"] != to_product["id"]:
                    results.append({
                        "from_id": from_product["id"],
                        "to_id": to_product["id"],
                        "confidence": 0.9,
                        "confirmed_by": "regex",
                    })
        return results

    async def _scan_posts(self, registry: list[dict]):
        offset = 0
        while True:
            async with async_session() as session:
                result = await session.execute(
                    select(Post.id, Post.user_id, Post.title, Post.body, Post.raw_metadata)
                    .where(
                        (Post.raw_metadata.is_(None))
                        | (~Post.raw_metadata.has_key("migrations_scanned"))
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
                        post_id, user_id, title, body, raw_metadata = post
                        text = f"{title or ''} {body or ''}".strip()
                        if not text:
                            continue

                        migrations = self._detect_migrations(text, registry)
                        for mig in migrations:
                            stmt = pg_insert(Migration).values(
                                from_product_id=mig["from_id"],
                                to_product_id=mig["to_id"],
                                post_id=post_id,
                                user_id=user_id,
                                confidence=mig["confidence"],
                                confirmed_by=mig["confirmed_by"],
                            ).on_conflict_do_nothing()
                            await session.execute(stmt)
                            self.migrations_found += 1

                        # Mark as scanned
                        metadata = dict(raw_metadata) if raw_metadata else {}
                        metadata["migrations_scanned"] = True
                        from sqlalchemy import update
                        await session.execute(
                            update(Post).where(Post.id == post_id).values(raw_metadata=metadata)
                        )
                    except Exception as e:
                        self.errors += 1
                        self.log.warning("migration_scan_error", post_id=post[0], error=str(e))

                await session.commit()

            offset += self.BATCH_SIZE
            self.log.info("migration_batch", offset=offset, found=self.migrations_found)
