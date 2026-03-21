"""APScheduler-based cron scheduler for all scrapers."""

import asyncio

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scrapers.reddit_scraper import RedditScraper
from scrapers.hn_scraper import HNScraper
from scrapers.youtube_scraper import YouTubeScraper
from scrapers.news_scraper import NewsScraper
from scrapers.arxiv_scraper import ArXivScraper
from scrapers.job_scraper import JobScraper
from scrapers.github_scraper import GitHubScraper
from scrapers.huggingface_scraper import HuggingFaceScraper
from scrapers.producthunt_scraper import ProductHuntScraper
from scrapers.stackoverflow_scraper import StackOverflowScraper
from scrapers.paperswithcode_scraper import PapersWithCodeScraper
from scrapers.package_scraper import PackageScraper
from scrapers.yc_scraper import YCScraper

logger = structlog.get_logger()


async def run_reddit():
    logger.info("scheduler_job_start", scraper="reddit")
    try:
        scraper = RedditScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="reddit", error=str(e))


async def run_hn():
    logger.info("scheduler_job_start", scraper="hn")
    try:
        scraper = HNScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="hn", error=str(e))


async def run_youtube():
    logger.info("scheduler_job_start", scraper="youtube")
    try:
        scraper = YouTubeScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="youtube", error=str(e))


async def run_news():
    logger.info("scheduler_job_start", scraper="news")
    try:
        scraper = NewsScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="news", error=str(e))


async def run_arxiv():
    logger.info("scheduler_job_start", scraper="arxiv")
    try:
        scraper = ArXivScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="arxiv", error=str(e))


async def run_jobs():
    logger.info("scheduler_job_start", scraper="jobs")
    try:
        scraper = JobScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="jobs", error=str(e))


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler with all scraper jobs."""
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        run_reddit,
        trigger=IntervalTrigger(hours=24),
        id="reddit_scraper",
        name="Reddit RSS Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_hn,
        trigger=IntervalTrigger(hours=12),
        id="hn_scraper",
        name="Hacker News Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_youtube,
        trigger=IntervalTrigger(hours=24),
        id="youtube_scraper",
        name="YouTube Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_news,
        trigger=IntervalTrigger(hours=6),
        id="news_scraper",
        name="News RSS Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_arxiv,
        trigger=IntervalTrigger(hours=24),
        id="arxiv_scraper",
        name="ArXiv Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_jobs,
        trigger=IntervalTrigger(hours=24),
        id="job_scraper",
        name="Job Market Scraper",
        max_instances=1,
        replace_existing=True,
    )

    scheduler.add_job(
        run_github,
        trigger=IntervalTrigger(hours=24),
        id="github_scraper",
        name="GitHub Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_huggingface,
        trigger=IntervalTrigger(hours=24),
        id="huggingface_scraper",
        name="Hugging Face Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_producthunt,
        trigger=IntervalTrigger(hours=24),
        id="producthunt_scraper",
        name="Product Hunt Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_stackoverflow,
        trigger=IntervalTrigger(hours=24),
        id="stackoverflow_scraper",
        name="Stack Overflow Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_paperswithcode,
        trigger=IntervalTrigger(hours=24),
        id="paperswithcode_scraper",
        name="Papers with Code Scraper",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_packages,
        trigger=IntervalTrigger(hours=24),
        id="package_scraper",
        name="Package Download Tracker",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        run_yc,
        trigger=IntervalTrigger(hours=168),
        id="yc_scraper",
        name="YC Companies Scraper",
        max_instances=1,
        replace_existing=True,
    )

    # --- Processor jobs (run after scrapers have new data) ---

    scheduler.add_job(
        _run_processor_sentiment,
        trigger=IntervalTrigger(hours=6),
        id="processor_sentiment",
        name="Sentiment Analyzer",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        _run_processor_personas,
        trigger=IntervalTrigger(hours=12),
        id="processor_personas",
        name="Persona Extractor",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        _run_processor_topics,
        trigger=IntervalTrigger(hours=6),
        id="processor_topics",
        name="Topic Detector",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        _run_processor_news,
        trigger=IntervalTrigger(hours=6),
        id="processor_news",
        name="News Processor",
        max_instances=1,
        replace_existing=True,
    )
    scheduler.add_job(
        _run_processor_graph,
        trigger=IntervalTrigger(hours=24),
        id="processor_graph",
        name="Graph Builder",
        max_instances=1,
        replace_existing=True,
    )

    # --- Agno agent jobs (run AFTER processors have updated data) ---

    # Group 1: Independent signal agents (staggered 5 min apart)
    _agent_schedule = [
        ("research_pipeline", 24),
        ("traction_scorer", 24),
        ("market_gap_detector", 24),
        ("divergence_detector", 12),
        ("lifecycle_mapper", 24),
        ("talent_flow", 24),
        ("product_discoverer", 12),
        ("narrative_shift", 48),
    ]
    for agent_name, hours in _agent_schedule:
        scheduler.add_job(
            _run_agent,
            trigger=IntervalTrigger(hours=hours),
            id=f"agent_{agent_name}",
            name=f"Agent: {agent_name}",
            max_instances=1,
            replace_existing=True,
            kwargs={"agent_name": agent_name},
        )

    # Group 2: Dependent agents
    scheduler.add_job(
        _run_agent,
        trigger=IntervalTrigger(hours=24),
        id="agent_competitive_threat",
        name="Agent: competitive_threat",
        max_instances=1,
        replace_existing=True,
        kwargs={"agent_name": "competitive_threat"},
    )
    scheduler.add_job(
        _run_agent,
        trigger=IntervalTrigger(hours=168),
        id="agent_smart_money_tracker",
        name="Agent: smart_money_tracker",
        max_instances=1,
        replace_existing=True,
        kwargs={"agent_name": "smart_money_tracker"},
    )

    # Synthesizer: runs LAST, every 12 hours
    scheduler.add_job(
        _run_agent,
        trigger=IntervalTrigger(hours=12),
        id="agent_insight_synthesizer",
        name="Agent: insight_synthesizer",
        max_instances=1,
        replace_existing=True,
        kwargs={"agent_name": "insight_synthesizer"},
    )

    return scheduler


# --- Agent wrapper ---

async def _run_agent(agent_name: str):
    logger.info("scheduler_job_start", agent=agent_name)
    try:
        from agents.orchestrator import CrossSourceOrchestrator
        orchestrator = CrossSourceOrchestrator()
        await orchestrator.run_single(agent_name)
    except Exception as e:
        logger.error("scheduler_job_failed", agent=agent_name, error=str(e))


# --- Processor wrappers ---

async def _run_processor_sentiment():
    logger.info("scheduler_job_start", processor="sentiment")
    try:
        from processors.run_processors import run_sentiment
        await run_sentiment()
    except Exception as e:
        logger.error("scheduler_job_failed", processor="sentiment", error=str(e))


async def _run_processor_personas():
    logger.info("scheduler_job_start", processor="personas")
    try:
        from processors.run_processors import run_personas
        await run_personas()
    except Exception as e:
        logger.error("scheduler_job_failed", processor="personas", error=str(e))


async def _run_processor_topics():
    logger.info("scheduler_job_start", processor="topics")
    try:
        from processors.run_processors import run_topics
        await run_topics()
    except Exception as e:
        logger.error("scheduler_job_failed", processor="topics", error=str(e))


async def _run_processor_news():
    logger.info("scheduler_job_start", processor="news")
    try:
        from processors.run_processors import run_news
        await run_news()
    except Exception as e:
        logger.error("scheduler_job_failed", processor="news", error=str(e))


async def _run_processor_graph():
    logger.info("scheduler_job_start", processor="graph")
    try:
        from processors.run_processors import run_graph
        await run_graph()
    except Exception as e:
        logger.error("scheduler_job_failed", processor="graph", error=str(e))


async def run_github():
    logger.info("scheduler_job_start", scraper="github")
    try:
        scraper = GitHubScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="github", error=str(e))


async def run_huggingface():
    logger.info("scheduler_job_start", scraper="huggingface")
    try:
        scraper = HuggingFaceScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="huggingface", error=str(e))


async def run_producthunt():
    logger.info("scheduler_job_start", scraper="producthunt")
    try:
        scraper = ProductHuntScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="producthunt", error=str(e))


async def run_stackoverflow():
    logger.info("scheduler_job_start", scraper="stackoverflow")
    try:
        scraper = StackOverflowScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="stackoverflow", error=str(e))


async def run_paperswithcode():
    logger.info("scheduler_job_start", scraper="paperswithcode")
    try:
        scraper = PapersWithCodeScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="paperswithcode", error=str(e))


async def run_packages():
    logger.info("scheduler_job_start", scraper="packages")
    try:
        scraper = PackageScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="packages", error=str(e))


async def run_yc():
    logger.info("scheduler_job_start", scraper="yc")
    try:
        scraper = YCScraper()
        await scraper.run()
    except Exception as e:
        logger.error("scheduler_job_failed", scraper="yc", error=str(e))


SCRAPER_MAP = {
    "reddit": run_reddit,
    "hn": run_hn,
    "youtube": run_youtube,
    "news": run_news,
    "arxiv": run_arxiv,
    "jobs": run_jobs,
    "github": run_github,
    "huggingface": run_huggingface,
    "producthunt": run_producthunt,
    "stackoverflow": run_stackoverflow,
    "paperswithcode": run_paperswithcode,
    "packages": run_packages,
    "yc": run_yc,
}
