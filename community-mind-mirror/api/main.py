"""FastAPI application for the Community Mind Mirror Intelligence Dashboard."""

import time

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from api.deps import get_db
from api.routes import dashboard, topics, personas, news, search, websocket, intelligence, signals, agents, source_data, job_intelligence, product_reviews, gig_board, research
from database.connection import (
    async_session, User, Post, Persona, Topic, TopicMention,
    CommunityGraph, NewsEvent, ScraperRun,
    DiscoveredProduct, ProductMention, Migration, PainPoint,
    HypeIndex, LeaderShift, PlatformTone, FundingRound, AgentRun,
    ResearchPipeline, TractionScore, TechnologyLifecycle,
    MarketGap, CompetitiveThreat, PlatformDivergence,
    GithubRepo, HFModel, PackageDownload, YCCompany, SOQuestion, PHLaunch,
    ProductReview, GigPost, ResearchProject,
)

logger = structlog.get_logger()

app = FastAPI(
    title="Community Mind Mirror",
    description="Intelligence Dashboard API for AI/tech community analysis",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    if not request.url.path.startswith("/api/ws"):
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed=f"{elapsed:.3f}s",
        )
    return response


# Include routers
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(topics.router, prefix="/api/topics", tags=["topics"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(news.router, prefix="/api/news", tags=["news"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"])
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(source_data.router, prefix="/api/sources", tags=["source-data"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(job_intelligence.router, prefix="/api/job-intelligence", tags=["job-intelligence"])
app.include_router(product_reviews.router, prefix="/api/product-reviews", tags=["product-reviews"])
app.include_router(gig_board.router, prefix="/api/gig-board", tags=["gig-board"])
app.include_router(research.router, prefix="/api/research", tags=["research"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "community-mind-mirror"}


@app.get("/api/stats")
async def stats():
    """Return record counts for all tables."""
    async with async_session() as session:
        users = (await session.execute(select(func.count(User.id)))).scalar()
        posts = (await session.execute(select(func.count(Post.id)))).scalar()
        personas = (await session.execute(select(func.count(Persona.id)))).scalar()
        topics_count = (await session.execute(select(func.count(Topic.id)))).scalar()
        mentions = (await session.execute(select(func.count(TopicMention.id)))).scalar()
        graph_edges = (await session.execute(select(func.count(CommunityGraph.id)))).scalar()
        news_events = (await session.execute(select(func.count(NewsEvent.id)))).scalar()
        scraper_runs = (await session.execute(select(func.count(ScraperRun.id)))).scalar()

    async with async_session() as session:
        products = (await session.execute(select(func.count(DiscoveredProduct.id)))).scalar()
        product_mentions = (await session.execute(select(func.count(ProductMention.id)))).scalar()
        migrations = (await session.execute(select(func.count(Migration.id)))).scalar()
        pain_points = (await session.execute(select(func.count(PainPoint.id)))).scalar()
        hype_index = (await session.execute(select(func.count(HypeIndex.id)))).scalar()
        leader_shifts = (await session.execute(select(func.count(LeaderShift.id)))).scalar()
        platform_tones = (await session.execute(select(func.count(PlatformTone.id)))).scalar()
        funding_rounds = (await session.execute(select(func.count(FundingRound.id)))).scalar()

    async with async_session() as session:
        agent_runs = (await session.execute(select(func.count(AgentRun.id)))).scalar()
        research_pipeline = (await session.execute(select(func.count(ResearchPipeline.id)))).scalar()
        traction_scores = (await session.execute(select(func.count(TractionScore.id)))).scalar()
        tech_lifecycle = (await session.execute(select(func.count(TechnologyLifecycle.id)))).scalar()
        market_gaps = (await session.execute(select(func.count(MarketGap.id)))).scalar()
        competitive_threats = (await session.execute(select(func.count(CompetitiveThreat.id)))).scalar()
        platform_divergence = (await session.execute(select(func.count(PlatformDivergence.id)))).scalar()

    async with async_session() as session:
        github_repos = (await session.execute(select(func.count(GithubRepo.id)))).scalar()
        hf_models = (await session.execute(select(func.count(HFModel.id)))).scalar()
        package_downloads = (await session.execute(select(func.count(PackageDownload.id)))).scalar()
        yc_companies = (await session.execute(select(func.count(YCCompany.id)))).scalar()
        so_questions = (await session.execute(select(func.count(SOQuestion.id)))).scalar()
        ph_launches = (await session.execute(select(func.count(PHLaunch.id)))).scalar()

    async with async_session() as session:
        product_reviews_count = (await session.execute(select(func.count(ProductReview.id)))).scalar()
        gig_posts_count = (await session.execute(select(func.count(GigPost.id)))).scalar()
        research_projects_count = (await session.execute(select(func.count(ResearchProject.id)))).scalar()

    return {
        "users": users,
        "posts": posts,
        "personas": personas,
        "topics": topics_count,
        "topic_mentions": mentions,
        "graph_edges": graph_edges,
        "news_events": news_events,
        "scraper_runs": scraper_runs,
        "discovered_products": products,
        "product_mentions": product_mentions,
        "migrations": migrations,
        "pain_points": pain_points,
        "hype_index": hype_index,
        "leader_shifts": leader_shifts,
        "platform_tones": platform_tones,
        "funding_rounds": funding_rounds,
        "agent_runs": agent_runs,
        "research_pipeline": research_pipeline,
        "traction_scores": traction_scores,
        "technology_lifecycle": tech_lifecycle,
        "market_gaps": market_gaps,
        "competitive_threats": competitive_threats,
        "platform_divergence": platform_divergence,
        "github_repos": github_repos,
        "hf_models": hf_models,
        "package_downloads": package_downloads,
        "yc_companies": yc_companies,
        "so_questions": so_questions,
        "ph_launches": ph_launches,
        "product_reviews": product_reviews_count,
        "gig_posts": gig_posts_count,
        "research_projects": research_projects_count,
    }


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
