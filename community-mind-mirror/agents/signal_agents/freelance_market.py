"""Freelance Market Signal Agent — cross-platform freelance intelligence.

Pulls structured gig data from upwork, fiverr, freelancer, peopleperhour, adzuna
and generates cross-platform market intelligence: skill demand trends, budget
benchmarks, underserved niches, platform positioning, and opportunity signals
for AI/tech freelancers and businesses hiring them.
"""

import json
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import text

from database.connection import async_session, MarketGap
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

LOOKBACK_DAYS = 30
MAX_GIGS = 600
FREELANCE_PLATFORMS = [
    "upwork", "fiverr", "freelancer", "peopleperhour",
    "adzuna", "web3career",
]


async def run(usage: TokenUsage | None = None) -> str:
    log = logger.bind(agent="freelance_market")
    if usage is None:
        usage = TokenUsage()

    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    async with async_session() as session:
        # Structured gig data from freelance platforms
        gig_rows = (await session.execute(text("""
            SELECT
                g.gig_title,
                g.project_type,
                g.need_category,
                g.skills_required,
                g.tech_stack,
                g.budget_min_usd,
                g.budget_max_usd,
                g.pay_type,
                g.experience_level,
                g.remote_policy,
                g.need_description,
                p.raw_metadata->>'source' AS platform,
                g.posted_at
            FROM gig_posts g
            JOIN posts p ON p.id = g.post_id
            WHERE g.is_gig = true
              AND p.raw_metadata->>'source' = ANY(:platforms)
              AND (g.posted_at >= :cutoff OR g.posted_at IS NULL)
            ORDER BY g.posted_at DESC NULLS LAST
            LIMIT :limit
        """), {
            "platforms": FREELANCE_PLATFORMS,
            "cutoff": cutoff,
            "limit": MAX_GIGS,
        })).fetchall()

        # Also pull recent Twitter job signals
        twitter_rows = (await session.execute(text("""
            SELECT p.title, p.body
            FROM posts p
            LEFT JOIN gig_posts g ON g.post_id = p.id
            WHERE p.raw_metadata->>'source' = 'twitter'
              AND (g.is_gig = true OR g.id IS NULL)
              AND p.posted_at >= :cutoff
            LIMIT 100
        """), {"cutoff": cutoff})).fetchall()

        # Pain points from freelance market processor
        pain_rows = (await session.execute(text("""
            SELECT title, description, intensity_score, sample_quotes
            FROM pain_points
            WHERE sample_quotes::text LIKE '%freelance_market_processor%'
            ORDER BY intensity_score DESC
            LIMIT 10
        """))).fetchall()

    if not gig_rows:
        log.info("freelance_market_agent_no_data")
        return json.dumps({"status": "no_data", "message": "No gig posts from freelance platforms yet"})

    # Aggregate for LLM context
    from collections import defaultdict
    skill_counts: dict[str, int] = defaultdict(int)
    category_budgets: dict[str, list] = defaultdict(list)
    platform_skills: dict[str, list] = defaultdict(list)
    project_types: dict[str, int] = defaultdict(int)

    sample_descriptions = []
    for row in gig_rows[:50]:  # sample for qualitative context
        if row.need_description:
            sample_descriptions.append(f"[{row.platform}] {row.need_description[:200]}")

    for row in gig_rows:
        for s in (row.skills_required or []):
            s = s.strip().lower()
            if s:
                skill_counts[s] += 1
                platform_skills[row.platform or "unknown"].append(s)
        if row.need_category:
            if row.budget_min_usd:
                category_budgets[row.need_category].append(row.budget_min_usd)
        if row.project_type:
            project_types[row.project_type] += 1

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:25]
    category_avg = {
        cat: round(sum(budgets) / len(budgets))
        for cat, budgets in category_budgets.items()
        if budgets
    }

    platform_top_skills = {
        plat: _top_n(skills, 10)
        for plat, skills in platform_skills.items()
    }

    prev_insights = [
        {"title": r.title, "description": r.description}
        for r in pain_rows
    ]

    twitter_signals = [f"{r.title}" for r in twitter_rows[:30]]

    context = {
        "period": f"Last {LOOKBACK_DAYS} days",
        "total_gigs_analyzed": len(gig_rows),
        "platforms_covered": FREELANCE_PLATFORMS,
        "top_demanded_skills": [{"skill": s, "count": c} for s, c in top_skills],
        "avg_budget_by_category_usd": category_avg,
        "platform_specific_top_skills": platform_top_skills,
        "project_type_distribution": dict(project_types),
        "sample_project_descriptions": sample_descriptions[:20],
        "twitter_hiring_signals": twitter_signals,
        "prior_market_insights": prev_insights,
    }

    prompt = f"""You are a freelance market intelligence analyst. Based on {len(gig_rows)} gig postings from the last {LOOKBACK_DAYS} days across {len(FREELANCE_PLATFORMS)} platforms, generate deep market intelligence.

Data:
{json.dumps(context, indent=2)[:6000]}

Generate a structured intelligence report covering:

1. **SKILL DEMAND MATRIX** — Top 10 skills by demand, their avg budgets, and supply/demand tension
2. **PLATFORM POSITIONING** — What each platform specializes in (Upwork = enterprise, Fiverr = productized, etc.)
3. **BUDGET BENCHMARKS** — Realistic project budgets per category/skill combination
4. **HIGH-OPPORTUNITY NICHES** — Specific high-demand + high-budget + underserved areas
5. **EMERGING SIGNALS** — New skills/categories rising in demand (cross-ref Twitter signals)
6. **STRATEGIC RECOMMENDATIONS** — Actionable advice for: (a) freelancers positioning themselves, (b) companies hiring freelancers

Return JSON:
{{
  "skill_demand_matrix": [
    {{"skill": "...", "demand_count": N, "avg_budget_usd": N, "tension": "high|medium|low", "top_platforms": [...]}}
  ],
  "platform_positioning": {{
    "upwork": "...",
    "fiverr": "...",
    "freelancer": "...",
    "peopleperhour": "..."
  }},
  "budget_benchmarks": [
    {{"category": "...", "project_type": "...", "budget_range": "$X-$Y", "notes": "..."}}
  ],
  "high_opportunity_niches": [
    {{"niche": "...", "demand_signals": "...", "estimated_budget": "...", "why_underserved": "..."}}
  ],
  "emerging_signals": [
    {{"signal": "...", "evidence": "...", "timeline": "..."}}
  ],
  "strategic_recs": {{
    "for_freelancers": ["...", "..."],
    "for_hirers": ["...", "..."]
  }},
  "summary": "2-3 sentence executive summary of the freelance market right now"
}}"""

    result = await call_llm(
        prompt=prompt,
        model="mini",
        parse_json=True,
        usage_tracker=usage,
        max_tokens=2500,
        temperature=0.2,
    )

    if not isinstance(result, dict):
        log.warning("freelance_market_agent_llm_failed")
        return json.dumps({"error": "LLM failed to return structured data"})

    # Store high-opportunity niches as MarketGap records
    stored = 0
    async with async_session() as session:
        for niche in result.get("high_opportunity_niches", []):
            gap = MarketGap(
                gap_title=niche.get("niche", "")[:200],
                gap_description=niche.get("demand_signals", ""),
                evidence_posts=json.dumps({
                    "why_underserved": niche.get("why_underserved"),
                    "estimated_budget": niche.get("estimated_budget"),
                    "source": "freelance_market_agent",
                    "platforms": FREELANCE_PLATFORMS,
                }),
                gap_score=0.8,
                status="validated",
            )
            session.add(gap)
            stored += 1
        await session.commit()

    result["_meta"] = {
        "gigs_analyzed": len(gig_rows),
        "market_gaps_stored": stored,
        "llm_cost_usd": round(usage.estimated_cost_usd, 4),
    }

    log.info("freelance_market_agent_complete",
             niches=stored, gigs=len(gig_rows),
             cost=f"${usage.estimated_cost_usd:.4f}")
    return json.dumps(result)


def _top_n(items: list, n: int) -> list:
    from collections import Counter
    return [s for s, _ in Counter(items).most_common(n)]
