"""API routes for custom market research projects."""

import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select, func, delete

from api.models.schemas import (
    PaginatedResponse,
    ResearchProjectCreate,
    ResearchProjectResponse,
    ResearchInsightsResponse,
    ResearchContactResponse,
    PostResponse,
)
from database.connection import (
    async_session, ResearchProject, ResearchInsight, ResearchContact, Post,
)

router = APIRouter()


@router.post("/", response_model=ResearchProjectResponse)
async def create_project(body: ResearchProjectCreate):
    """Create a new research project."""
    async with async_session() as session:
        project = ResearchProject(
            name=body.name,
            description=body.description,
            initial_terms=body.initial_terms,
            status="draft",
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        return ResearchProjectResponse.model_validate(project)


@router.get("/", response_model=PaginatedResponse[ResearchProjectResponse])
async def list_projects(
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List research projects with optional status filter."""
    async with async_session() as session:
        base = select(ResearchProject)
        count_q = select(func.count(ResearchProject.id))

        if status:
            base = base.where(ResearchProject.status == status)
            count_q = count_q.where(ResearchProject.status == status)

        total = (await session.execute(count_q)).scalar() or 0

        rows = (await session.execute(
            base.order_by(ResearchProject.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )).scalars().all()

        items = [ResearchProjectResponse.model_validate(r) for r in rows]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{project_id}", response_model=ResearchProjectResponse)
async def get_project(project_id: int):
    """Get a single research project."""
    async with async_session() as session:
        project = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ResearchProjectResponse.model_validate(project)


@router.post("/{project_id}/run")
async def run_research(project_id: int, background_tasks: BackgroundTasks):
    """Trigger the research pipeline (keyword expansion → scraping → analysis)."""
    async with async_session() as session:
        project = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.status in ("expanding", "scraping", "processing"):
            raise HTTPException(status_code=409, detail="Research already in progress")

    # Run in background
    background_tasks.add_task(_run_pipeline, project_id)

    return {"status": "started", "project_id": project_id}


async def _run_pipeline(project_id: int):
    """Background task that runs the full research pipeline."""
    from processors.research_processor import ResearchProcessor

    processor = ResearchProcessor()
    await processor.run(project_id)


@router.get("/{project_id}/insights", response_model=ResearchInsightsResponse)
async def get_insights(project_id: int):
    """Get research insights for a project."""
    async with async_session() as session:
        insight = (await session.execute(
            select(ResearchInsight).where(ResearchInsight.project_id == project_id)
        )).scalar_one_or_none()

        if not insight:
            raise HTTPException(status_code=404, detail="Insights not ready yet")

        return ResearchInsightsResponse.model_validate(insight)


@router.get("/{project_id}/contacts", response_model=PaginatedResponse[ResearchContactResponse])
async def list_contacts(
    project_id: int,
    sentiment: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List contacts for a research project."""
    async with async_session() as session:
        base = select(ResearchContact).where(ResearchContact.project_id == project_id)
        count_q = select(func.count(ResearchContact.id)).where(
            ResearchContact.project_id == project_id
        )

        if sentiment:
            base = base.where(ResearchContact.sentiment_leaning == sentiment)
            count_q = count_q.where(ResearchContact.sentiment_leaning == sentiment)

        total = (await session.execute(count_q)).scalar() or 0

        rows = (await session.execute(
            base.order_by(ResearchContact.post_count.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )).scalars().all()

        items = [ResearchContactResponse.model_validate(r) for r in rows]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/{project_id}/posts", response_model=PaginatedResponse[PostResponse])
async def list_project_posts(
    project_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """List posts collected for a research project."""
    async with async_session() as session:
        condition = (
            Post.raw_metadata["source"].astext == "custom_research"
        ) & (
            Post.raw_metadata["project_id"].astext == str(project_id)
        )

        count_q = select(func.count(Post.id)).where(condition)
        total = (await session.execute(count_q)).scalar() or 0

        rows = (await session.execute(
            select(Post)
            .where(condition)
            .order_by(Post.score.desc().nullslast())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )).scalars().all()

        items = [PostResponse.model_validate(r) for r in rows]

    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.delete("/{project_id}")
async def delete_project(project_id: int):
    """Delete a research project and all related data."""
    async with async_session() as session:
        project = (await session.execute(
            select(ResearchProject).where(ResearchProject.id == project_id)
        )).scalar_one_or_none()

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if project.status in ("expanding", "scraping", "processing"):
            raise HTTPException(status_code=409, detail="Cannot delete while research is running")

        # Delete related data
        await session.execute(
            delete(ResearchContact).where(ResearchContact.project_id == project_id)
        )
        await session.execute(
            delete(ResearchInsight).where(ResearchInsight.project_id == project_id)
        )
        await session.execute(
            delete(ResearchProject).where(ResearchProject.id == project_id)
        )
        await session.commit()

    return {"status": "deleted", "project_id": project_id}
