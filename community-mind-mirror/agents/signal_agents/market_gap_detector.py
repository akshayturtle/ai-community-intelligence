"""Agent 3: Market Gap Detector — Finds problems with no solution (startup opportunities).

Redesigned: Pre-computes all gap data in Python, LLM analyzes and scores.
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
You are a venture capital analyst identifying billion-dollar startup opportunities.

A market gap is: HIGH community pain + ZERO good solutions + GROWING demand signals.

You will receive pre-computed data including pain points, complaint themes,
existing products, funding, jobs, and YC presence.

For each pain point / complaint theme, determine:
1. gap_signal: wide_open (pain > 70, products = 0) | emerging (pain > 50, products <= 3) | competitive (products > 5) | saturated (products > 20)
2. opportunity_score = pain_score * (1 / max(existing_products, 1)) * (1 + job_postings/100)
3. reasoning: Why the pain is real, why solutions are insufficient, why timing is right

OUTPUT: JSON array sorted by opportunity_score DESC:
{
  "problem_title": "...",
  "pain_score": 94,
  "complaint_count": 142,
  "existing_products": 0,
  "existing_product_names": [],
  "total_funding_in_space": 0,
  "funded_startups": [],
  "job_postings_related": 23,
  "yc_batch_presence": 0.52,
  "gap_signal": "wide_open",
  "opportunity_score": 97.3,
  "reasoning": "..."
}

CRITICAL: Return ONLY a valid JSON array. No markdown, no explanation.
Generate at least 5 gap entries from the data provided."""


async def _prefetch_gap_data() -> str:
    """Pre-compute all market gap data."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, ssl=DATABASE_SSL)
    try:
        # Source 1: Existing pain points
        pain_points = await pool.fetch(
            "SELECT title, description, intensity_score, post_count, has_solution, "
            "mentioned_products, platforms, sample_quotes "
            "FROM pain_points ORDER BY intensity_score DESC LIMIT 25"
        )

        # Source 2: Mine negative-sentiment posts for complaint themes
        # sentiment is stored as JSON object with compound field
        negative_posts = await pool.fetch(
            "SELECT title, body, subreddit, platform_id, "
            "COALESCE((raw_metadata->'sentiment'->>'compound')::float, 0) as sentiment "
            "FROM posts WHERE (raw_metadata->'sentiment'->>'compound')::float < -0.2 "
            "ORDER BY (raw_metadata->'sentiment'->>'compound')::float ASC LIMIT 50"
        )

        # Source 3: Top complaint product mentions
        complaints = await pool.fetch(
            "SELECT dp.canonical_name, COUNT(*) as complaint_count "
            "FROM product_mentions pm "
            "JOIN discovered_products dp ON pm.product_id = dp.id "
            "WHERE pm.context_type = 'complaint' "
            "GROUP BY dp.canonical_name ORDER BY complaint_count DESC LIMIT 15"
        )

        # Context data: products, funding, YC, jobs, PH launches
        products = await pool.fetch(
            "SELECT canonical_name, category, total_mentions FROM discovered_products "
            "WHERE status = 'active' ORDER BY total_mentions DESC"
        )

        funding = await pool.fetch(
            "SELECT company_name, amount, stage, sector FROM funding_rounds "
            "WHERE amount IS NOT NULL ORDER BY amount DESC LIMIT 20"
        )

        yc = await pool.fetch(
            "SELECT name, batch, description FROM yc_companies "
            "ORDER BY batch DESC LIMIT 30"
        )

        jobs_by_sector = await pool.fetch(
            "SELECT title FROM job_listings LIMIT 100"
        )

        ph_recent = await pool.fetch(
            "SELECT name, tagline, votes_count FROM ph_launches "
            "ORDER BY votes_count DESC LIMIT 20"
        )

        # Build context
        data = {
            "pain_points": [
                {
                    "title": p["title"],
                    "description": p["description"],
                    "intensity": float(p["intensity_score"] or 0),
                    "post_count": p["post_count"],
                    "has_solution": p["has_solution"],
                    "mentioned_products": json.loads(p["mentioned_products"]) if isinstance(p["mentioned_products"], str) else p["mentioned_products"],
                }
                for p in pain_points
            ],
            "negative_posts_sample": [
                {
                    "title": p["title"][:100] if p["title"] else "",
                    "body": (p["body"] or "")[:200],
                    "sentiment": round(float(p["sentiment"]), 3),
                    "subreddit": p["subreddit"],
                }
                for p in negative_posts
            ],
            "top_complained_products": [
                {"product": c["canonical_name"], "complaints": c["complaint_count"]}
                for c in complaints
            ],
            "existing_products": [
                {"name": p["canonical_name"], "category": p["category"], "mentions": p["total_mentions"]}
                for p in products
            ],
            "recent_funding": [
                {"company": f["company_name"], "amount": str(f["amount"]), "stage": f["stage"], "sector": f["sector"]}
                for f in funding
            ],
            "yc_companies": [
                {"name": y["name"], "batch": y["batch"], "description": (y["description"] or "")[:100]}
                for y in yc
            ],
            "job_titles_sample": [j["title"][:80] for j in jobs_by_sector],
            "ph_launches": [
                {"name": p["name"], "tagline": p["tagline"], "votes": p["votes_count"]}
                for p in ph_recent
            ],
        }

        return json.dumps(data, indent=2, default=str)
    finally:
        await pool.close()


def create_market_gap_agent() -> Agent:
    model_name = AGENT_MODELS["market_gap_detector"]

    return Agent(
        name="Market Gap Detector",
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


async def run_market_gap_detector() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_gap_data()
    agent = create_market_gap_agent()
    message = (
        "Analyze this community data to identify market gaps and startup opportunities. "
        "Find at least 5 gaps.\n\n" + data
    )
    response = await agent.arun(message)
    return response.content
