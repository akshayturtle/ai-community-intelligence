"""Main entry point — run scrapers, processors, or scheduler.

Usage:
    python main.py --scheduler               Run all scrapers + processors on schedule
    python main.py --scraper reddit          Run Reddit scraper once
    python main.py --scraper all             Run all scrapers once sequentially
    python main.py --processor sentiment     Run sentiment analysis
    python main.py --processor personas      Run persona extraction
    python main.py --processor topics        Run topic detection
    python main.py --processor news          Run news processing
    python main.py --processor graph         Run graph building
    python main.py --processor products      Run product discovery
    python main.py --processor migrations    Run migration detection
    python main.py --processor pain_points   Run pain point synthesis
    python main.py --processor hype_index    Run hype vs reality index
    python main.py --processor leader_shifts Run leader shift detection
    python main.py --processor funding       Run funding analysis
    python main.py --processor platform_tones Run platform tone analysis
    python main.py --processor all           Run all processors in order
    python main.py --summary                 Print database summary
"""

import argparse
import asyncio
import signal
import time

import structlog
from sqlalchemy import select, func

from database.connection import (
    async_session, engine, User, Post, NewsEvent, ScraperRun,
    Persona, Topic, TopicMention, CommunityGraph,
    DiscoveredProduct, ProductMention, Migration, PainPoint,
    HypeIndex, LeaderShift, PlatformTone, FundingRound,
    GithubRepo, PackageDownload, YCCompany, HFModel,
    PHLaunch, SOQuestion, AgentRun,
)
from init_db import init_db
from scheduler.cron_jobs import create_scheduler, SCRAPER_MAP

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
)

log = structlog.get_logger()


async def print_summary():
    """Print a summary of all data in the database."""
    async with async_session() as session:
        user_count = (await session.execute(select(func.count(User.id)))).scalar()
        post_count = (await session.execute(select(func.count(Post.id)))).scalar()
        news_count = (await session.execute(select(func.count(NewsEvent.id)))).scalar()
        run_count = (await session.execute(select(func.count(ScraperRun.id)))).scalar()

        # Per-platform user counts
        platform_users = (
            await session.execute(
                select(User.platform_id, func.count(User.id))
                .group_by(User.platform_id)
            )
        ).all()

        # Per-platform post counts
        platform_posts = (
            await session.execute(
                select(Post.platform_id, func.count(Post.id))
                .group_by(Post.platform_id)
            )
        ).all()

        # News events by source type
        news_by_type = (
            await session.execute(
                select(NewsEvent.source_type, func.count(NewsEvent.id))
                .group_by(NewsEvent.source_type)
            )
        ).all()

    # Platform ID mapping (from init_db seed order)
    platform_names = {
        1: "reddit", 2: "hackernews", 3: "youtube", 4: "twitter",
        5: "linkedin", 6: "producthunt", 7: "stackoverflow",
        8: "discord", 9: "mastodon", 10: "bluesky",
    }

    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)
    print(f"Total users:       {user_count}")
    print(f"Total posts:       {post_count}")
    print(f"Total news events: {news_count}")
    print(f"Total scraper runs: {run_count}")

    print("\n--- Users by Platform ---")
    for pid, count in sorted(platform_users):
        name = platform_names.get(pid, f"platform_{pid}")
        print(f"  {name:20s} {count}")

    print("\n--- Posts by Platform ---")
    for pid, count in sorted(platform_posts):
        name = platform_names.get(pid, f"platform_{pid}")
        print(f"  {name:20s} {count}")

    print("\n--- News Events by Type ---")
    for stype, count in sorted(news_by_type):
        print(f"  {stype:25s} {count}")

    # Processor data
    async with async_session() as session:
        persona_count = (await session.execute(select(func.count(Persona.id)))).scalar()
        topic_count = (await session.execute(select(func.count(Topic.id)))).scalar()
        mention_count = (await session.execute(select(func.count(TopicMention.id)))).scalar()
        graph_count = (await session.execute(select(func.count(CommunityGraph.id)))).scalar()
        news_with_entities = (
            await session.execute(
                select(func.count(NewsEvent.id)).where(NewsEvent.entities.isnot(None))
            )
        ).scalar()

    print("\n--- Processor Data ---")
    print(f"  Personas:            {persona_count}")
    print(f"  Topics:              {topic_count}")
    print(f"  Topic mentions:      {mention_count}")
    print(f"  Graph edges:         {graph_count}")
    print(f"  News with entities:  {news_with_entities}")

    # Intelligence data
    async with async_session() as session:
        product_count = (await session.execute(select(func.count(DiscoveredProduct.id)))).scalar()
        product_mention_count = (await session.execute(select(func.count(ProductMention.id)))).scalar()
        migration_count = (await session.execute(select(func.count(Migration.id)))).scalar()
        pain_point_count = (await session.execute(select(func.count(PainPoint.id)))).scalar()
        hype_count = (await session.execute(select(func.count(HypeIndex.id)))).scalar()
        shift_count = (await session.execute(select(func.count(LeaderShift.id)))).scalar()
        tone_count = (await session.execute(select(func.count(PlatformTone.id)))).scalar()
        funding_count = (await session.execute(select(func.count(FundingRound.id)))).scalar()

    print("\n--- Intelligence Data ---")
    print(f"  Discovered products: {product_count}")
    print(f"  Product mentions:    {product_mention_count}")
    print(f"  Migrations:          {migration_count}")
    print(f"  Pain points:         {pain_point_count}")
    print(f"  Hype index sectors:  {hype_count}")
    print(f"  Leader shifts:       {shift_count}")
    print(f"  Platform tones:      {tone_count}")
    print(f"  Funding rounds:      {funding_count}")

    # Phase 2 scraper data
    async with async_session() as session:
        gh_count = (await session.execute(select(func.count(GithubRepo.id)))).scalar()
        pkg_count = (await session.execute(select(func.count(PackageDownload.id)))).scalar()
        yc_count = (await session.execute(select(func.count(YCCompany.id)))).scalar()
        hf_count = (await session.execute(select(func.count(HFModel.id)))).scalar()
        ph_count = (await session.execute(select(func.count(PHLaunch.id)))).scalar()
        so_count = (await session.execute(select(func.count(SOQuestion.id)))).scalar()
        agent_count = (await session.execute(select(func.count(AgentRun.id)))).scalar()

    print("\n--- Phase 2 Scraper Data ---")
    print(f"  GitHub repos:        {gh_count}")
    print(f"  HF models:           {hf_count}")
    print(f"  PH launches:         {ph_count}")
    print(f"  SO questions:        {so_count}")
    print(f"  Package downloads:   {pkg_count}")
    print(f"  YC companies:        {yc_count}")
    print(f"  Agent runs:          {agent_count}")

    print("=" * 60)


async def run_single_scraper(name: str):
    """Run a single scraper by name."""
    if name not in SCRAPER_MAP:
        print(f"Unknown scraper: {name}")
        print(f"Available: {', '.join(SCRAPER_MAP.keys())}")
        return

    start = time.time()
    log.info("running_scraper", name=name)
    await SCRAPER_MAP[name]()
    elapsed = time.time() - start
    log.info("scraper_finished", name=name, elapsed=f"{elapsed:.1f}s")


async def run_all_scrapers():
    """Run all scrapers once, sequentially."""
    start = time.time()
    for name in SCRAPER_MAP:
        log.info("running_scraper", name=name)
        try:
            await SCRAPER_MAP[name]()
        except Exception as e:
            log.error("scraper_failed", name=name, error=str(e))
    elapsed = time.time() - start
    log.info("all_scrapers_finished", elapsed=f"{elapsed:.1f}s")


async def run_scheduler():
    """Start the APScheduler and run scrapers on their configured intervals."""
    scheduler = create_scheduler()
    scheduler.start()
    log.info("scheduler_started", jobs=len(scheduler.get_jobs()))

    for job in scheduler.get_jobs():
        log.info("scheduled_job", id=job.id, trigger=str(job.trigger))

    # Keep running until interrupted
    stop_event = asyncio.Event()

    def handle_signal():
        log.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await stop_event.wait()
    scheduler.shutdown()
    log.info("scheduler_shutdown")


async def main():
    parser = argparse.ArgumentParser(description="Community Mind Mirror — Scraper CLI")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--scheduler", action="store_true", help="Run all scrapers on schedule"
    )
    group.add_argument(
        "--scraper",
        type=str,
        choices=list(SCRAPER_MAP.keys()) + ["all"],
        help="Run a specific scraper once",
    )
    group.add_argument(
        "--processor",
        type=str,
        choices=[
            "all", "sentiment", "personas", "topics", "graph", "news",
            "products", "migrations", "pain_points", "hype_index",
            "leader_shifts", "funding", "platform_tones",
        ],
        help="Run a specific processor once",
    )
    group.add_argument(
        "--agent",
        type=str,
        choices=[
            "all", "research_pipeline", "traction_scorer", "market_gap_detector",
            "competitive_threat", "divergence_detector", "lifecycle_mapper",
            "smart_money_tracker", "talent_flow", "product_discoverer",
            "narrative_shift", "insight_synthesizer",
        ],
        help="Run a specific Agno signal agent once",
    )
    group.add_argument(
        "--summary", action="store_true", help="Print database summary"
    )

    args = parser.parse_args()

    # Always init DB first
    await init_db()

    if args.summary:
        await print_summary()
    elif args.scraper == "all":
        await run_all_scrapers()
        await print_summary()
    elif args.scraper:
        await run_single_scraper(args.scraper)
        await print_summary()
    elif args.processor:
        from processors.run_processors import run_all as run_all_processors, PROCESSOR_MAP as PROC_MAP
        if args.processor == "all":
            await run_all_processors()
        else:
            start = time.time()
            log.info("running_processor", name=args.processor)
            result = await PROC_MAP[args.processor]()
            elapsed = time.time() - start
            log.info("processor_finished", name=args.processor, elapsed=f"{elapsed:.1f}s", **result)
        await print_summary()
    elif args.agent:
        from agents.orchestrator import CrossSourceOrchestrator
        orchestrator = CrossSourceOrchestrator()
        if args.agent == "all":
            log.info("running_all_agents")
            results = await orchestrator.run_all_signals()
            succeeded = sum(1 for v in results.values() if v is not None)
            log.info("all_agents_finished", total=len(results), succeeded=succeeded)
        else:
            start_t = time.time()
            log.info("running_agent", name=args.agent)
            result = await orchestrator.run_single(args.agent)
            elapsed = time.time() - start_t
            log.info("agent_finished", name=args.agent, elapsed=f"{elapsed:.1f}s")
            print(f"\n--- Agent Output ({args.agent}) ---")
            print(result[:5000] if result else "(no output)")
        await print_summary()
    elif args.scheduler:
        await run_scheduler()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
