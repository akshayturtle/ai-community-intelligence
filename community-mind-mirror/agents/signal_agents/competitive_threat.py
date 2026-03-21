"""Agent 4: Competitive Threat Scorer — Scores competitive threats per product.

Redesigned: Pre-computes all threat signals in Python, LLM scores and summarizes.
"""

import json

import asyncpg
from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.config import (
    DATABASE_URL, AGENT_MODELS,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    get_deployment_for_model,
)

INSTRUCTIONS = """\
You are a competitive intelligence analyst. Score competitive threats using unfakeable signals.

You will receive pre-computed data for each product and its competitors.

For each competitor, assign a threat_score (0-100) based on:
- Migrations away from target (highest weight — people actually switching)
- GitHub velocity (momentum indicator)
- Hiring activity (growth signal)
- Community sentiment (perception)
- Co-mention frequency (direct comparison)

Write a concise executive summary for each threat.

OUTPUT: A JSON array with one object per target product:
[
  {
    "target_product": "Cursor",
    "category": "ai_coding",
    "competitors": [
      {
        "name": "Copilot",
        "threat_score": 75,
        "migrations_from_target": 12,
        "gh_star_velocity": 200,
        "hiring_count": 8,
        "avg_sentiment": 0.72,
        "opinion_leaders_flipped": 0,
        "summary": "Growing threat. 12 users migrated, strong GitHub momentum."
      }
    ]
  }
]

CRITICAL: Return ONLY a valid JSON array. No markdown, no explanation.
Score ALL products provided."""


async def _prefetch_competitive_data() -> str:
    """Pre-compute competitive signals for each product category."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        # Get product categories with 2+ products
        categories = await pool.fetch("""
            SELECT category, COUNT(*) as cnt,
                   ARRAY_AGG(canonical_name ORDER BY total_mentions DESC) as products
            FROM discovered_products
            WHERE status = 'active' AND confidence >= 0.7
            GROUP BY category
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 8
        """)

        competitive_data = []
        for cat in categories:
            products = cat["products"]
            target = products[0]
            competitors = products[1:]

            comp_data = []
            for comp_name in competitors:
                # Migrations from target to competitor
                migrations = await pool.fetchval(
                    "SELECT COUNT(*) FROM migrations m "
                    "JOIN discovered_products fp ON m.from_product_id = fp.id "
                    "JOIN discovered_products tp ON m.to_product_id = tp.id "
                    "WHERE fp.canonical_name = $1 AND tp.canonical_name = $2",
                    target, comp_name
                ) or 0

                # GitHub velocity for competitor
                gh = await pool.fetchrow(
                    "SELECT stars, star_velocity FROM github_repos "
                    "WHERE LOWER(repo_full_name) LIKE $1 OR LOWER(description) LIKE $1 "
                    "ORDER BY stars DESC LIMIT 1",
                    f"%{comp_name.lower()}%"
                )
                gh_velocity = round(float(gh["star_velocity"] or 0), 1) if gh else 0
                gh_stars = int(gh["stars"] or 0) if gh else 0

                # Hiring activity
                hiring = await pool.fetchval(
                    "SELECT COUNT(*) FROM job_listings "
                    "WHERE LOWER(title) LIKE $1",
                    f"%{comp_name.lower()}%"
                ) or 0

                # Community sentiment
                sentiment = await pool.fetchval(
                    "SELECT AVG(sentiment) FROM product_mentions "
                    "WHERE product_id = (SELECT id FROM discovered_products WHERE canonical_name = $1) "
                    "AND sentiment IS NOT NULL",
                    comp_name
                )

                # Co-mentions (posts mentioning both products)
                co_mentions = await pool.fetchval(
                    "SELECT COUNT(*) FROM posts "
                    "WHERE LOWER(body) LIKE $1 AND LOWER(body) LIKE $2",
                    f"%{target.lower()}%", f"%{comp_name.lower()}%"
                ) or 0

                comp_data.append({
                    "name": comp_name,
                    "evidence": {
                        "migrations_from_target": migrations,
                        "gh_stars": gh_stars,
                        "gh_star_velocity": gh_velocity,
                        "hiring_count": hiring,
                        "avg_sentiment": round(float(sentiment), 3) if sentiment else None,
                        "co_mentions": co_mentions,
                    },
                })

            target_mentions = await pool.fetchval(
                "SELECT total_mentions FROM discovered_products WHERE canonical_name = $1",
                target
            ) or 0

            competitive_data.append({
                "target_product": target,
                "category": cat["category"],
                "target_mentions": target_mentions,
                "competitors": comp_data,
            })

        return json.dumps(competitive_data, indent=2, default=str)
    finally:
        await pool.close()


def create_competitive_threat_agent() -> Agent:
    model_name = AGENT_MODELS["competitive_threat"]

    return Agent(
        name="Competitive Threat Scorer",
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


async def run_competitive_threat() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_competitive_data()
    agent = create_competitive_threat_agent()
    message = f"Score competitive threats for ALL these products:\n\n{data}"
    response = await agent.arun(message)
    return response.content
