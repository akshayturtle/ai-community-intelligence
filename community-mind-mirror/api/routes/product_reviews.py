"""API routes for product review intelligence."""

from fastapi import APIRouter, Query
from sqlalchemy import select, func, text

from api.models.schemas import PaginatedResponse, ProductReviewResponse
from database.connection import async_session, ProductReview, DiscoveredProduct

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ProductReviewResponse])
async def list_product_reviews(
    category: str | None = None,
    sentiment: str | None = None,
    sort_by: str = Query("satisfaction_score", pattern="^(satisfaction_score|post_count|product_name)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List all product reviews with pagination and filtering."""
    async with async_session() as session:
        base = select(ProductReview)

        if sentiment:
            base = base.where(ProductReview.overall_sentiment == sentiment)

        if category:
            base = base.join(DiscoveredProduct, DiscoveredProduct.id == ProductReview.product_id).where(
                DiscoveredProduct.category == category
            )

        # Count
        count_q = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_q)).scalar() or 0

        # Sort
        if sort_by == "satisfaction_score":
            base = base.order_by(ProductReview.satisfaction_score.desc().nullslast())
        elif sort_by == "post_count":
            base = base.order_by(ProductReview.post_count.desc().nullslast())
        else:
            base = base.order_by(ProductReview.product_name)

        # Paginate
        rows = (await session.execute(
            base.offset((page - 1) * per_page).limit(per_page)
        )).scalars().all()

        items = [ProductReviewResponse.model_validate(r) for r in rows]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/summary")
async def product_review_summary():
    """Aggregate review stats."""
    async with async_session() as session:
        total = (await session.execute(select(func.count(ProductReview.id)))).scalar() or 0

        # Sentiment distribution
        sentiment_dist = {}
        result = await session.execute(
            select(ProductReview.overall_sentiment, func.count(ProductReview.id))
            .group_by(ProductReview.overall_sentiment)
        )
        for sentiment, count in result.all():
            sentiment_dist[sentiment or "unknown"] = count

        # Average satisfaction
        avg_satisfaction = (await session.execute(
            select(func.avg(ProductReview.satisfaction_score))
        )).scalar()

        # Top rated (top 5)
        top_rated = (await session.execute(
            select(ProductReview.product_name, ProductReview.satisfaction_score)
            .where(ProductReview.satisfaction_score.isnot(None))
            .order_by(ProductReview.satisfaction_score.desc())
            .limit(5)
        )).all()

        # Most common feature requests (aggregate from JSONB)
        feature_requests = (await session.execute(text("""
            SELECT req, COUNT(*) as cnt
            FROM product_reviews, jsonb_array_elements_text(feature_requests) AS req
            GROUP BY req ORDER BY cnt DESC LIMIT 10
        """))).all()

        # Common churn reasons
        churn_reasons = (await session.execute(text("""
            SELECT reason, COUNT(*) as cnt
            FROM product_reviews, jsonb_array_elements_text(churn_reasons) AS reason
            GROUP BY reason ORDER BY cnt DESC LIMIT 10
        """))).all()

    return {
        "total_reviews": total,
        "sentiment_distribution": sentiment_dist,
        "avg_satisfaction": round(avg_satisfaction, 1) if avg_satisfaction else None,
        "top_rated": [{"product": r.product_name, "score": r.satisfaction_score} for r in top_rated],
        "top_feature_requests": [{"request": r[0], "count": r[1]} for r in feature_requests],
        "top_churn_reasons": [{"reason": r[0], "count": r[1]} for r in churn_reasons],
    }


@router.get("/{product_id}", response_model=ProductReviewResponse)
async def get_product_review(product_id: int):
    """Get review for a specific product."""
    async with async_session() as session:
        result = await session.execute(
            select(ProductReview).where(ProductReview.product_id == product_id)
        )
        review = result.scalar_one_or_none()
        if not review:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Review not found")
        return ProductReviewResponse.model_validate(review)
