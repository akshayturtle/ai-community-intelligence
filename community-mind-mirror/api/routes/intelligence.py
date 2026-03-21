"""Intelligence routes — products, migrations, pain points, job analysis."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    ProductResponse, MigrationResponse, MigrationAggregateResponse,
    PainPointResponse, PaginatedResponse,
)
from database.connection import (
    DiscoveredProduct, ProductMention, Migration, PainPoint,
    Post, NewsEvent, Topic, JobListing,
)
from scrapers.base_scraper import _utc_naive

router = APIRouter()


@router.get("/products", response_model=PaginatedResponse[ProductResponse])
async def list_products(
    category: str | None = None,
    status: str | None = None,
    search: str | None = None,
    sort_by: str = Query("total_mentions", pattern="^(total_mentions|confidence|canonical_name|last_seen_at)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Paginated product landscape with sentiment and recommendation rate."""
    stmt = select(DiscoveredProduct)
    count_stmt = select(func.count(DiscoveredProduct.id))

    if category:
        stmt = stmt.where(DiscoveredProduct.category == category)
        count_stmt = count_stmt.where(DiscoveredProduct.category == category)
    if status:
        stmt = stmt.where(DiscoveredProduct.status == status)
        count_stmt = count_stmt.where(DiscoveredProduct.status == status)
    if search:
        stmt = stmt.where(DiscoveredProduct.canonical_name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(DiscoveredProduct.canonical_name.ilike(f"%{search}%"))

    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "total_mentions": DiscoveredProduct.total_mentions.desc().nullslast(),
        "confidence": DiscoveredProduct.confidence.desc().nullslast(),
        "canonical_name": DiscoveredProduct.canonical_name.asc(),
        "last_seen_at": DiscoveredProduct.last_seen_at.desc().nullslast(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, DiscoveredProduct.total_mentions.desc().nullslast()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    products = result.scalars().all()

    items = []
    for p in products:
        # Calculate recommendation rate and avg sentiment from mentions
        mention_stats = await db.execute(
            select(
                func.count(ProductMention.id).label("total"),
                func.count(case((ProductMention.context_type == "recommendation", 1))).label("recs"),
                func.avg(ProductMention.sentiment).label("avg_sent"),
            ).where(ProductMention.product_id == p.id)
        )
        row = mention_stats.one()
        total_mentions = row.total or 0
        rec_rate = round(row.recs / total_mentions, 4) if total_mentions > 0 else None
        avg_sent = round(float(row.avg_sent), 4) if row.avg_sent is not None else None

        # Trend: compare last 7 days vs previous 7 days
        now = _utc_naive()
        recent = (await db.execute(
            select(func.count(ProductMention.id))
            .where(ProductMention.product_id == p.id, ProductMention.detected_at >= now - timedelta(days=7))
        )).scalar() or 0
        older = (await db.execute(
            select(func.count(ProductMention.id))
            .where(
                ProductMention.product_id == p.id,
                ProductMention.detected_at >= now - timedelta(days=14),
                ProductMention.detected_at < now - timedelta(days=7),
            )
        )).scalar() or 0

        if older == 0:
            trend = "up" if recent > 0 else "stable"
        elif recent > older * 1.2:
            trend = "up"
        elif recent < older * 0.8:
            trend = "down"
        else:
            trend = "stable"

        items.append(ProductResponse(
            id=p.id,
            canonical_name=p.canonical_name,
            category=p.category,
            aliases=p.aliases,
            confidence=p.confidence,
            status=p.status,
            discovered_by=p.discovered_by,
            total_mentions=p.total_mentions or 0,
            last_seen_at=p.last_seen_at,
            recommendation_rate=rec_rate,
            avg_sentiment=avg_sent,
            trend=trend,
        ))

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/migrations", response_model=list[MigrationAggregateResponse])
async def list_migrations(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated migration patterns: FROM → TO with counts."""
    result = await db.execute(
        select(
            DiscoveredProduct.canonical_name.label("from_name"),
            func.min(Migration.to_product_id).label("to_id"),
            func.count(Migration.id).label("cnt"),
            func.avg(Migration.confidence).label("avg_conf"),
        )
        .join(DiscoveredProduct, Migration.from_product_id == DiscoveredProduct.id)
        .group_by(DiscoveredProduct.canonical_name, Migration.to_product_id)
        .order_by(desc("cnt"))
        .limit(limit)
    )
    rows = result.all()

    items = []
    for from_name, to_id, cnt, avg_conf in rows:
        # Get to_product name
        to_product = await db.get(DiscoveredProduct, to_id) if to_id else None
        to_name = to_product.canonical_name if to_product else "Unknown"
        items.append(MigrationAggregateResponse(
            from_product=from_name,
            to_product=to_name,
            count=cnt,
            avg_confidence=round(float(avg_conf), 4) if avg_conf else None,
        ))

    return items


@router.get("/migrations/raw", response_model=PaginatedResponse[MigrationResponse])
async def list_migrations_raw(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Raw migration records with details."""
    total = (await db.execute(select(func.count(Migration.id)))).scalar()

    result = await db.execute(
        select(Migration)
        .order_by(Migration.detected_at.desc().nullslast())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    migrations = result.scalars().all()

    items = []
    for m in migrations:
        from_p = await db.get(DiscoveredProduct, m.from_product_id) if m.from_product_id else None
        to_p = await db.get(DiscoveredProduct, m.to_product_id) if m.to_product_id else None
        items.append(MigrationResponse(
            id=m.id,
            from_product=from_p.canonical_name if from_p else "Unknown",
            to_product=to_p.canonical_name if to_p else "Unknown",
            from_product_id=m.from_product_id,
            to_product_id=m.to_product_id,
            reason=m.reason,
            confidence=m.confidence,
            confirmed_by=m.confirmed_by,
            detected_at=m.detected_at,
        ))

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/unmet-needs", response_model=list[PainPointResponse])
async def list_unmet_needs(
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Pain points without solutions — startup opportunities."""
    result = await db.execute(
        select(PainPoint)
        .where(PainPoint.has_solution == False)
        .where(PainPoint.status == "active")
        .order_by(PainPoint.intensity_score.desc().nullslast())
        .limit(limit)
    )
    points = result.scalars().all()

    items = []
    for pp in points:
        topic_name = None
        if pp.topic_id:
            topic = await db.get(Topic, pp.topic_id)
            topic_name = topic.name if topic else None
        items.append(PainPointResponse(
            id=pp.id, title=pp.title, description=pp.description,
            intensity_score=pp.intensity_score, has_solution=pp.has_solution,
            mentioned_products=pp.mentioned_products, platforms=pp.platforms,
            sample_quotes=pp.sample_quotes, topic_id=pp.topic_id,
            topic_name=topic_name, post_count=pp.post_count,
            status=pp.status, created_at=pp.created_at,
        ))

    return items


@router.get("/job-analysis")
async def job_analysis(db: AsyncSession = Depends(get_db)):
    """Job market analysis: role trends, salary insights, geo breakdown."""
    now = _utc_naive()
    cutoff_30 = now - timedelta(days=30)
    cutoff_90 = now - timedelta(days=90)

    effective_date = func.coalesce(JobListing.published_at, JobListing.created_at)
    result = await db.execute(
        select(JobListing)
        .where(effective_date >= cutoff_90)
        .order_by(effective_date.desc())
    )
    jobs = result.scalars().all()

    # Aggregate by role keywords
    role_keywords = {
        "ML Engineer": ["machine learning engineer", "ml engineer", "mle"],
        "Data Scientist": ["data scientist", "data science"],
        "AI Engineer": ["ai engineer", "artificial intelligence engineer"],
        "Backend Engineer": ["backend engineer", "back-end engineer", "server engineer"],
        "Full Stack": ["full stack", "fullstack"],
        "DevOps/MLOps": ["devops", "mlops", "platform engineer", "sre"],
        "Product Manager": ["product manager", "pm"],
        "Research Scientist": ["research scientist", "researcher"],
    }

    role_counts = {role: {"total": 0, "recent_30d": 0} for role in role_keywords}
    location_counts = {}

    for job in jobs:
        title_lower = (job.title or "").lower()
        location = job.location or ""

        if location:
            location_counts[location] = location_counts.get(location, 0) + 1

        for role, keywords in role_keywords.items():
            if any(kw in title_lower for kw in keywords):
                role_counts[role]["total"] += 1
                if (job.published_at or job.created_at) and (job.published_at or job.created_at) >= cutoff_30:
                    role_counts[role]["recent_30d"] += 1

    # Sort roles by total
    role_trends = [
        {"role": role, "total_90d": data["total"], "total_30d": data["recent_30d"]}
        for role, data in sorted(role_counts.items(), key=lambda x: x[1]["total"], reverse=True)
        if data["total"] > 0
    ]

    # Top locations
    geo_breakdown = [
        {"location": loc, "count": cnt}
        for loc, cnt in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    ]

    return {
        "total_listings_90d": len(jobs),
        "role_trends": role_trends,
        "geo_breakdown": geo_breakdown,
    }
