"""Source data routes — direct access to third-party scraped data."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    GithubRepoResponse, HFModelResponse, PackageDownloadResponse,
    YCCompanyResponse, SOQuestionResponse, PHLaunchResponse,
    PaginatedResponse,
)
from database.connection import (
    GithubRepo, HFModel, PackageDownload, YCCompany, SOQuestion, PHLaunch,
)
from scrapers.base_scraper import _utc_naive

router = APIRouter()


# ── GitHub Trending ───────────────────────────────────────────────

@router.get("/github-trending", response_model=PaginatedResponse[GithubRepoResponse])
async def github_trending(
    language: str | None = None,
    min_stars: int | None = None,
    sort_by: str = Query("stars", pattern="^(stars|star_velocity|forks|pushed_at)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """GitHub repos sorted by stars or star velocity."""
    stmt = select(GithubRepo)
    count_stmt = select(func.count(GithubRepo.id))

    if language:
        stmt = stmt.where(GithubRepo.language.ilike(language))
        count_stmt = count_stmt.where(GithubRepo.language.ilike(language))
    if min_stars is not None:
        stmt = stmt.where(GithubRepo.stars >= min_stars)
        count_stmt = count_stmt.where(GithubRepo.stars >= min_stars)

    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "stars": GithubRepo.stars.desc().nullslast(),
        "star_velocity": GithubRepo.star_velocity.desc().nullslast(),
        "forks": GithubRepo.forks.desc().nullslast(),
        "pushed_at": GithubRepo.pushed_at.desc().nullslast(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, GithubRepo.stars.desc().nullslast()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        GithubRepoResponse(
            id=r.id, repo_full_name=r.repo_full_name, name=r.name,
            description=r.description, stars=r.stars, forks=r.forks,
            language=r.language, topics=r.topics,
            star_velocity=r.star_velocity,
            contributor_count=r.contributor_count,
            license=r.license, pushed_at=r.pushed_at,
            last_scraped_at=r.last_scraped_at,
        )
        for r in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Hugging Face Trending ─────────────────────────────────────────

@router.get("/hf-trending", response_model=PaginatedResponse[HFModelResponse])
async def hf_trending(
    pipeline_tag: str | None = None,
    library: str | None = None,
    sort_by: str = Query("trending_score", pattern="^(trending_score|downloads|likes|downloads_last_week)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Hugging Face models sorted by trending score or downloads."""
    stmt = select(HFModel)
    count_stmt = select(func.count(HFModel.id))

    if pipeline_tag:
        stmt = stmt.where(HFModel.pipeline_tag == pipeline_tag)
        count_stmt = count_stmt.where(HFModel.pipeline_tag == pipeline_tag)
    if library:
        stmt = stmt.where(HFModel.library_name.ilike(f"%{library}%"))
        count_stmt = count_stmt.where(HFModel.library_name.ilike(f"%{library}%"))

    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "trending_score": HFModel.trending_score.desc().nullslast(),
        "downloads": HFModel.downloads.desc().nullslast(),
        "likes": HFModel.likes.desc().nullslast(),
        "downloads_last_week": HFModel.downloads_last_week.desc().nullslast(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, HFModel.trending_score.desc().nullslast()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        HFModelResponse(
            id=m.id, model_id=m.model_id, pipeline_tag=m.pipeline_tag,
            downloads=m.downloads, likes=m.likes, tags=m.tags,
            library_name=m.library_name,
            downloads_last_week=m.downloads_last_week,
            trending_score=m.trending_score, last_modified=m.last_modified,
        )
        for m in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Package Download Trends ───────────────────────────────────────

@router.get("/package-trends", response_model=list[PackageDownloadResponse])
async def package_trends(
    registry: str | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Package download trends aggregated by package name."""
    now = _utc_naive()
    cutoff_30 = (now - timedelta(days=30)).date()
    cutoff_7 = (now - timedelta(days=7)).date()

    # Get distinct packages
    pkg_stmt = select(
        PackageDownload.package_name,
        PackageDownload.registry,
    ).group_by(PackageDownload.package_name, PackageDownload.registry)

    if registry:
        pkg_stmt = pkg_stmt.where(PackageDownload.registry == registry)
    if search:
        pkg_stmt = pkg_stmt.where(PackageDownload.package_name.ilike(f"%{search}%"))

    pkg_stmt = pkg_stmt.limit(limit)
    packages = (await db.execute(pkg_stmt)).all()

    items = []
    for pkg_name, reg in packages:
        # 30-day total
        total_30d = (await db.execute(
            select(func.sum(PackageDownload.downloads))
            .where(
                PackageDownload.package_name == pkg_name,
                PackageDownload.registry == reg,
                PackageDownload.date >= cutoff_30,
            )
        )).scalar() or 0

        # Latest daily value
        latest = (await db.execute(
            select(PackageDownload.downloads)
            .where(PackageDownload.package_name == pkg_name, PackageDownload.registry == reg)
            .order_by(PackageDownload.date.desc())
            .limit(1)
        )).scalar() or 0

        # Trend: compare last 7d vs previous 7d
        recent_sum = (await db.execute(
            select(func.sum(PackageDownload.downloads))
            .where(
                PackageDownload.package_name == pkg_name,
                PackageDownload.registry == reg,
                PackageDownload.date >= cutoff_7,
            )
        )).scalar() or 0

        cutoff_14 = (now - timedelta(days=14)).date()
        older_sum = (await db.execute(
            select(func.sum(PackageDownload.downloads))
            .where(
                PackageDownload.package_name == pkg_name,
                PackageDownload.registry == reg,
                PackageDownload.date >= cutoff_14,
                PackageDownload.date < cutoff_7,
            )
        )).scalar() or 0

        if older_sum == 0:
            trend = "up" if recent_sum > 0 else "stable"
        elif recent_sum > older_sum * 1.1:
            trend = "up"
        elif recent_sum < older_sum * 0.9:
            trend = "down"
        else:
            trend = "stable"

        items.append(PackageDownloadResponse(
            package_name=pkg_name,
            registry=reg,
            total_downloads_30d=total_30d,
            latest_daily=latest,
            trend=trend,
        ))

    # Sort by 30d downloads descending
    items.sort(key=lambda x: x.total_downloads_30d, reverse=True)
    return items


# ── YC Batches ────────────────────────────────────────────────────

@router.get("/yc-batches", response_model=PaginatedResponse[YCCompanyResponse])
async def yc_batches(
    batch: str | None = None,
    industry: str | None = None,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """YC companies by batch, industry, or status."""
    stmt = select(YCCompany)
    count_stmt = select(func.count(YCCompany.id))

    if batch:
        stmt = stmt.where(YCCompany.batch == batch)
        count_stmt = count_stmt.where(YCCompany.batch == batch)
    if status:
        stmt = stmt.where(YCCompany.status == status)
        count_stmt = count_stmt.where(YCCompany.status == status)
    if search:
        stmt = stmt.where(YCCompany.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(YCCompany.name.ilike(f"%{search}%"))
    if industry:
        # JSONB array contains
        stmt = stmt.where(YCCompany.industries.op("@>")(f'["{industry}"]'))
        count_stmt = count_stmt.where(YCCompany.industries.op("@>")(f'["{industry}"]'))

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(YCCompany.batch.desc().nullslast(), YCCompany.name.asc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        YCCompanyResponse(
            id=c.id, slug=c.slug, name=c.name, description=c.description,
            batch=c.batch, status=c.status, industries=c.industries,
            regions=c.regions, team_size=c.team_size, website=c.website,
        )
        for c in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Stack Overflow Trends ─────────────────────────────────────────

@router.get("/so-trends", response_model=PaginatedResponse[SOQuestionResponse])
async def so_trends(
    tag: str | None = None,
    is_answered: bool | None = None,
    sort_by: str = Query("creation_date", pattern="^(creation_date|view_count|score|answer_count)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Stack Overflow questions sorted by recency, views, or score."""
    stmt = select(SOQuestion)
    count_stmt = select(func.count(SOQuestion.id))

    if tag:
        stmt = stmt.where(SOQuestion.tags.op("@>")(f'["{tag}"]'))
        count_stmt = count_stmt.where(SOQuestion.tags.op("@>")(f'["{tag}"]'))
    if is_answered is not None:
        stmt = stmt.where(SOQuestion.is_answered == is_answered)
        count_stmt = count_stmt.where(SOQuestion.is_answered == is_answered)

    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "creation_date": SOQuestion.creation_date.desc().nullslast(),
        "view_count": SOQuestion.view_count.desc().nullslast(),
        "score": SOQuestion.score.desc().nullslast(),
        "answer_count": SOQuestion.answer_count.desc().nullslast(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, SOQuestion.creation_date.desc().nullslast()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        SOQuestionResponse(
            id=q.id, so_question_id=q.so_question_id, title=q.title,
            tags=q.tags, view_count=q.view_count, answer_count=q.answer_count,
            score=q.score, is_answered=q.is_answered, link=q.link,
            creation_date=q.creation_date,
        )
        for q in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Product Hunt Recent ───────────────────────────────────────────

@router.get("/ph-recent", response_model=PaginatedResponse[PHLaunchResponse])
async def ph_recent(
    search: str | None = None,
    min_votes: int | None = None,
    sort_by: str = Query("launched_at", pattern="^(launched_at|votes_count|comments_count)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Recent Product Hunt launches."""
    stmt = select(PHLaunch)
    count_stmt = select(func.count(PHLaunch.id))

    if search:
        stmt = stmt.where(PHLaunch.name.ilike(f"%{search}%"))
        count_stmt = count_stmt.where(PHLaunch.name.ilike(f"%{search}%"))
    if min_votes is not None:
        stmt = stmt.where(PHLaunch.votes_count >= min_votes)
        count_stmt = count_stmt.where(PHLaunch.votes_count >= min_votes)

    total = (await db.execute(count_stmt)).scalar()

    sort_map = {
        "launched_at": PHLaunch.launched_at.desc().nullslast(),
        "votes_count": PHLaunch.votes_count.desc().nullslast(),
        "comments_count": PHLaunch.comments_count.desc().nullslast(),
    }
    stmt = stmt.order_by(sort_map.get(sort_by, PHLaunch.launched_at.desc().nullslast()))
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        PHLaunchResponse(
            id=p.id, ph_id=p.ph_id, name=p.name, tagline=p.tagline,
            description=p.description, votes_count=p.votes_count,
            comments_count=p.comments_count, website=p.website,
            topics=p.topics, launched_at=p.launched_at,
        )
        for p in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)
