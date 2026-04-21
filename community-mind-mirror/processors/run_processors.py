"""CLI orchestrator for all processors.

Usage:
    python -m processors.run_processors --all
    python -m processors.run_processors --sentiment
    python -m processors.run_processors --personas
    python -m processors.run_processors --topics
    python -m processors.run_processors --graph
    python -m processors.run_processors --news
"""

import argparse
import asyncio
import time

import structlog
from sqlalchemy import select, func

from database.connection import (
    async_session, engine, Persona, Topic, TopicMention, CommunityGraph, NewsEvent,
    DiscoveredProduct, ProductMention, Migration, PainPoint, HypeIndex,
    LeaderShift, PlatformTone, FundingRound,
)
from init_db import init_db

structlog.configure(
    processors=[structlog.dev.ConsoleRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(0),
)

log = structlog.get_logger()

# Execution order: sentiment first (cheap, feeds into others),
# then personas, topics, news, graph (uses everything),
# then intelligence processors that depend on the above
PROCESSOR_ORDER = [
    "sentiment", "personas", "topics", "news", "graph",
    "products", "migrations", "pain_points", "hype_index",
    "leader_shifts", "funding", "platform_tones",
    "product_reviews", "gig_posts",
]


async def run_sentiment() -> dict:
    from processors.sentiment_analyzer import SentimentAnalyzer
    analyzer = SentimentAnalyzer()
    return await analyzer.run()


async def run_personas() -> dict:
    from processors.persona_extractor import PersonaExtractor
    extractor = PersonaExtractor()
    return await extractor.run()


async def run_topics() -> dict:
    from processors.topic_detector import TopicDetector
    detector = TopicDetector()
    return await detector.run()


async def run_news() -> dict:
    from processors.news_processor import NewsProcessor
    processor = NewsProcessor()
    return await processor.run()


async def run_graph() -> dict:
    from processors.graph_builder import GraphBuilder
    builder = GraphBuilder()
    return await builder.run()


async def run_products() -> dict:
    from processors.product_processor import ProductProcessor
    processor = ProductProcessor()
    return await processor.run()


async def run_migrations() -> dict:
    from processors.migration_processor import MigrationProcessor
    processor = MigrationProcessor()
    return await processor.run()


async def run_pain_points() -> dict:
    from processors.pain_point_processor import PainPointProcessor
    processor = PainPointProcessor()
    return await processor.run()


async def run_hype_index() -> dict:
    from processors.hype_processor import HypeProcessor
    processor = HypeProcessor()
    return await processor.run()


async def run_leader_shifts() -> dict:
    from processors.leader_shift_processor import LeaderShiftProcessor
    processor = LeaderShiftProcessor()
    return await processor.run()


async def run_funding() -> dict:
    from processors.funding_processor import FundingProcessor
    processor = FundingProcessor()
    return await processor.run()


async def run_platform_tones() -> dict:
    from processors.platform_tone_processor import PlatformToneProcessor
    processor = PlatformToneProcessor()
    return await processor.run()


async def run_product_reviews() -> dict:
    from processors.product_review_processor import ProductReviewProcessor
    processor = ProductReviewProcessor()
    return await processor.run()


async def run_gig_posts() -> dict:
    from processors.gig_post_processor import run as run_gig
    processed, failed = await run_gig()
    return {"processed": processed, "failed": failed}


async def run_freelance_market() -> dict:
    from processors.freelance_market_processor import FreelanceMarketProcessor
    processor = FreelanceMarketProcessor()
    return await processor.run()


PROCESSOR_MAP = {
    "sentiment": run_sentiment,
    "personas": run_personas,
    "topics": run_topics,
    "news": run_news,
    "graph": run_graph,
    "products": run_products,
    "migrations": run_migrations,
    "pain_points": run_pain_points,
    "hype_index": run_hype_index,
    "leader_shifts": run_leader_shifts,
    "funding": run_funding,
    "platform_tones": run_platform_tones,
    "product_reviews": run_product_reviews,
    "gig_posts": run_gig_posts,
    "freelance_market": run_freelance_market,
}


async def run_all() -> None:
    """Run all processors in dependency order."""
    total_start = time.time()
    for name in PROCESSOR_ORDER:
        log.info("processor_starting", name=name)
        start = time.time()
        try:
            result = await PROCESSOR_MAP[name]()
            elapsed = time.time() - start
            log.info("processor_complete", name=name, elapsed=f"{elapsed:.1f}s", **result)
        except Exception as e:
            elapsed = time.time() - start
            log.error("processor_failed", name=name, elapsed=f"{elapsed:.1f}s", error=str(e))

    total_elapsed = time.time() - total_start
    log.info("all_processors_complete", elapsed=f"{total_elapsed:.1f}s")


async def print_processor_summary():
    """Print a summary of processor output tables."""
    async with async_session() as session:
        persona_count = (await session.execute(select(func.count(Persona.id)))).scalar()
        topic_count = (await session.execute(select(func.count(Topic.id)))).scalar()
        mention_count = (await session.execute(select(func.count(TopicMention.id)))).scalar()
        graph_edge_count = (await session.execute(select(func.count(CommunityGraph.id)))).scalar()

        # News events with entities
        news_with_entities = (
            await session.execute(
                select(func.count(NewsEvent.id)).where(NewsEvent.entities.isnot(None))
            )
        ).scalar()

        # Personas by influence type
        persona_types = (
            await session.execute(
                select(Persona.influence_type, func.count(Persona.id))
                .group_by(Persona.influence_type)
            )
        ).all()

        # Topics by status
        topic_statuses = (
            await session.execute(
                select(Topic.status, func.count(Topic.id))
                .group_by(Topic.status)
            )
        ).all()

    print("\n" + "=" * 60)
    print("PROCESSOR SUMMARY")
    print("=" * 60)
    print(f"Total personas:        {persona_count}")
    print(f"Total topics:          {topic_count}")
    print(f"Total topic mentions:  {mention_count}")
    print(f"Total graph edges:     {graph_edge_count}")
    print(f"News with entities:    {news_with_entities}")

    # New intelligence tables
    async with async_session() as session:
        product_count = (await session.execute(select(func.count(DiscoveredProduct.id)))).scalar()
        mention_count_pm = (await session.execute(select(func.count(ProductMention.id)))).scalar()
        migration_count = (await session.execute(select(func.count(Migration.id)))).scalar()
        pain_point_count = (await session.execute(select(func.count(PainPoint.id)))).scalar()
        hype_count = (await session.execute(select(func.count(HypeIndex.id)))).scalar()
        shift_count = (await session.execute(select(func.count(LeaderShift.id)))).scalar()
        tone_count = (await session.execute(select(func.count(PlatformTone.id)))).scalar()
        funding_count = (await session.execute(select(func.count(FundingRound.id)))).scalar()

    print(f"\n--- Intelligence Data ---")
    print(f"  Discovered products: {product_count}")
    print(f"  Product mentions:    {mention_count_pm}")
    print(f"  Migrations:          {migration_count}")
    print(f"  Pain points:         {pain_point_count}")
    print(f"  Hype index sectors:  {hype_count}")
    print(f"  Leader shifts:       {shift_count}")
    print(f"  Platform tones:      {tone_count}")
    print(f"  Funding rounds:      {funding_count}")

    if persona_types:
        print("\n--- Personas by Influence Type ---")
        for itype, count in sorted(persona_types, key=lambda x: x[1], reverse=True):
            print(f"  {itype or 'unknown':25s} {count}")

    if topic_statuses:
        print("\n--- Topics by Status ---")
        for status, count in sorted(topic_statuses, key=lambda x: x[1], reverse=True):
            print(f"  {status or 'unknown':25s} {count}")

    print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="Community Mind Mirror — Processor CLI")
    parser.add_argument("--all", action="store_true", help="Run all processors in order")
    parser.add_argument("--sentiment", action="store_true", help="Run sentiment analysis")
    parser.add_argument("--personas", action="store_true", help="Run persona extraction")
    parser.add_argument("--topics", action="store_true", help="Run topic detection")
    parser.add_argument("--graph", action="store_true", help="Run graph building")
    parser.add_argument("--news", action="store_true", help="Run news processing")
    parser.add_argument("--summary", action="store_true", help="Print processor summary only")
    args = parser.parse_args()

    await init_db()

    if args.summary:
        await print_processor_summary()
    elif args.all:
        await run_all()
        await print_processor_summary()
    else:
        ran_any = False
        for name in PROCESSOR_ORDER:
            if getattr(args, name, False):
                log.info("processor_starting", name=name)
                start = time.time()
                try:
                    result = await PROCESSOR_MAP[name]()
                    elapsed = time.time() - start
                    log.info("processor_complete", name=name, elapsed=f"{elapsed:.1f}s", **result)
                except Exception as e:
                    elapsed = time.time() - start
                    log.error("processor_failed", name=name, elapsed=f"{elapsed:.1f}s", error=str(e))
                ran_any = True

        if ran_any:
            await print_processor_summary()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
