"""Topic routes — listing, detail, timeline, and posts."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, case, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    TopicResponse, TopicDetailResponse, TopicTimelineResponse,
    TopicTimelinePoint, PostResponse, PaginatedResponse, NewsEventResponse,
    PlatformToneResponse,
)
from database.connection import Topic, TopicMention, Post, NewsEvent, User, Platform, PlatformTone
from scrapers.base_scraper import _utc_naive

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TopicResponse])
async def list_topics(
    status: str | None = None,
    min_mentions: int | None = None,
    min_velocity: float | None = None,
    search: str | None = None,
    sort_by: str = Query("velocity", pattern="^(velocity|total_mentions|last_seen_at)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of topics with filters."""
    stmt = select(Topic)
    count_stmt = select(func.count(Topic.id))

    if status:
        stmt = stmt.where(Topic.status == status)
        count_stmt = count_stmt.where(Topic.status == status)
    if min_mentions is not None:
        stmt = stmt.where(Topic.total_mentions >= min_mentions)
        count_stmt = count_stmt.where(Topic.total_mentions >= min_mentions)
    if min_velocity is not None:
        stmt = stmt.where(Topic.velocity >= min_velocity)
        count_stmt = count_stmt.where(Topic.velocity >= min_velocity)
    if search:
        stmt = stmt.where(Topic.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(Topic.name.ilike(f"%{search}%"))

    total = (await db.execute(count_stmt)).scalar()

    sort_col = {"velocity": Topic.velocity.desc(), "total_mentions": Topic.total_mentions.desc(), "last_seen_at": Topic.last_seen_at.desc()}
    stmt = stmt.order_by(sort_col.get(sort_by, Topic.velocity.desc()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    topics = result.scalars().all()

    items = [
        TopicResponse(
            id=t.id, name=t.name, slug=t.slug, description=t.description,
            keywords=t.keywords, velocity=t.velocity, total_mentions=t.total_mentions,
            sentiment_distribution=t.sentiment_distribution, platforms_active=t.platforms_active,
            opinion_camps=t.opinion_camps, status=t.status,
            first_seen_at=t.first_seen_at, last_seen_at=t.last_seen_at,
        )
        for t in topics
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{topic_id}", response_model=TopicDetailResponse)
async def get_topic(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Full topic detail with top posts and related news."""
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    # Top 10 posts via topic_mentions
    posts_result = await db.execute(
        select(Post, User.username, Platform.name.label("pname"), TopicMention.relevance_score)
        .join(TopicMention, TopicMention.post_id == Post.id)
        .join(User, Post.user_id == User.id, isouter=True)
        .join(Platform, Post.platform_id == Platform.id, isouter=True)
        .where(TopicMention.topic_id == topic_id)
        .order_by(TopicMention.relevance_score.desc())
        .limit(10)
    )
    top_posts = [
        PostResponse(
            id=p.id, user_id=p.user_id, username=uname, platform_name=pname,
            post_type=p.post_type, title=p.title, body=(p.body or "")[:500],
            url=p.url, subreddit=p.subreddit, score=p.score,
            num_comments=p.num_comments, posted_at=p.posted_at,
            sentiment=(p.raw_metadata or {}).get("sentiment"),
        )
        for p, uname, pname, rel in posts_result.all()
    ]

    # Related news via topic_mentions
    news_result = await db.execute(
        select(NewsEvent)
        .join(TopicMention, TopicMention.news_event_id == NewsEvent.id)
        .where(TopicMention.topic_id == topic_id)
        .order_by(NewsEvent.published_at.desc().nullslast())
        .limit(10)
    )
    related_news = [
        NewsEventResponse(
            id=n.id, source_type=n.source_type, source_name=n.source_name,
            title=n.title, url=n.url, published_at=n.published_at,
            entities=n.entities, sentiment=n.sentiment, magnitude=n.magnitude,
        )
        for n in news_result.scalars().all()
    ]

    return TopicDetailResponse(
        id=topic.id, name=topic.name, slug=topic.slug, description=topic.description,
        keywords=topic.keywords, velocity=topic.velocity, total_mentions=topic.total_mentions,
        sentiment_distribution=topic.sentiment_distribution, platforms_active=topic.platforms_active,
        opinion_camps=topic.opinion_camps, status=topic.status,
        first_seen_at=topic.first_seen_at, last_seen_at=topic.last_seen_at,
        top_posts=top_posts, related_news=related_news,
    )


@router.get("/{topic_id}/timeline", response_model=TopicTimelineResponse)
async def get_topic_timeline(topic_id: int, db: AsyncSession = Depends(get_db)):
    """Sentiment trajectory over last 30 days in daily buckets."""
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    cutoff = _utc_naive() - timedelta(days=30)

    day_col = func.date_trunc("day", TopicMention.created_at).label("day")
    result = await db.execute(
        select(
            day_col,
            func.count(TopicMention.id).label("total"),
            func.avg(TopicMention.sentiment).label("avg_sent"),
            func.sum(case((TopicMention.sentiment > 0.05, 1), else_=0)).label("pos"),
            func.sum(case((TopicMention.sentiment < -0.05, 1), else_=0)).label("neg"),
        )
        .where(TopicMention.topic_id == topic_id, TopicMention.created_at >= cutoff)
        .group_by(day_col)
        .order_by(day_col)
    )
    rows = result.all()

    timeline = []
    for day, total, avg_sent, pos_count, neg_count in rows:
        pos_count = pos_count or 0
        neg_count = neg_count or 0
        neutral_count = (total or 0) - pos_count - neg_count
        timeline.append(TopicTimelinePoint(
            date=str(day.date()) if day else "",
            positive_count=pos_count,
            negative_count=neg_count,
            neutral_count=max(neutral_count, 0),
            avg_sentiment=round(float(avg_sent), 4) if avg_sent else None,
        ))

    return TopicTimelineResponse(topic_id=topic.id, topic_name=topic.name, timeline=timeline)


@router.get("/{topic_id}/posts", response_model=PaginatedResponse[PostResponse])
async def get_topic_posts(
    topic_id: int,
    platform: str | None = None,
    sentiment: str | None = None,
    sort_by: str = Query("relevance_score", pattern="^(relevance_score|posted_at|score)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated posts linked to this topic."""
    base = (
        select(Post, User.username, Platform.name.label("pname"), TopicMention.relevance_score)
        .join(TopicMention, TopicMention.post_id == Post.id)
        .join(User, Post.user_id == User.id, isouter=True)
        .join(Platform, Post.platform_id == Platform.id, isouter=True)
        .where(TopicMention.topic_id == topic_id)
    )

    if platform:
        base = base.where(Platform.name == platform)

    # Count
    count_stmt = select(func.count()).select_from(
        select(Post.id)
        .join(TopicMention, TopicMention.post_id == Post.id)
        .where(TopicMention.topic_id == topic_id)
        .subquery()
    )
    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "relevance_score": TopicMention.relevance_score.desc(),
        "posted_at": Post.posted_at.desc(),
        "score": Post.score.desc(),
    }
    base = base.order_by(sort_map.get(sort_by, TopicMention.relevance_score.desc()))
    base = base.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(base)
    items = [
        PostResponse(
            id=p.id, user_id=p.user_id, username=uname, platform_name=pname,
            post_type=p.post_type, title=p.title, body=(p.body or "")[:500],
            url=p.url, subreddit=p.subreddit, score=p.score,
            num_comments=p.num_comments, posted_at=p.posted_at,
            sentiment=(p.raw_metadata or {}).get("sentiment"),
        )
        for p, uname, pname, rel in result.all()
    ]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{topic_id}/platform-tones", response_model=list[PlatformToneResponse])
async def get_topic_platform_tones(topic_id: int, db: AsyncSession = Depends(get_db)):
    """How each platform discusses this topic differently."""
    topic = await db.get(Topic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")

    result = await db.execute(
        select(PlatformTone)
        .where(PlatformTone.topic_id == topic_id)
        .order_by(PlatformTone.post_count.desc().nullslast())
    )
    tones = result.scalars().all()

    return [
        PlatformToneResponse(
            id=t.id, topic_id=t.topic_id, platform_name=t.platform_name,
            tone_description=t.tone_description, post_count=t.post_count,
            avg_sentiment=t.avg_sentiment, analyzed_at=t.analyzed_at,
        )
        for t in tones
    ]
