"""Freelance Market Processor — aggregates cross-platform freelance intelligence.

Runs AFTER gig_post_processor has extracted structured data.
Queries GigPost records from freelance platforms (upwork, fiverr, freelancer, etc.)
and uses LLM to produce market intelligence:
  - Top demanded skills and budget ranges per skill
  - Underserved categories (high demand, few suppliers)
  - Platform-specific patterns (Upwork vs Fiverr vs Freelancer)
  - Budget benchmarks by project type and experience level

Stores results as PainPoint records (unmet market needs) for downstream
consumption by signal agents and the dashboard.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import text

from database.connection import async_session, PainPoint
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

# Platforms treated as freelance market data sources
FREELANCE_PLATFORMS = [
    "upwork", "fiverr", "freelancer", "peopleperhour",
    "adzuna", "web3career",
]

LOOKBACK_DAYS = 14
MAX_GIGS_FOR_ANALYSIS = 500


class FreelanceMarketProcessor:
    """Aggregate and analyse gig post data from freelance platforms."""

    def __init__(self):
        self.log = logger.bind(processor="freelance_market")
        self.usage = TokenUsage()

    async def run(self) -> dict:
        self.log.info("freelance_market_start")

        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

        async with async_session() as session:
            # Pull structured gig data from dedicated freelance platforms
            rows = (await session.execute(text("""
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
                "limit": MAX_GIGS_FOR_ANALYSIS,
            })).fetchall()

        if not rows:
            self.log.info("freelance_market_no_data", hint="Run gig_post_processor first")
            return {"gigs_analyzed": 0, "insights": 0}

        self.log.info("freelance_market_data_loaded", gigs=len(rows))

        # Aggregate statistics
        skill_counts: dict[str, int] = defaultdict(int)
        skill_budgets: dict[str, list[float]] = defaultdict(list)
        category_counts: dict[str, int] = defaultdict(int)
        platform_counts: dict[str, int] = defaultdict(int)
        platform_budgets: dict[str, list[float]] = defaultdict(list)
        project_type_counts: dict[str, int] = defaultdict(int)
        exp_level_counts: dict[str, int] = defaultdict(int)

        for row in rows:
            platform = row.platform or "unknown"
            platform_counts[platform] += 1

            # Budget (use midpoint)
            if row.budget_min_usd and row.budget_max_usd:
                mid = (row.budget_min_usd + row.budget_max_usd) / 2
                platform_budgets[platform].append(mid)
            elif row.budget_min_usd:
                platform_budgets[platform].append(row.budget_min_usd)

            for skill in (row.skills_required or []):
                s = skill.strip().lower()
                if s:
                    skill_counts[s] += 1
                    if row.budget_min_usd:
                        skill_budgets[s].append(row.budget_min_usd)

            if row.need_category:
                category_counts[row.need_category] += 1
            if row.project_type:
                project_type_counts[row.project_type] += 1
            if row.experience_level:
                exp_level_counts[row.experience_level] += 1

        # Build summary for LLM
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:30]
        top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        skill_budget_summary = {}
        for skill, _ in top_skills[:20]:
            budgets = skill_budgets.get(skill, [])
            if budgets:
                skill_budget_summary[skill] = {
                    "avg_usd": round(sum(budgets) / len(budgets)),
                    "max_usd": round(max(budgets)),
                    "count": skill_counts[skill],
                }

        platform_avg_budgets = {
            p: round(sum(b) / len(b)) if b else 0
            for p, b in platform_budgets.items()
        }

        market_summary = {
            "period_days": LOOKBACK_DAYS,
            "total_gigs": len(rows),
            "by_platform": dict(platform_counts),
            "avg_budget_by_platform_usd": platform_avg_budgets,
            "top_skills_demanded": [
                {"skill": s, "count": c, **skill_budget_summary.get(s, {})}
                for s, c in top_skills
            ],
            "top_categories": dict(top_categories),
            "project_types": dict(project_type_counts),
            "experience_levels": dict(exp_level_counts),
        }

        # LLM: generate market intelligence insights
        prompt = f"""You are a freelance market analyst. Based on {len(rows)} gig postings from the last {LOOKBACK_DAYS} days across freelance platforms, identify the most actionable market intelligence insights.

Market data:
{json.dumps(market_summary, indent=2)}

Generate 5-8 specific, actionable insights. Focus on:
1. Skills with HIGH demand but likely LOW supply (high count, high budget = opportunity)
2. Emerging categories with growing demand
3. Platform-specific patterns (what differs between upwork vs fiverr vs freelancer)
4. Budget benchmarks per skill category
5. Underserved niches (high budget + low volume = unmet demand)

Return JSON array:
[
  {{
    "title": "Concise insight title (max 80 chars)",
    "description": "2-3 sentence actionable description with specific numbers from the data",
    "category": "skill_demand" | "budget_benchmark" | "platform_pattern" | "emerging_niche" | "underserved_market",
    "platforms": ["upwork", ...],
    "skills_involved": ["skill1", "skill2"],
    "urgency": "high" | "medium" | "low",
    "avg_budget_usd": number or null
  }},
  ...
]"""

        insights_raw = await call_llm(
            prompt=prompt,
            model="mini",
            parse_json=True,
            usage_tracker=self.usage,
            max_tokens=2000,
            temperature=0.2,
        )

        if not isinstance(insights_raw, list):
            self.log.warning("freelance_market_llm_failed")
            return {"gigs_analyzed": len(rows), "insights": 0}

        # Store each insight as a PainPoint with source="freelance_market"
        stored = 0
        async with async_session() as session:
            for insight in insights_raw:
                title = insight.get("title", "")[:200]
                if not title:
                    continue
                desc = insight.get("description", "")
                category = insight.get("category", "freelance_market")
                skills = insight.get("skills_involved", [])
                platforms_involved = insight.get("platforms", FREELANCE_PLATFORMS)
                urgency = insight.get("urgency", "medium")
                avg_budget = insight.get("avg_budget_usd")

                # Use PainPoint table to store market insights
                # intensity_score: high=0.9, medium=0.6, low=0.3
                intensity = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(urgency, 0.5)

                pain = PainPoint(
                    title=title,
                    description=desc,
                    intensity_score=intensity,
                    post_count=len(rows),
                    has_solution=False,
                    mentioned_products=json.dumps(skills),
                    platforms=json.dumps(platforms_involved),
                    sample_quotes=json.dumps({
                        "category": category,
                        "skills": skills,
                        "avg_budget_usd": avg_budget,
                        "data_source": "freelance_market_processor",
                        "period_days": LOOKBACK_DAYS,
                    }),
                )
                session.add(pain)
                stored += 1
            await session.commit()

        self.log.info(
            "freelance_market_complete",
            gigs=len(rows),
            insights=stored,
            cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"gigs_analyzed": len(rows), "insights": stored, "platforms": dict(platform_counts)}
