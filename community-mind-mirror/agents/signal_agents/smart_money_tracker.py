"""Agent 7: Smart Money Tracker — Compares YC bets vs general VC bets.

Redesigned: Pre-computes all data in Python, LLM classifies sectors.
"""

import json

import asyncpg
from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.config import (
    DATABASE_URL, DATABASE_SSL, AGENT_MODELS,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    get_deployment_for_model,
)

INSTRUCTIONS = """\
You track where informed capital (YC) flows versus where hype capital (general VC) flows.

YC batch composition is a LEADING INDICATOR. When YC and general VC diverge,
YC is historically right ~73% of the time over 2 years.

Classify each sector:
- consensus_bet: YC high + VC high + builders active
- smart_money_early: YC increasing + VC low → OPPORTUNITY (underfunded)
- hype_capital: YC low/declining + VC high → BUBBLE WARNING
- underfunded: YC + builders present, VC hasn't caught on

You will receive pre-computed evidence data. Classify each sector.

OUTPUT: A JSON array of objects, one per sector:
[
  {
    "sector": "AI agents",
    "yc_companies_last_batch": 12,
    "yc_trend": "increasing",
    "yc_percentage_of_batch": 15.0,
    "vc_funding_articles": 8,
    "vc_signal": "moderate",
    "builder_repos": 45,
    "builder_stars": 120000,
    "community_posts_30d": 500,
    "classification": "smart_money_early",
    "reasoning": "YC increased AI agent companies from 8% to 15%. VC funding still low."
  }
]

classification must be one of: consensus_bet, smart_money_early, hype_capital, underfunded

CRITICAL: Return ONLY a valid JSON array with ALL sectors. No markdown, no explanation."""


async def _prefetch_smart_money_data() -> str:
    """Pre-compute YC vs VC vs builder activity per sector."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, ssl=DATABASE_SSL)
    try:
        # Get YC batch composition
        batches = await pool.fetch(
            "SELECT DISTINCT batch FROM yc_companies ORDER BY batch DESC LIMIT 4"
        )
        batch_names = [b["batch"] for b in batches]

        # Get per-sector counts across batches (industries is JSONB array)
        sectors = await pool.fetch("""
            SELECT sector,
                   COUNT(*) FILTER (WHERE batch = $1) as latest_batch,
                   COUNT(*) FILTER (WHERE batch = $2) as prev_batch,
                   COUNT(*) as total
            FROM (
                SELECT jsonb_array_elements_text(industries) as sector, batch
                FROM yc_companies
                WHERE batch = ANY($3)
                AND industries IS NOT NULL AND jsonb_typeof(industries) = 'array'
            ) sub
            GROUP BY sector
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 20
        """, batch_names[0] if batch_names else '',
             batch_names[1] if len(batch_names) > 1 else '',
             batch_names)

        # Get total companies per batch for percentage calculation
        batch_totals = {}
        for bn in batch_names[:2]:
            total = await pool.fetchval(
                "SELECT COUNT(*) FROM yc_companies WHERE batch = $1", bn
            )
            batch_totals[bn] = total or 1

        # Get VC funding news per sector keyword
        funding_news = await pool.fetch("""
            SELECT title FROM news_events
            WHERE source_type = 'news'
            AND (LOWER(title) LIKE '%funding%' OR LOWER(title) LIKE '%raised%'
                 OR LOWER(title) LIKE '%series%' OR LOWER(title) LIKE '%seed%'
                 OR LOWER(title) LIKE '%million%' OR LOWER(title) LIKE '%billion%')
            ORDER BY published_at DESC NULLS LAST
            LIMIT 100
        """)
        funding_titles = [r["title"].lower() for r in funding_news]

        # Also get structured funding rounds
        funding_rounds = await pool.fetch("""
            SELECT sector, COUNT(*) as cnt, STRING_AGG(company_name, ', ' ORDER BY announced_at DESC) as companies
            FROM funding_rounds
            WHERE sector IS NOT NULL
            GROUP BY sector
            ORDER BY cnt DESC
        """)
        funding_by_sector = {r["sector"].lower(): {"count": r["cnt"], "companies": r["companies"]} for r in funding_rounds}

        sector_data = []
        for s in sectors:
            sector_name = s["sector"]
            sector_lower = sector_name.lower()
            sector_keywords = [kw.strip().lower() for kw in sector_lower.replace("/", " ").replace("-", " ").split() if len(kw.strip()) > 2]

            latest = s["latest_batch"]
            prev = s["prev_batch"]
            latest_total = batch_totals.get(batch_names[0], 1) if batch_names else 1
            pct = round(latest / latest_total * 100, 1) if latest_total else 0

            # Determine YC trend
            if latest > prev:
                yc_trend = "increasing"
            elif latest < prev:
                yc_trend = "decreasing"
            else:
                yc_trend = "stable"

            # Count VC funding articles mentioning this sector
            vc_articles = sum(
                1 for title in funding_titles
                if any(kw in title for kw in sector_keywords)
            )

            # Get structured funding data
            fr_data = funding_by_sector.get(sector_lower, {})

            # GitHub builder activity
            gh = {"cnt": 0, "stars": 0}
            for kw in sector_keywords[:3]:
                row = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(stars), 0) as stars "
                    "FROM github_repos WHERE LOWER(description) LIKE $1 "
                    "OR topics::text ILIKE $1",
                    f"%{kw}%"
                )
                if row and row["cnt"] > gh["cnt"]:
                    gh = {"cnt": int(row["cnt"]), "stars": int(row["stars"])}

            # Community posts (last 30 days)
            community = 0
            for kw in sector_keywords[:3]:
                c = await pool.fetchval(
                    "SELECT COUNT(*) FROM posts WHERE LOWER(body) LIKE $1 "
                    "AND posted_at > NOW() - INTERVAL '30 days'",
                    f"%{kw}%"
                ) or 0
                community = max(community, c)

            # Determine VC signal strength
            vc_total = vc_articles + fr_data.get("count", 0)
            if vc_total >= 10:
                vc_signal = "strong"
            elif vc_total >= 4:
                vc_signal = "moderate"
            elif vc_total >= 1:
                vc_signal = "weak"
            else:
                vc_signal = "none"

            sector_data.append({
                "sector": sector_name,
                "yc_latest_batch_count": latest,
                "yc_prev_batch_count": prev,
                "yc_percentage_of_batch": pct,
                "vc_funding_articles": vc_articles,
                "vc_funding_rounds": fr_data.get("count", 0),
                "vc_funded_companies": fr_data.get("companies", ""),
                "vc_signal": vc_signal,
                "builder_repos": gh["cnt"],
                "builder_stars": gh["stars"],
                "community_posts_30d": community,
            })

        return json.dumps(sector_data, indent=2, default=str)
    finally:
        await pool.close()


def create_smart_money_agent() -> Agent:
    model_name = AGENT_MODELS["smart_money_tracker"]

    return Agent(
        name="Smart Money Tracker",
        model=AzureOpenAI(
            id=get_deployment_for_model(model_name),
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        ),
        instructions=INSTRUCTIONS,
        markdown=False,
        use_json_mode=True,
    )


async def run_smart_money_tracker() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_smart_money_data()
    agent = create_smart_money_agent()
    message = f"Classify ALL these sectors based on smart money signals:\n\n{data}"
    response = await agent.arun(message)
    return response.content
