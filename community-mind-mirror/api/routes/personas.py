"""Persona routes — listing, detail, posts, and graph connections."""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    PersonaResponse, PersonaDetailResponse, PostResponse,
    PaginatedResponse, GraphEdgeResponse,
)
from database.connection import Persona, User, Post, Platform, CommunityGraph
from scrapers.base_scraper import _utc_naive

router = APIRouter()


@router.get("", response_model=PaginatedResponse[PersonaResponse])
async def list_personas(
    platform: str | None = None,
    inferred_role: str | None = None,
    inferred_location: str | None = None,
    min_influence_score: float | None = None,
    search: str | None = None,
    sort_by: str = Query("influence_score", pattern="^(influence_score|username)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of personas with filters."""
    stmt = (
        select(Persona, User.username, Platform.name.label("pname"))
        .join(User, Persona.user_id == User.id)
        .join(Platform, User.platform_id == Platform.id)
    )
    count_base = (
        select(func.count(Persona.id))
        .join(User, Persona.user_id == User.id)
        .join(Platform, User.platform_id == Platform.id)
    )

    if platform:
        stmt = stmt.where(Platform.name == platform)
        count_base = count_base.where(Platform.name == platform)
    if inferred_role:
        stmt = stmt.where(Persona.inferred_role == inferred_role)
        count_base = count_base.where(Persona.inferred_role == inferred_role)
    if inferred_location:
        stmt = stmt.where(Persona.inferred_location.ilike(f"%{inferred_location}%"))
        count_base = count_base.where(Persona.inferred_location.ilike(f"%{inferred_location}%"))
    if min_influence_score is not None:
        stmt = stmt.where(Persona.influence_score >= min_influence_score)
        count_base = count_base.where(Persona.influence_score >= min_influence_score)
    if search:
        stmt = stmt.where(User.username.ilike(f"%{search}%"))
        count_base = count_base.where(User.username.ilike(f"%{search}%"))

    total = (await db.execute(count_base)).scalar()

    if sort_by == "username":
        stmt = stmt.order_by(User.username)
    else:
        stmt = stmt.order_by(Persona.influence_score.desc())

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)

    items = [
        PersonaResponse(
            id=p.id, user_id=p.user_id, username=uname, platform_name=pname,
            core_beliefs=p.core_beliefs, communication_style=p.communication_style,
            emotional_triggers=p.emotional_triggers, expertise_domains=p.expertise_domains,
            influence_type=p.influence_type, influence_score=p.influence_score,
            inferred_location=p.inferred_location, inferred_role=p.inferred_role,
            personality_summary=p.personality_summary, active_topics=p.active_topics,
            model_used=p.model_used, extracted_at=p.extracted_at,
        )
        for p, uname, pname in result.all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{persona_id}", response_model=PersonaDetailResponse)
async def get_persona(persona_id: int, db: AsyncSession = Depends(get_db)):
    """Full persona detail with posts and connections."""
    result = await db.execute(
        select(Persona, User.username, Platform.name.label("pname"))
        .join(User, Persona.user_id == User.id)
        .join(Platform, User.platform_id == Platform.id)
        .where(Persona.id == persona_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Persona not found")

    persona, username, platform_name = row

    # Top 10 posts by score
    posts_result = await db.execute(
        select(Post, Platform.name.label("pname"))
        .join(Platform, Post.platform_id == Platform.id, isouter=True)
        .where(Post.user_id == persona.user_id)
        .order_by(Post.score.desc())
        .limit(10)
    )
    top_posts = [
        PostResponse(
            id=p.id, user_id=p.user_id, username=username, platform_name=pname,
            post_type=p.post_type, title=p.title, body=(p.body or "")[:500],
            url=p.url, subreddit=p.subreddit, score=p.score,
            num_comments=p.num_comments, posted_at=p.posted_at,
            sentiment=(p.raw_metadata or {}).get("sentiment"),
        )
        for p, pname in posts_result.all()
    ]

    # Top 10 connections
    connections = await _get_user_connections(db, persona.user_id, limit=10)

    return PersonaDetailResponse(
        id=persona.id, user_id=persona.user_id, username=username,
        platform_name=platform_name,
        core_beliefs=persona.core_beliefs, communication_style=persona.communication_style,
        emotional_triggers=persona.emotional_triggers, expertise_domains=persona.expertise_domains,
        influence_type=persona.influence_type, influence_score=persona.influence_score,
        inferred_location=persona.inferred_location, inferred_role=persona.inferred_role,
        personality_summary=persona.personality_summary, active_topics=persona.active_topics,
        system_prompt=persona.system_prompt, validation_score=persona.validation_score,
        model_used=persona.model_used, extracted_at=persona.extracted_at,
        top_posts=top_posts, connections=connections,
    )


@router.get("/{persona_id}/posts", response_model=PaginatedResponse[PostResponse])
async def get_persona_posts(
    persona_id: int,
    platform: str | None = None,
    post_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated posts by this persona's user."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    stmt = (
        select(Post, User.username, Platform.name.label("pname"))
        .join(User, Post.user_id == User.id, isouter=True)
        .join(Platform, Post.platform_id == Platform.id, isouter=True)
        .where(Post.user_id == persona.user_id)
    )
    count_stmt = select(func.count(Post.id)).where(Post.user_id == persona.user_id)

    if platform:
        stmt = stmt.where(Platform.name == platform)
    if post_type:
        stmt = stmt.where(Post.post_type == post_type)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(Post.posted_at.desc()).offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        PostResponse(
            id=p.id, user_id=p.user_id, username=uname, platform_name=pname,
            post_type=p.post_type, title=p.title, body=(p.body or "")[:500],
            url=p.url, subreddit=p.subreddit, score=p.score,
            num_comments=p.num_comments, posted_at=p.posted_at,
            sentiment=(p.raw_metadata or {}).get("sentiment"),
        )
        for p, uname, pname in result.all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{persona_id}/graph", response_model=list[GraphEdgeResponse])
async def get_persona_graph(
    persona_id: int,
    db: AsyncSession = Depends(get_db),
):
    """This persona's community graph connections."""
    persona = await db.get(Persona, persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    return await _get_user_connections(db, persona.user_id, limit=50)


async def _get_user_connections(
    db: AsyncSession, user_id: int, limit: int = 10
) -> list[GraphEdgeResponse]:
    """Get community graph connections for a user."""
    # Outgoing edges
    out_result = await db.execute(
        select(CommunityGraph, User.username)
        .join(User, CommunityGraph.target_user_id == User.id, isouter=True)
        .where(CommunityGraph.source_user_id == user_id)
        .order_by(CommunityGraph.interaction_count.desc())
        .limit(limit)
    )
    # Incoming edges
    in_result = await db.execute(
        select(CommunityGraph, User.username)
        .join(User, CommunityGraph.source_user_id == User.id, isouter=True)
        .where(CommunityGraph.target_user_id == user_id)
        .order_by(CommunityGraph.interaction_count.desc())
        .limit(limit)
    )

    edges = []
    seen = set()
    for edge, uname in list(out_result.all()) + list(in_result.all()):
        other_id = edge.target_user_id if edge.source_user_id == user_id else edge.source_user_id
        if other_id in seen:
            continue
        seen.add(other_id)
        edges.append(GraphEdgeResponse(
            connected_user_id=other_id,
            connected_username=uname,
            interaction_type=edge.interaction_type,
            interaction_count=edge.interaction_count,
            avg_sentiment=edge.avg_sentiment,
        ))

    edges.sort(key=lambda e: e.interaction_count or 0, reverse=True)
    return edges[:limit]
