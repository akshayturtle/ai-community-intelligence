"""Search route — full-text search across posts, news, topics, and users."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import SearchResults, PostResponse, NewsEventResponse, TopicResponse, UserResponse
from database.connection import Post, NewsEvent, Topic, User, Platform

router = APIRouter()


@router.get("", response_model=SearchResults)
async def search(
    q: str = Query(..., min_length=2, description="Search query"),
    db: AsyncSession = Depends(get_db),
):
    """Full-text search across posts, news, topics, and users."""
    pattern = f"%{q}%"

    # Posts (title + body)
    posts_result = await db.execute(
        select(Post, User.username, Platform.name.label("pname"))
        .join(User, Post.user_id == User.id, isouter=True)
        .join(Platform, Post.platform_id == Platform.id, isouter=True)
        .where(Post.title.ilike(pattern) | Post.body.ilike(pattern))
        .order_by(Post.score.desc())
        .limit(10)
    )
    posts = [
        PostResponse(
            id=p.id, user_id=p.user_id, username=uname, platform_name=pname,
            post_type=p.post_type, title=p.title, body=(p.body or "")[:300],
            url=p.url, subreddit=p.subreddit, score=p.score,
            posted_at=p.posted_at,
            sentiment=(p.raw_metadata or {}).get("sentiment"),
        )
        for p, uname, pname in posts_result.all()
    ]

    # News events
    news_result = await db.execute(
        select(NewsEvent)
        .where(NewsEvent.title.ilike(pattern) | NewsEvent.body.ilike(pattern))
        .order_by(NewsEvent.published_at.desc().nullslast())
        .limit(10)
    )
    news = [
        NewsEventResponse(
            id=n.id, source_type=n.source_type, source_name=n.source_name,
            title=n.title, url=n.url, published_at=n.published_at,
            entities=n.entities, sentiment=n.sentiment, magnitude=n.magnitude,
        )
        for n in news_result.scalars().all()
    ]

    # Topics
    topics_result = await db.execute(
        select(Topic)
        .where(Topic.name.ilike(pattern))
        .order_by(Topic.velocity.desc())
        .limit(10)
    )
    topics = [
        TopicResponse(
            id=t.id, name=t.name, slug=t.slug, description=t.description,
            velocity=t.velocity, total_mentions=t.total_mentions, status=t.status,
        )
        for t in topics_result.scalars().all()
    ]

    # Users
    users_result = await db.execute(
        select(User, Platform.name.label("pname"))
        .join(Platform, User.platform_id == Platform.id, isouter=True)
        .where(User.username.ilike(pattern))
        .order_by(User.karma_score.desc().nullslast())
        .limit(10)
    )
    users = [
        UserResponse(
            id=u.id, platform_id=u.platform_id, platform_name=pname,
            platform_user_id=u.platform_user_id, username=u.username,
            bio=u.bio, karma_score=u.karma_score,
        )
        for u, pname in users_result.all()
    ]

    return SearchResults(posts=posts, news=news, topics=topics, users=users)
