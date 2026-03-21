"""Agent management routes — monitoring, triggering, and cost tracking."""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    AgentRunResponse, AgentRunDetailResponse,
    AgentStatusResponse, AgentCostResponse,
)
from database.connection import AgentRun
from agents.config import AGENT_MODELS, AGENT_SCHEDULES

router = APIRouter()

# Valid agent names for triggering
VALID_AGENTS = list(AGENT_MODELS.keys())


# ── Agent Status Overview ─────────────────────────────────────────

@router.get("/status", response_model=list[AgentStatusResponse])
async def agent_status_all(db: AsyncSession = Depends(get_db)):
    """Status overview of all agents: last run, success rate, schedule."""
    items = []
    for agent_name in VALID_AGENTS:
        # Last run
        last_result = await db.execute(
            select(AgentRun)
            .where(AgentRun.agent_name == agent_name)
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        )
        last_run_obj = last_result.scalar_one_or_none()

        # Total runs and success count
        stats = await db.execute(
            select(
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "success").label("successes"),
            ).where(AgentRun.agent_name == agent_name)
        )
        row = stats.one()
        total_runs = row.total or 0
        successes = row.successes or 0
        success_rate = round(successes / total_runs, 4) if total_runs > 0 else None

        last_run = None
        if last_run_obj:
            last_run = AgentRunResponse(
                id=last_run_obj.id, agent_name=last_run_obj.agent_name,
                status=last_run_obj.status, duration_seconds=last_run_obj.duration_seconds,
                tokens_used=last_run_obj.tokens_used, cost_usd=last_run_obj.cost_usd,
                records_produced=last_run_obj.records_produced,
                started_at=last_run_obj.started_at, completed_at=last_run_obj.completed_at,
            )

        schedule = AGENT_SCHEDULES.get(agent_name, {})
        items.append(AgentStatusResponse(
            agent_name=agent_name,
            model=AGENT_MODELS.get(agent_name),
            schedule_hours=schedule.get("interval_hours"),
            last_run=last_run,
            total_runs=total_runs,
            success_rate=success_rate,
        ))

    return items


# ── Agent Run History ─────────────────────────────────────────────

@router.get("/runs", response_model=list[AgentRunResponse])
async def agent_runs(
    agent_name: str | None = None,
    status: str | None = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Recent agent runs, optionally filtered by agent name or status."""
    stmt = select(AgentRun).order_by(AgentRun.started_at.desc()).limit(limit)
    if agent_name:
        stmt = stmt.where(AgentRun.agent_name == agent_name)
    if status:
        stmt = stmt.where(AgentRun.status == status)

    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [
        AgentRunResponse(
            id=r.id, agent_name=r.agent_name, status=r.status,
            duration_seconds=r.duration_seconds, tokens_used=r.tokens_used,
            cost_usd=r.cost_usd, records_produced=r.records_produced,
            started_at=r.started_at, completed_at=r.completed_at,
        )
        for r in runs
    ]


# ── Single Run Detail ─────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=AgentRunDetailResponse)
async def agent_run_detail(
    run_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Full detail of a single agent run including output."""
    run = await db.get(AgentRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")

    return AgentRunDetailResponse(
        id=run.id, agent_name=run.agent_name, status=run.status,
        duration_seconds=run.duration_seconds, tokens_used=run.tokens_used,
        cost_usd=run.cost_usd, records_produced=run.records_produced,
        started_at=run.started_at, completed_at=run.completed_at,
        output=run.output[:10000] if run.output else None,
        output_json=run.output_json,
        error_message=run.error_message,
    )


# ── Trigger Single Agent ──────────────────────────────────────────

@router.post("/trigger/{agent_name}")
async def trigger_agent(
    agent_name: str,
    background_tasks: BackgroundTasks,
):
    """Trigger a single agent to run in the background."""
    if agent_name not in VALID_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent: {agent_name}. Available: {VALID_AGENTS}",
        )

    background_tasks.add_task(_run_agent_background, agent_name)
    return {"status": "triggered", "agent": agent_name}


# ── Trigger All Agents ────────────────────────────────────────────

@router.post("/trigger-all")
async def trigger_all_agents(background_tasks: BackgroundTasks):
    """Trigger full orchestrator pipeline in the background."""
    background_tasks.add_task(_run_all_agents_background)
    return {"status": "triggered", "agents": "all"}


# ── Cost Tracking ─────────────────────────────────────────────────

@router.get("/costs", response_model=list[AgentCostResponse])
async def agent_costs(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate cost and token usage per agent over the last N days."""
    from datetime import timedelta
    from scrapers.base_scraper import _utc_naive

    cutoff = _utc_naive() - timedelta(days=days)

    result = await db.execute(
        select(
            AgentRun.agent_name,
            func.count(AgentRun.id).label("total_runs"),
            func.sum(AgentRun.tokens_used).label("total_tokens"),
            func.sum(AgentRun.cost_usd).label("total_cost"),
            func.avg(AgentRun.duration_seconds).label("avg_duration"),
        )
        .where(AgentRun.started_at >= cutoff)
        .group_by(AgentRun.agent_name)
        .order_by(func.sum(AgentRun.cost_usd).desc().nullslast())
    )
    rows = result.all()

    return [
        AgentCostResponse(
            agent_name=name,
            total_runs=total,
            total_tokens=tokens,
            total_cost_usd=round(float(cost), 4) if cost else None,
            avg_duration_seconds=round(float(avg_dur), 2) if avg_dur else None,
        )
        for name, total, tokens, cost, avg_dur in rows
    ]


# ── Background task helpers ───────────────────────────────────────

async def _run_agent_background(agent_name: str):
    """Run a single agent via the orchestrator."""
    from agents.orchestrator import CrossSourceOrchestrator
    orchestrator = CrossSourceOrchestrator()
    await orchestrator.run_single(agent_name)


async def _run_all_agents_background():
    """Run full orchestrator pipeline."""
    from agents.orchestrator import CrossSourceOrchestrator
    orchestrator = CrossSourceOrchestrator()
    await orchestrator.run_all_signals()
