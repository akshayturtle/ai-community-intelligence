"""News routes — listing and detail for news events."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import NewsEventResponse, PaginatedResponse
from database.connection import NewsEvent, TopicMention, Post, Platform, User

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NewsEventResponse])
async def list_news(
    source_type: str | None = None,
    source_name: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = Query("published_at", pattern="^(published_at|created_at)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated news events with filters."""
    stmt = select(NewsEvent)
    count_stmt = select(func.count(NewsEvent.id))

    if source_type:
        stmt = stmt.where(NewsEvent.source_type == source_type)
        count_stmt = count_stmt.where(NewsEvent.source_type == source_type)
    if source_name:
        stmt = stmt.where(NewsEvent.source_name.ilike(f"%{source_name}%"))
        count_stmt = count_stmt.where(NewsEvent.source_name.ilike(f"%{source_name}%"))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(NewsEvent.title.ilike(pattern) | NewsEvent.body.ilike(pattern))
        count_stmt = count_stmt.where(NewsEvent.title.ilike(pattern) | NewsEvent.body.ilike(pattern))
    if date_from:
        stmt = stmt.where(NewsEvent.published_at >= date_from)
        count_stmt = count_stmt.where(NewsEvent.published_at >= date_from)
    if date_to:
        stmt = stmt.where(NewsEvent.published_at <= date_to)
        count_stmt = count_stmt.where(NewsEvent.published_at <= date_to)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(NewsEvent.published_at.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        NewsEventResponse(
            id=n.id, source_type=n.source_type, source_name=n.source_name,
            title=n.title, body=(n.body or "")[:500], url=n.url, authors=n.authors,
            published_at=n.published_at, categories=n.categories,
            entities=n.entities, sentiment=n.sentiment, magnitude=n.magnitude,
        )
        for n in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{news_id}", response_model=dict)
async def get_news(news_id: int, db: AsyncSession = Depends(get_db)):
    """Full news event detail with related community reactions."""
    event = await db.get(NewsEvent, news_id)
    if not event:
        raise HTTPException(status_code=404, detail="News event not found")

    # Related community posts via topic_mentions sharing same topics
    reactions = []
    mentions_result = await db.execute(
        select(TopicMention)
        .where(TopicMention.news_event_id == news_id)
    )
    topic_ids = [m.topic_id for m in mentions_result.scalars().all()]

    if topic_ids:
        # Find posts in those same topics
        posts_result = await db.execute(
            select(Post, User.username, Platform.name.label("pname"))
            .join(TopicMention, TopicMention.post_id == Post.id)
            .join(User, Post.user_id == User.id, isouter=True)
            .join(Platform, Post.platform_id == Platform.id, isouter=True)
            .where(TopicMention.topic_id.in_(topic_ids))
            .order_by(Post.score.desc())
            .limit(20)
        )
        for p, uname, pname in posts_result.all():
            reactions.append({
                "post_id": p.id, "username": uname, "platform": pname,
                "title": p.title, "score": p.score,
                "posted_at": str(p.posted_at) if p.posted_at else None,
                "sentiment": (p.raw_metadata or {}).get("sentiment", {}).get("compound"),
            })

    return {
        "event": NewsEventResponse(
            id=event.id, source_type=event.source_type, source_name=event.source_name,
            title=event.title, body=event.body, url=event.url, authors=event.authors,
            published_at=event.published_at, categories=event.categories,
            entities=event.entities, sentiment=event.sentiment, magnitude=event.magnitude,
        ),
        "reactions": reactions,
    }
