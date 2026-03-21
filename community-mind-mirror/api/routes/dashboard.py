"""Dashboard routes — power the main dashboard panels."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, case, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    DashboardPulseResponse, DashboardDebateResponse, LeaderResponse,
    ResearchRadarResponse, FundingSignalResponse, JobTrendResponse,
    GeoDistributionResponse, NewsImpactResponse, OverviewResponse,
    TopicResponse, NewsEventResponse,
    HypeIndexResponse, PainPointResponse, LeaderShiftResponse, FundingRoundResponse,
    CrossSourceHighlight,
)
from database.connection import (
    User, Post, Persona, Topic, TopicMention, NewsEvent,
    CommunityGraph, ScraperRun, Platform,
    HypeIndex, PainPoint, LeaderShift, FundingRound, AgentRun,
    MarketGap, CompetitiveThreat, PlatformDivergence, TractionScore,
    JobListing,
)
from scrapers.base_scraper import _utc_naive

router = APIRouter()

# Platform ID → name cache
PLATFORM_NAMES = {
    1: "reddit", 2: "hackernews", 3: "youtube", 4: "twitter",
    5: "linkedin", 6: "producthunt", 7: "stackoverflow",
    8: "discord", 9: "mastodon", 10: "bluesky",
}


@router.get("/pulse", response_model=DashboardPulseResponse)
async def dashboard_pulse(
    status: str | None = None,
    min_velocity: float | None = None,
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Top 20 trending topics sorted by velocity."""
    stmt = select(Topic).order_by(Topic.velocity.desc()).limit(20)
    if status:
        stmt = stmt.where(Topic.status == status)
    if min_velocity is not None:
        stmt = stmt.where(Topic.velocity >= min_velocity)

    result = await db.execute(stmt)
    topics = result.scalars().all()

    items = []
    for t in topics:
        # Filter by platform if specified
        if platform and t.platforms_active:
            if platform not in t.platforms_active:
                continue
        items.append(TopicResponse(
            id=t.id, name=t.name, slug=t.slug, description=t.description,
            keywords=t.keywords, velocity=t.velocity, total_mentions=t.total_mentions,
            sentiment_distribution=t.sentiment_distribution, platforms_active=t.platforms_active,
            opinion_camps=t.opinion_camps, status=t.status,
            first_seen_at=t.first_seen_at, last_seen_at=t.last_seen_at,
        ))
    return DashboardPulseResponse(topics=items)


@router.get("/debates", response_model=DashboardDebateResponse)
async def dashboard_debates(db: AsyncSession = Depends(get_db)):
    """Top 10 most polarizing topics (smallest gap between positive/negative)."""
    result = await db.execute(
        select(Topic)
        .where(Topic.sentiment_distribution.isnot(None), Topic.total_mentions > 0)
        .order_by(Topic.total_mentions.desc())
        .limit(50)
    )
    topics = result.scalars().all()

    debates = []
    for t in topics:
        sd = t.sentiment_distribution or {}
        pos = sd.get("positive", 0)
        neg = sd.get("negative", 0)
        polarization = abs(pos - neg)
        debates.append({
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "opinion_camps": t.opinion_camps,
            "sentiment_distribution": sd,
            "total_mentions": t.total_mentions,
            "polarization_score": round(polarization, 4),
        })

    # Sort by polarization ascending (most divided first)
    debates.sort(key=lambda d: d["polarization_score"])
    return DashboardDebateResponse(debates=debates[:10])


@router.get("/leaders", response_model=list[LeaderResponse])
async def dashboard_leaders(
    platform: str | None = None,
    role: str | None = None,
    min_influence_score: float | None = None,
    location: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Top opinion leaders sorted by influence_score."""
    stmt = (
        select(Persona, User.username, Platform.name.label("platform_name"))
        .join(User, Persona.user_id == User.id)
        .join(Platform, User.platform_id == Platform.id)
        .order_by(Persona.influence_score.desc())
        .limit(limit)
    )
    if role:
        stmt = stmt.where(Persona.inferred_role == role)
    if min_influence_score is not None:
        stmt = stmt.where(Persona.influence_score >= min_influence_score)
    if location:
        stmt = stmt.where(Persona.inferred_location.ilike(f"%{location}%"))
    if platform:
        stmt = stmt.where(Platform.name == platform)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        LeaderResponse(
            id=p.id, user_id=p.user_id, username=uname,
            platform_name=pname, influence_score=p.influence_score,
            inferred_role=p.inferred_role, inferred_location=p.inferred_location,
            personality_summary=p.personality_summary,
            core_beliefs=p.core_beliefs, active_topics=p.active_topics,
        )
        for p, uname, pname in rows
    ]


@router.get("/research", response_model=ResearchRadarResponse)
async def dashboard_research(
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recent ArXiv papers from last 30 days."""
    cutoff = _utc_naive() - timedelta(days=30)
    result = await db.execute(
        select(NewsEvent)
        .where(NewsEvent.source_type == "arxiv", NewsEvent.published_at >= cutoff)
        .order_by(NewsEvent.published_at.desc())
        .limit(limit)
    )
    papers = result.scalars().all()
    return ResearchRadarResponse(papers=[
        NewsEventResponse(
            id=p.id, source_type=p.source_type, source_name=p.source_name,
            title=p.title, body=p.body, url=p.url, authors=p.authors,
            published_at=p.published_at, categories=p.categories,
            entities=p.entities, sentiment=p.sentiment, magnitude=p.magnitude,
        ) for p in papers
    ])


@router.get("/funding", response_model=FundingSignalResponse)
async def dashboard_funding(
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Funding-related news from last 30 days."""
    cutoff = _utc_naive() - timedelta(days=30)
    result = await db.execute(
        select(NewsEvent)
        .where(
            NewsEvent.source_type == "news",
            NewsEvent.published_at >= cutoff,
        )
        .order_by(NewsEvent.published_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    # Filter for funding-related by entities.sector or keywords in title
    funding_events = []
    for e in events:
        entities = e.entities or {}
        sector = entities.get("sector", "")
        title_lower = (e.title or "").lower()
        if "funding" in sector.lower() or any(
            kw in title_lower for kw in ["funding", "raised", "invest", "valuation", "series", "ipo"]
        ):
            funding_events.append(e)

    return FundingSignalResponse(events=[
        NewsEventResponse(
            id=e.id, source_type=e.source_type, source_name=e.source_name,
            title=e.title, body=e.body, url=e.url, authors=e.authors,
            published_at=e.published_at, categories=e.categories,
            entities=e.entities, sentiment=e.sentiment, magnitude=e.magnitude,
        ) for e in funding_events[:limit]
    ])


@router.get("/jobs", response_model=JobTrendResponse)
async def dashboard_jobs(db: AsyncSession = Depends(get_db)):
    """Job trend aggregation + recent listings."""
    now = _utc_naive()

    effective_date = func.coalesce(JobListing.published_at, JobListing.created_at)

    # Weekly counts for last 90 days
    cutoff_90 = now - timedelta(days=90)
    result = await db.execute(
        select(
            func.date_trunc("week", effective_date).label("week"),
            func.count(JobListing.id).label("count"),
        )
        .where(effective_date >= cutoff_90)
        .group_by(text("1"))
        .order_by(text("1"))
    )
    weekly = [{"week": str(row[0]), "count": row[1]} for row in result.all()]

    # Recent listings (last 7 days)
    cutoff_7 = now - timedelta(days=7)
    result = await db.execute(
        select(JobListing)
        .where(effective_date >= cutoff_7)
        .order_by(effective_date.desc())
        .limit(50)
    )
    listings = result.scalars().all()
    recent = [
        {
            "id": j.id, "title": j.title, "url": j.url,
            "published_at": str(j.published_at or j.created_at) if (j.published_at or j.created_at) else None,
            "metadata": {
                "company": j.company, "location": j.location,
                "salary_min": j.salary_min, "salary_max": j.salary_max,
                "remote": j.remote, "source": j.source,
            },
        }
        for j in listings
    ]

    # Aggregate by role for dashboard cards
    role_keywords = {
        "ML Engineer": ["machine learning engineer", "ml engineer", "mle"],
        "Data Scientist": ["data scientist", "data science"],
        "AI Engineer": ["ai engineer", "artificial intelligence engineer", "ai architect"],
        "Backend Engineer": ["backend engineer", "back-end engineer", "server engineer", "software engineer"],
        "Full Stack": ["full stack", "fullstack"],
        "DevOps / MLOps": ["devops", "mlops", "platform engineer", "sre"],
        "Product Manager": ["product manager", "pm"],
        "Research Scientist": ["research scientist", "researcher"],
    }
    cutoff_30 = now - timedelta(days=30)
    all_jobs_result = await db.execute(
        select(JobListing)
        .where(effective_date >= cutoff_90)
    )
    all_jobs = all_jobs_result.scalars().all()

    role_counts: dict[str, dict] = {role: {"total": 0, "recent_30d": 0} for role in role_keywords}
    for job in all_jobs:
        title_lower = (job.title or "").lower()
        for role, keywords in role_keywords.items():
            if any(kw in title_lower for kw in keywords):
                role_counts[role]["total"] += 1
                job_date = job.published_at or job.created_at
                if job_date and job_date >= cutoff_30:
                    role_counts[role]["recent_30d"] += 1

    role_cards = []
    for role, data in sorted(role_counts.items(), key=lambda x: x[1]["total"], reverse=True):
        if data["total"] > 0:
            older = data["total"] - data["recent_30d"]
            growth = round(((data["recent_30d"] - older) / older) * 100) if older > 0 else (100 if data["recent_30d"] > 0 else 0)
            role_cards.append({"role": role, "count": data["total"], "growth": growth})

    return JobTrendResponse(weekly_counts=weekly, recent_listings=recent, role_cards=role_cards)


@router.get("/news-impact", response_model=list[NewsImpactResponse])
async def dashboard_news_impact(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """High-impact news events with community reaction data."""
    result = await db.execute(
        select(NewsEvent)
        .where(NewsEvent.magnitude.in_(["high", "critical"]))
        .order_by(NewsEvent.published_at.desc().nullslast())
        .limit(limit)
    )
    events = result.scalars().all()

    impacts = []
    for event in events:
        # Find related posts via topic_mentions
        mentions_result = await db.execute(
            select(TopicMention, Post, Platform.name)
            .join(Post, TopicMention.post_id == Post.id, isouter=True)
            .join(Platform, Post.platform_id == Platform.id, isouter=True)
            .where(TopicMention.news_event_id == event.id)
            .limit(20)
        )
        mention_rows = mentions_result.all()

        reactions = []
        platforms_reacted = set()
        sentiments = []
        for mention, post, pname in mention_rows:
            if post:
                platforms_reacted.add(pname or "unknown")
                sentiment_data = (post.raw_metadata or {}).get("sentiment", {})
                compound = sentiment_data.get("compound", 0)
                sentiments.append(compound)
                reactions.append({
                    "post_id": post.id, "platform": pname,
                    "title": post.title, "score": post.score,
                    "sentiment": compound, "posted_at": str(post.posted_at),
                })

        impacts.append(NewsImpactResponse(
            event=NewsEventResponse(
                id=event.id, source_type=event.source_type, source_name=event.source_name,
                title=event.title, body=event.body, url=event.url, authors=event.authors,
                published_at=event.published_at, categories=event.categories,
                entities=event.entities, sentiment=event.sentiment, magnitude=event.magnitude,
            ),
            reactions=reactions,
            platforms_reacted=list(platforms_reacted),
            avg_community_sentiment=round(sum(sentiments) / len(sentiments), 4) if sentiments else None,
        ))

    return impacts


@router.get("/geo", response_model=GeoDistributionResponse)
async def dashboard_geo(db: AsyncSession = Depends(get_db)):
    """Aggregate personas by inferred_location."""
    result = await db.execute(
        select(
            Persona.inferred_location,
            func.count(Persona.id).label("user_count"),
            func.avg(Persona.influence_score).label("avg_influence"),
        )
        .where(Persona.inferred_location.isnot(None), Persona.inferred_location != "")
        .group_by(Persona.inferred_location)
        .having(func.count(Persona.id) >= 1)
        .order_by(desc("user_count"))
    )
    rows = result.all()

    locations = []
    for loc, count, avg_inf in rows:
        # Get top topics for this location
        topic_result = await db.execute(
            select(Persona.active_topics)
            .where(Persona.inferred_location == loc, Persona.active_topics.isnot(None))
            .limit(5)
        )
        all_topics = []
        for (topics_list,) in topic_result.all():
            if isinstance(topics_list, list):
                all_topics.extend(topics_list)
        # Most common topics
        topic_counts = {}
        for t in all_topics:
            topic_counts[t] = topic_counts.get(t, 0) + 1
        top_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:5]

        locations.append({
            "location": loc,
            "user_count": count,
            "avg_influence": round(float(avg_inf or 0), 4),
            "top_topics": top_topics,
        })

    return GeoDistributionResponse(locations=locations)


@router.get("/overview", response_model=OverviewResponse)
async def dashboard_overview(db: AsyncSession = Depends(get_db)):
    """Combined summary endpoint."""
    # Counts
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_personas = (await db.execute(select(func.count(Persona.id)))).scalar()
    total_posts = (await db.execute(select(func.count(Post.id)))).scalar()
    total_topics = (await db.execute(select(func.count(Topic.id)))).scalar()

    # News by source type
    news_result = await db.execute(
        select(NewsEvent.source_type, func.count(NewsEvent.id))
        .group_by(NewsEvent.source_type)
    )
    news_by_source = {stype: count for stype, count in news_result.all()}

    # Top 5 trending topics
    topics_result = await db.execute(
        select(Topic).order_by(Topic.velocity.desc()).limit(5)
    )
    trending = [
        TopicResponse(
            id=t.id, name=t.name, slug=t.slug, velocity=t.velocity,
            total_mentions=t.total_mentions, status=t.status,
            sentiment_distribution=t.sentiment_distribution,
            platforms_active=t.platforms_active,
        )
        for t in topics_result.scalars().all()
    ]

    # Top 5 leaders
    leaders_result = await db.execute(
        select(Persona, User.username, Platform.name.label("pname"))
        .join(User, Persona.user_id == User.id)
        .join(Platform, User.platform_id == Platform.id)
        .order_by(Persona.influence_score.desc())
        .limit(5)
    )
    top_leaders = [
        LeaderResponse(
            id=p.id, user_id=p.user_id, username=uname,
            platform_name=pname, influence_score=p.influence_score,
            inferred_role=p.inferred_role,
        )
        for p, uname, pname in leaders_result.all()
    ]

    # Latest 5 news
    news_latest = await db.execute(
        select(NewsEvent)
        .where(NewsEvent.source_type == "news")
        .order_by(NewsEvent.published_at.desc().nullslast())
        .limit(5)
    )
    latest_news = [
        NewsEventResponse(
            id=n.id, source_type=n.source_type, source_name=n.source_name,
            title=n.title, url=n.url, published_at=n.published_at,
            sentiment=n.sentiment, magnitude=n.magnitude,
        )
        for n in news_latest.scalars().all()
    ]

    # Scraper health
    scraper_names = ["reddit_scraper", "hn_scraper", "youtube_scraper", "news_scraper", "arxiv_scraper", "job_scraper"]
    health = []
    for sname in scraper_names:
        run_result = await db.execute(
            select(ScraperRun)
            .where(ScraperRun.scraper_name == sname)
            .order_by(ScraperRun.started_at.desc())
            .limit(1)
        )
        run = run_result.scalar_one_or_none()
        if run:
            health.append({
                "scraper": sname,
                "status": run.status,
                "last_run": str(run.started_at) if run.started_at else None,
                "records_fetched": run.records_fetched,
            })
        else:
            health.append({"scraper": sname, "status": "never_run", "last_run": None})

    return OverviewResponse(
        total_users=total_users, total_personas=total_personas,
        total_posts=total_posts, total_topics=total_topics,
        news_by_source=news_by_source, trending_topics=trending,
        top_leaders=top_leaders, latest_news=latest_news,
        scraper_health=health,
    )


# ── New Intelligence Dashboard Endpoints ────────────────────────────


@router.get("/hype-index", response_model=list[HypeIndexResponse])
async def dashboard_hype_index(
    status: str | None = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Hype vs Reality Index — press sentiment vs builder sentiment gap."""
    stmt = (
        select(HypeIndex, Topic.name.label("topic_name"))
        .join(Topic, HypeIndex.topic_id == Topic.id, isouter=True)
        .order_by(HypeIndex.gap.desc().nullslast())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(HypeIndex.status == status)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        HypeIndexResponse(
            id=h.id, topic_id=h.topic_id, sector_name=h.sector_name,
            topic_name=tname, builder_sentiment=h.builder_sentiment,
            vc_sentiment=h.vc_sentiment, gap=h.gap, status=h.status,
            builder_post_count=h.builder_post_count, vc_post_count=h.vc_post_count,
            calculated_at=h.calculated_at,
        )
        for h, tname in rows
    ]


@router.get("/pain-points", response_model=list[PainPointResponse])
async def dashboard_pain_points(
    has_solution: bool | None = None,
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Community pain points sorted by intensity."""
    stmt = (
        select(PainPoint)
        .where(PainPoint.status == "active")
        .order_by(PainPoint.intensity_score.desc().nullslast())
        .limit(limit)
    )
    if has_solution is not None:
        stmt = stmt.where(PainPoint.has_solution == has_solution)

    result = await db.execute(stmt)
    points = result.scalars().all()

    # Deduplicate by normalized title (word-overlap Jaccard >= 0.5)
    # Keep the entry with the highest post_count among duplicates
    import string

    def _norm(title: str) -> set[str]:
        t = title.lower().strip().translate(str.maketrans("", "", string.punctuation))
        return set(t.split())

    seen: list[tuple[set[str], int]] = []  # (word_set, index_in_items)
    items = []
    for pp in points:
        words = _norm(pp.title)
        is_dup = False
        for existing_words, idx in seen:
            if not words or not existing_words:
                continue
            jaccard = len(words & existing_words) / len(words | existing_words)
            if jaccard >= 0.5:
                # Keep the one with higher post_count; replace if new one is better
                if (pp.post_count or 0) > (items[idx].post_count or 0):
                    # Replace the weaker duplicate
                    topic_name = None
                    if pp.topic_id:
                        topic = await db.get(Topic, pp.topic_id)
                        topic_name = topic.name if topic else None
                    items[idx] = PainPointResponse(
                        id=pp.id, title=pp.title, description=pp.description,
                        intensity_score=pp.intensity_score, has_solution=pp.has_solution,
                        mentioned_products=pp.mentioned_products, platforms=pp.platforms,
                        sample_quotes=pp.sample_quotes, topic_id=pp.topic_id,
                        topic_name=topic_name, post_count=pp.post_count,
                        status=pp.status, created_at=pp.created_at,
                    )
                is_dup = True
                break
        if not is_dup:
            topic_name = None
            if pp.topic_id:
                topic = await db.get(Topic, pp.topic_id)
                topic_name = topic.name if topic else None
            idx = len(items)
            items.append(PainPointResponse(
                id=pp.id, title=pp.title, description=pp.description,
                intensity_score=pp.intensity_score, has_solution=pp.has_solution,
                mentioned_products=pp.mentioned_products, platforms=pp.platforms,
                sample_quotes=pp.sample_quotes, topic_id=pp.topic_id,
                topic_name=topic_name, post_count=pp.post_count,
                status=pp.status, created_at=pp.created_at,
            ))
            seen.append((words, idx))

    return items


@router.get("/leader-shifts", response_model=list[LeaderShiftResponse])
async def dashboard_leader_shifts(
    shift_type: str | None = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Recent leader opinion shifts."""
    from database.connection import Persona, User

    stmt = (
        select(LeaderShift, User.username.label("persona_name"))
        .join(Persona, LeaderShift.persona_id == Persona.id, isouter=True)
        .join(User, Persona.user_id == User.id, isouter=True)
        .order_by(LeaderShift.detected_at.desc().nullslast())
        .limit(limit)
    )
    if shift_type:
        stmt = stmt.where(LeaderShift.shift_type == shift_type)

    result = await db.execute(stmt)
    rows = result.all()

    return [
        LeaderShiftResponse(
            id=ls.id, persona_id=ls.persona_id, persona_name=pname,
            topic_id=ls.topic_id, topic_name=ls.topic_name,
            old_stance=ls.old_stance, new_stance=ls.new_stance,
            shift_type=ls.shift_type, trigger=ls.trigger,
            summary=ls.summary, old_sentiment=ls.old_sentiment,
            new_sentiment=ls.new_sentiment, detected_at=ls.detected_at,
        )
        for ls, pname in rows
    ]


@router.get("/funding-rounds", response_model=list[FundingRoundResponse])
async def dashboard_funding_rounds(
    stage: str | None = None,
    sector: str | None = None,
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Structured funding rounds with community reaction."""
    stmt = (
        select(FundingRound)
        .order_by(FundingRound.announced_at.desc().nullslast())
        .limit(limit)
    )
    if stage:
        stmt = stmt.where(FundingRound.stage == stage)
    if sector:
        stmt = stmt.where(FundingRound.sector.ilike(f"%{sector}%"))

    result = await db.execute(stmt)
    rounds = result.scalars().all()

    return [
        FundingRoundResponse(
            id=fr.id, company_name=fr.company_name, amount=fr.amount,
            stage=fr.stage, sector=fr.sector, location=fr.location,
            news_event_id=fr.news_event_id, community_sentiment=fr.community_sentiment,
            community_post_count=fr.community_post_count,
            reaction_summary=fr.reaction_summary, announced_at=fr.announced_at,
        )
        for fr in rounds
    ]


# ── Cross-Source Highlights ───────────────────────────────────────

@router.get("/cross-source-highlights", response_model=list[CrossSourceHighlight])
async def cross_source_highlights(
    limit: int = Query(10, le=30),
    db: AsyncSession = Depends(get_db),
):
    """Top cross-source intelligence highlights combining agent signals."""
    highlights = []

    # 1. Top market gaps (high opportunity, no products)
    gaps = await db.execute(
        select(MarketGap)
        .where(MarketGap.opportunity_score.isnot(None))
        .order_by(MarketGap.opportunity_score.desc())
        .limit(3)
    )
    for g in gaps.scalars().all():
        highlights.append(CrossSourceHighlight(
            type="insight",
            title=f"Market Gap: {g.problem_title}",
            description=f"Opportunity score {g.opportunity_score}, {g.complaint_count or 0} complaints, {g.existing_products or 0} existing products.",
            confidence="high" if (g.opportunity_score or 0) > 70 else "medium",
            signals_used=["market_gaps", "pain_points"],
            color="green",
        ))

    # 2. Top competitive threats
    threats = await db.execute(
        select(CompetitiveThreat)
        .where(CompetitiveThreat.threat_score.isnot(None))
        .order_by(CompetitiveThreat.threat_score.desc())
        .limit(2)
    )
    for c in threats.scalars().all():
        highlights.append(CrossSourceHighlight(
            type="alert",
            title=f"Competitive Threat: {c.competitor} vs {c.target_product}",
            description=f"Threat score {c.threat_score}, {c.migrations_away or 0} migrations away, {c.opinion_leaders_flipped or 0} leaders flipped.",
            confidence="high" if (c.threat_score or 0) > 70 else "medium",
            signals_used=["competitive_threats", "traction_scores"],
            color="red",
        ))

    # 3. High-divergence topics
    divergences = await db.execute(
        select(PlatformDivergence)
        .where(PlatformDivergence.max_divergence.isnot(None))
        .order_by(PlatformDivergence.max_divergence.desc())
        .limit(2)
    )
    for d in divergences.scalars().all():
        highlights.append(CrossSourceHighlight(
            type="trend",
            title=f"Platform Divergence: {d.topic_name}",
            description=f"Max divergence {d.max_divergence}. {d.divergence_direction or ''}",
            confidence="medium",
            signals_used=["platform_divergence"],
            color="yellow",
        ))

    # 4. Hype-only products (high traction label warnings)
    hype_products = await db.execute(
        select(TractionScore)
        .where(TractionScore.traction_label.in_(["hype_only", "hype-only"]))
        .order_by(TractionScore.calculated_at.desc())
        .limit(2)
    )
    for t in hype_products.scalars().all():
        flags = t.red_flags or []
        highlights.append(CrossSourceHighlight(
            type="alert",
            title=f"Hype Warning: {t.entity_name}",
            description=f"Traction score {t.traction_score}. Red flags: {', '.join(flags[:3]) if flags else 'none'}.",
            confidence="high",
            signals_used=["traction_scores"],
            color="red",
        ))

    # 5. Latest synthesizer insights (from agent_runs)
    synth = await db.execute(
        select(AgentRun)
        .where(AgentRun.agent_name == "insight_synthesizer", AgentRun.status == "success")
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    run = synth.scalar_one_or_none()
    if run and run.output_json:
        cards = run.output_json if isinstance(run.output_json, list) else []
        for card in cards[:3]:
            highlights.append(CrossSourceHighlight(
                type="insight",
                title=card.get("category", "insight").replace("_", " ").title(),
                description=card.get("insight", ""),
                confidence=card.get("confidence"),
                signals_used=card.get("signals_used"),
                color=card.get("color", "blue"),
            ))

    return highlights[:limit]
