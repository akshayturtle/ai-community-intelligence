"""Signal routes — cross-source intelligence from Agno agents."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models.schemas import (
    ResearchPipelineResponse, TractionScoreResponse, TechnologyLifecycleResponse,
    MarketGapResponse, CompetitiveThreatResponse, PlatformDivergenceResponse,
    NarrativeShiftResponse, SmartMoneyResponse, TalentFlowResponse,
    InsightCardResponse, SignalSummaryResponse, PaginatedResponse,
)
from database.connection import (
    ResearchPipeline, TractionScore, TechnologyLifecycle,
    MarketGap, CompetitiveThreat, PlatformDivergence,
    NarrativeShift, SmartMoney, TalentFlow, AgentRun,
)

router = APIRouter()


# ── Research Pipeline ─────────────────────────────────────────────

@router.get("/research-pipeline", response_model=PaginatedResponse[ResearchPipelineResponse])
async def list_research_pipeline(
    stage: str | None = None,
    velocity: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Research-to-product pipeline tracking: ArXiv → GitHub → HF → Community → PH."""
    stmt = select(ResearchPipeline)
    count_stmt = select(func.count(ResearchPipeline.id))

    if stage:
        stmt = stmt.where(ResearchPipeline.current_stage == stage)
        count_stmt = count_stmt.where(ResearchPipeline.current_stage == stage)
    if velocity:
        stmt = stmt.where(ResearchPipeline.pipeline_velocity == velocity)
        count_stmt = count_stmt.where(ResearchPipeline.pipeline_velocity == velocity)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(ResearchPipeline.updated_at.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        ResearchPipelineResponse(
            id=r.id, paper_title=r.paper_title, arxiv_id=r.arxiv_id,
            published_at=r.published_at, current_stage=r.current_stage,
            pipeline_velocity=r.pipeline_velocity, github_repos=r.github_repos,
            hf_model_ids=r.hf_model_ids, hf_total_downloads=r.hf_total_downloads,
            community_mention_count=r.community_mention_count,
            community_sentiment=r.community_sentiment, ph_launches=r.ph_launches,
            so_question_count=r.so_question_count,
            days_paper_to_code=r.days_paper_to_code,
            days_code_to_adoption=r.days_code_to_adoption,
            days_total_pipeline=r.days_total_pipeline, updated_at=r.updated_at,
        )
        for r in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Traction Scores ───────────────────────────────────────────────

@router.get("/traction-scores", response_model=PaginatedResponse[TractionScoreResponse])
async def list_traction_scores(
    label: str | None = None,
    entity_type: str | None = None,
    min_score: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Anti-hype traction scoring using unfakeable signals."""
    stmt = select(TractionScore)
    count_stmt = select(func.count(TractionScore.id))

    if label:
        stmt = stmt.where(TractionScore.traction_label == label)
        count_stmt = count_stmt.where(TractionScore.traction_label == label)
    if entity_type:
        stmt = stmt.where(TractionScore.entity_type == entity_type)
        count_stmt = count_stmt.where(TractionScore.entity_type == entity_type)
    if min_score is not None:
        stmt = stmt.where(TractionScore.traction_score >= min_score)
        count_stmt = count_stmt.where(TractionScore.traction_score >= min_score)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(TractionScore.traction_score.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        TractionScoreResponse(
            id=t.id, entity_name=t.entity_name, entity_type=t.entity_type,
            traction_score=t.traction_score, traction_label=t.traction_label,
            ph_votes=t.ph_votes, gh_stars=t.gh_stars,
            gh_star_velocity=t.gh_star_velocity,
            gh_non_founder_contributors=t.gh_non_founder_contributors,
            pypi_monthly_downloads=t.pypi_monthly_downloads,
            npm_monthly_downloads=t.npm_monthly_downloads,
            organic_mentions=t.organic_mentions,
            self_promo_mentions=t.self_promo_mentions,
            job_listings=t.job_listings, recommendation_rate=t.recommendation_rate,
            score_breakdown=t.score_breakdown, red_flags=t.red_flags,
            reasoning=t.reasoning, calculated_at=t.calculated_at,
        )
        for t in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Technology Lifecycle ──────────────────────────────────────────

@router.get("/technology-lifecycle", response_model=PaginatedResponse[TechnologyLifecycleResponse])
async def list_technology_lifecycle(
    stage: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Technology adoption stage mapping: research → experimentation → growth → mature → declining."""
    stmt = select(TechnologyLifecycle)
    count_stmt = select(func.count(TechnologyLifecycle.id))

    if stage:
        stmt = stmt.where(TechnologyLifecycle.current_stage == stage)
        count_stmt = count_stmt.where(TechnologyLifecycle.current_stage == stage)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(TechnologyLifecycle.calculated_at.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        TechnologyLifecycleResponse(
            id=t.id, technology_name=t.technology_name,
            current_stage=t.current_stage, stage_evidence=t.stage_evidence,
            arxiv_paper_count=t.arxiv_paper_count,
            github_repo_count=t.github_repo_count,
            hf_model_count=t.hf_model_count,
            so_question_count=t.so_question_count,
            job_listing_count=t.job_listing_count,
            community_mention_count=t.community_mention_count,
            community_sentiment_trajectory=t.community_sentiment_trajectory,
            calculated_at=t.calculated_at,
        )
        for t in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Market Gaps ───────────────────────────────────────────────────

@router.get("/market-gaps", response_model=PaginatedResponse[MarketGapResponse])
async def list_market_gaps(
    signal: str | None = None,
    min_opportunity: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Market gap / startup opportunity identification."""
    stmt = select(MarketGap)
    count_stmt = select(func.count(MarketGap.id))

    if signal:
        stmt = stmt.where(MarketGap.gap_signal == signal)
        count_stmt = count_stmt.where(MarketGap.gap_signal == signal)
    if min_opportunity is not None:
        stmt = stmt.where(MarketGap.opportunity_score >= min_opportunity)
        count_stmt = count_stmt.where(MarketGap.opportunity_score >= min_opportunity)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(MarketGap.opportunity_score.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        MarketGapResponse(
            id=g.id, problem_title=g.problem_title, pain_score=g.pain_score,
            complaint_count=g.complaint_count, existing_products=g.existing_products,
            existing_product_names=g.existing_product_names,
            total_funding_in_space=g.total_funding_in_space,
            funded_startups=g.funded_startups,
            job_postings_related=g.job_postings_related,
            yc_batch_presence=g.yc_batch_presence, gap_signal=g.gap_signal,
            opportunity_score=g.opportunity_score, reasoning=g.reasoning,
            calculated_at=g.calculated_at,
        )
        for g in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Competitive Threats ───────────────────────────────────────────

@router.get("/competitive-threats", response_model=PaginatedResponse[CompetitiveThreatResponse])
async def list_competitive_threats(
    target: str | None = None,
    min_threat: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Per-product competitive threat scoring."""
    stmt = select(CompetitiveThreat)
    count_stmt = select(func.count(CompetitiveThreat.id))

    if target:
        stmt = stmt.where(CompetitiveThreat.target_product.ilike(f"%{target}%"))
        count_stmt = count_stmt.where(CompetitiveThreat.target_product.ilike(f"%{target}%"))
    if min_threat is not None:
        stmt = stmt.where(CompetitiveThreat.threat_score >= min_threat)
        count_stmt = count_stmt.where(CompetitiveThreat.threat_score >= min_threat)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(CompetitiveThreat.threat_score.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        CompetitiveThreatResponse(
            id=c.id, target_product=c.target_product, competitor=c.competitor,
            migrations_away=c.migrations_away,
            competitor_gh_velocity=c.competitor_gh_velocity,
            competitor_hiring=c.competitor_hiring,
            competitor_sentiment=c.competitor_sentiment,
            competitor_sentiment_trend=c.competitor_sentiment_trend,
            opinion_leaders_flipped=c.opinion_leaders_flipped,
            threat_score=c.threat_score, threat_summary=c.threat_summary,
            calculated_at=c.calculated_at,
        )
        for c in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Platform Divergence ───────────────────────────────────────────

@router.get("/platform-divergence", response_model=PaginatedResponse[PlatformDivergenceResponse])
async def list_platform_divergence(
    status: str | None = None,
    min_divergence: float | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Cross-platform sentiment disagreements."""
    stmt = select(PlatformDivergence)
    count_stmt = select(func.count(PlatformDivergence.id))

    if status:
        stmt = stmt.where(PlatformDivergence.status == status)
        count_stmt = count_stmt.where(PlatformDivergence.status == status)
    if min_divergence is not None:
        stmt = stmt.where(PlatformDivergence.max_divergence >= min_divergence)
        count_stmt = count_stmt.where(PlatformDivergence.max_divergence >= min_divergence)

    total = (await db.execute(count_stmt)).scalar()
    stmt = stmt.order_by(PlatformDivergence.max_divergence.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    items = [
        PlatformDivergenceResponse(
            id=d.id, topic_name=d.topic_name,
            reddit_sentiment=d.reddit_sentiment, hn_sentiment=d.hn_sentiment,
            youtube_sentiment=d.youtube_sentiment, ph_sentiment=d.ph_sentiment,
            max_divergence=d.max_divergence,
            divergence_direction=d.divergence_direction,
            prediction=d.prediction, status=d.status,
            calculated_at=d.calculated_at,
        )
        for d in result.scalars().all()
    ]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Narrative Shifts ──────────────────────────────────────────────

@router.get("/narrative-shifts", response_model=PaginatedResponse[NarrativeShiftResponse])
async def list_narrative_shifts(
    shift_type: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Narrative shift analysis: how community framing of topics evolves over time."""
    stmt = select(NarrativeShift)
    count_stmt = select(func.count(NarrativeShift.id))

    if shift_type:
        stmt = stmt.where(NarrativeShift.shift_type == shift_type)
        count_stmt = count_stmt.where(NarrativeShift.shift_type == shift_type)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(NarrativeShift.calculated_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    )
    items = [NarrativeShiftResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Smart Money ──────────────────────────────────────────────────

@router.get("/smart-money", response_model=PaginatedResponse[SmartMoneyResponse])
async def list_smart_money(
    classification: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Smart money tracker: YC vs VC capital flow analysis per sector."""
    stmt = select(SmartMoney)
    count_stmt = select(func.count(SmartMoney.id))

    if classification:
        stmt = stmt.where(SmartMoney.classification == classification)
        count_stmt = count_stmt.where(SmartMoney.classification == classification)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(SmartMoney.calculated_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    )
    items = [SmartMoneyResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


# ── Talent Flow ──────────────────────────────────────────────────

@router.get("/talent-flow", response_model=PaginatedResponse[TalentFlowResponse])
async def list_talent_flow(
    category: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Talent flow analysis: supply-demand skill gap prediction."""
    stmt = select(TalentFlow)
    count_stmt = select(func.count(TalentFlow.id))

    if category:
        stmt = stmt.where(TalentFlow.category == category)
        count_stmt = count_stmt.where(TalentFlow.category == category)

    total = (await db.execute(count_stmt)).scalar() or 0
    result = await db.execute(
        stmt.order_by(TalentFlow.calculated_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    )
    items = [TalentFlowResponse.model_validate(r) for r in result.scalars().all()]
    return PaginatedResponse(total=total, page=page, per_page=per_page, items=items)


@router.get("/summary", response_model=SignalSummaryResponse)
async def signal_summary(db: AsyncSession = Depends(get_db)):
    """Aggregated cross-signal summary for the overview tab."""
    # Counts per signal type
    counts = {}
    for name, model in [
        ("research_pipeline", ResearchPipeline), ("traction_scores", TractionScore),
        ("technology_lifecycle", TechnologyLifecycle), ("market_gaps", MarketGap),
        ("competitive_threats", CompetitiveThreat), ("platform_divergence", PlatformDivergence),
        ("narrative_shifts", NarrativeShift), ("smart_money", SmartMoney),
        ("talent_flow", TalentFlow),
    ]:
        r = await db.execute(select(func.count(model.id)))
        counts[name] = r.scalar() or 0

    # Top 3 market gaps by opportunity_score
    r = await db.execute(
        select(MarketGap).order_by(MarketGap.opportunity_score.desc().nulls_last()).limit(3)
    )
    top_opportunities = [
        {"problem_title": g.problem_title, "opportunity_score": g.opportunity_score,
         "gap_signal": g.gap_signal, "complaint_count": g.complaint_count}
        for g in r.scalars().all()
    ]

    # Top 3 competitive threats
    r = await db.execute(
        select(CompetitiveThreat).order_by(CompetitiveThreat.threat_score.desc().nulls_last()).limit(3)
    )
    top_threats = [
        {"target_product": t.target_product, "competitor": t.competitor,
         "threat_score": t.threat_score, "migrations_away": t.migrations_away}
        for t in r.scalars().all()
    ]

    # Top 3 talent gaps
    r = await db.execute(
        select(TalentFlow).order_by(TalentFlow.gap.desc().nulls_last()).limit(3)
    )
    top_skill_gaps = [
        {"skill": t.skill, "gap": t.gap, "salary_pressure": t.salary_pressure,
         "trend": t.trend, "demand_score": t.demand_score, "supply_score": t.supply_score}
        for t in r.scalars().all()
    ]

    # Smart money early sectors
    r = await db.execute(
        select(SmartMoney).where(SmartMoney.classification == "smart_money_early")
    )
    smart_money_early = [
        {"sector": s.sector, "yc_companies_last_batch": s.yc_companies_last_batch,
         "yc_trend": s.yc_trend, "vc_signal": s.vc_signal, "builder_repos": s.builder_repos}
        for s in r.scalars().all()
    ]

    # High-confidence narrative shifts
    r = await db.execute(
        select(NarrativeShift).where(NarrativeShift.confidence == "high")
        .order_by(NarrativeShift.calculated_at.desc().nulls_last()).limit(3)
    )
    shifts = [
        {"topic_name": n.topic_name, "shift_type": n.shift_type,
         "shift_velocity": n.shift_velocity, "older_frame": n.older_frame,
         "recent_frame": n.recent_frame}
        for n in r.scalars().all()
    ]

    # Get latest insights
    insights_resp = await latest_insights(limit=5, db=db)

    return SignalSummaryResponse(
        total_signals=counts,
        top_opportunities=top_opportunities,
        top_threats=top_threats,
        top_skill_gaps=top_skill_gaps,
        smart_money_early=smart_money_early,
        narrative_shifts=shifts,
        insights=insights_resp,
    )


@router.get("/product-discoveries")
async def latest_product_discoveries(db: AsyncSession = Depends(get_db)):
    """Latest product discoverer results (auto-discovered new products)."""
    return await _latest_agent_output("product_discoverer", db)


# ── Agent Output Fallbacks (for when signal tables are empty) ─────

@router.get("/agent-output/{agent_name}")
async def agent_output_fallback(agent_name: str, db: AsyncSession = Depends(get_db)):
    """Latest agent analysis text for any signal agent (fallback when tables are empty)."""
    return await _latest_agent_output(agent_name, db)


# ── Insight Cards ─────────────────────────────────────────────────

@router.get("/insights", response_model=list[InsightCardResponse])
async def latest_insights(
    category: str | None = None,
    confidence: str | None = None,
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Latest synthesized insight cards from the insight synthesizer agent."""
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.agent_name == "insight_synthesizer", AgentRun.status == "success")
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return []

    # Try output_json first, then parse output text
    cards = []
    if run.output_json:
        raw = run.output_json if isinstance(run.output_json, list) else [run.output_json]
        cards = raw
    elif run.output:
        try:
            parsed = json.loads(run.output)
            cards = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            return []

    # Filter
    if category:
        cards = [c for c in cards if c.get("category") == category]
    if confidence:
        cards = [c for c in cards if c.get("confidence") == confidence]

    return [
        InsightCardResponse(
            category=c.get("category"),
            color=c.get("color"),
            insight=c.get("insight"),
            signals_used=c.get("signals_used"),
            confidence=c.get("confidence"),
            recommended_action=c.get("recommended_action"),
        )
        for c in cards[:limit]
    ]


# ── Helpers ───────────────────────────────────────────────────────

async def _latest_agent_output(agent_name: str, db: AsyncSession) -> dict:
    """Return latest successful agent output (JSON if available, else raw text)."""
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.agent_name == agent_name, AgentRun.status == "success")
        .order_by(AgentRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if not run:
        return {"agent": agent_name, "data": None, "last_run": None}

    data = run.output_json
    if not data and run.output:
        try:
            # Normalize tabs and try parsing
            data = json.loads(run.output.replace("\t", "  "))
        except (json.JSONDecodeError, TypeError):
            data = run.output

    return {
        "agent": agent_name,
        "data": data,
        "last_run": str(run.started_at) if run.started_at else None,
        "duration_seconds": run.duration_seconds,
        "tokens_used": run.tokens_used,
    }
