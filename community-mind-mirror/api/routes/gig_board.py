"""API routes for the AI Gig Board — informal hiring/freelance posts from Reddit."""

from fastapi import APIRouter, Query
from sqlalchemy import select, func, text

from api.models.schemas import PaginatedResponse, GigPostResponse
from database.connection import async_session, GigPost

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[GigPostResponse])
async def list_gigs(
    project_type: str | None = None,
    need_category: str | None = None,
    remote_policy: str | None = None,
    min_budget: float | None = None,
    sort_by: str = Query("posted_at", pattern="^(posted_at|budget_max_usd)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List gig posts with filtering and pagination."""
    async with async_session() as session:
        base = select(GigPost).where(GigPost.is_gig == True)

        if project_type:
            base = base.where(GigPost.project_type == project_type)
        if need_category:
            base = base.where(GigPost.need_category == need_category)
        if remote_policy:
            base = base.where(GigPost.remote_policy == remote_policy)
        if min_budget is not None:
            base = base.where(GigPost.budget_max_usd >= min_budget)

        # Count
        count_q = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Sort
        if sort_by == "budget_max_usd":
            base = base.order_by(GigPost.budget_max_usd.desc().nullslast())
        else:
            base = base.order_by(GigPost.posted_at.desc().nullslast())

        # Paginate
        rows = (await session.execute(
            base.offset((page - 1) * per_page).limit(per_page)
        )).scalars().all()

        items = [GigPostResponse.model_validate(r) for r in rows]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/summary")
async def gig_summary():
    """Aggregate gig board stats."""
    async with async_session() as session:
        total = (await session.execute(
            select(func.count(GigPost.id)).where(GigPost.is_gig == True)
        )).scalar() or 0

        # By project type
        type_dist = {}
        result = await session.execute(
            select(GigPost.project_type, func.count(GigPost.id))
            .where(GigPost.is_gig == True)
            .group_by(GigPost.project_type)
        )
        for ptype, count in result.all():
            type_dist[ptype or "unknown"] = count

        # By need category
        category_dist = {}
        result = await session.execute(
            select(GigPost.need_category, func.count(GigPost.id))
            .where(GigPost.is_gig == True)
            .group_by(GigPost.need_category)
        )
        for cat, count in result.all():
            category_dist[cat or "unknown"] = count

        # Budget stats
        budget_stats = (await session.execute(
            select(
                func.avg(GigPost.budget_min_usd),
                func.avg(GigPost.budget_max_usd),
                func.min(GigPost.budget_min_usd),
                func.max(GigPost.budget_max_usd),
            ).where(GigPost.is_gig == True).where(GigPost.budget_max_usd.isnot(None))
        )).one()

        # Top tech stacks
        tech_stacks = (await session.execute(text("""
            SELECT tech, COUNT(*) as cnt
            FROM gig_posts, jsonb_array_elements_text(tech_stack) AS tech
            WHERE is_gig = true
            GROUP BY tech ORDER BY cnt DESC LIMIT 15
        """))).all()

        # Remote distribution
        remote_dist = {}
        result = await session.execute(
            select(GigPost.remote_policy, func.count(GigPost.id))
            .where(GigPost.is_gig == True)
            .group_by(GigPost.remote_policy)
        )
        for policy, count in result.all():
            remote_dist[policy or "unknown"] = count

    return {
        "total_gigs": total,
        "by_project_type": type_dist,
        "by_need_category": category_dist,
        "budget": {
            "avg_min": round(budget_stats[0], 0) if budget_stats[0] else None,
            "avg_max": round(budget_stats[1], 0) if budget_stats[1] else None,
            "min": budget_stats[2],
            "max": budget_stats[3],
        },
        "top_tech_stacks": [{"tech": r[0], "count": r[1]} for r in tech_stacks],
        "by_remote_policy": remote_dist,
    }


@router.get("/trends")
async def gig_trends():
    """Weekly gig volume trend."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT date_trunc('week', posted_at)::date AS week,
                   COUNT(*) AS gig_count
            FROM gig_posts
            WHERE posted_at IS NOT NULL AND is_gig = true
            GROUP BY week
            ORDER BY week DESC
            LIMIT 12
        """))
        weeks = result.all()

    return {
        "weekly_trend": [
            {"week": str(w[0]), "count": w[1]} for w in reversed(weeks)
        ]
    }
