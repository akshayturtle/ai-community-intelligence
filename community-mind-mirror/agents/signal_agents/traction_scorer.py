"""Agent 2: Traction Scorer — Scores real traction of products (anti-hype).

Redesigned: Pre-computes all data in Python, sends to LLM for scoring in one shot.
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
You are a startup due diligence analyst scoring REAL traction of AI products.

KEY PRINCIPLE: Product Hunt votes and social media hype are easy to fake.
GitHub commits from non-founders, PyPI downloads, organic community recommendations,
and job postings are NOT fakeable. Weight unfakeable signals heavily.

You will receive pre-computed data for each product. Score each one.

Score weights (PH votes intentionally excluded from score, shown for context):
- GitHub stars: 15 pts max. normalize(stars, 0, 50000) * 15
- Star velocity: 15 pts max. normalize(star_velocity, 0, 1000) * 15
- Non-founder contributors: 15 pts max. normalize(nfc, 0, 100) * 15
- Package downloads (PyPI+npm): 20 pts max. normalize(downloads, 0, 1000000) * 20
- Organic mentions: 15 pts max. normalize(organic, 0, 500) * 15
- Job listings: 10 pts max. normalize(jobs, 0, 50) * 10
- Recommendation rate: 10 pts max. normalize(rec_rate, 0, 100) * 10

normalize(x, min, max) = clamp((x - min) / (max - min), 0, 1)

Labels:
- 80+: verified_traction
- 60-80: growing
- 40-60: early
- 20-40: hype_only
- <20: dead

RED FLAG: If PH votes > 500 but traction_score < 40 → mark "hype_only" with red flag.

OUTPUT: JSON array sorted by traction_score DESC. Every entry MUST have:
entity_name, entity_type, ph_votes, gh_stars, gh_star_velocity,
gh_non_founder_contributors, pypi_monthly_downloads, npm_monthly_downloads,
organic_mentions, self_promo_mentions, job_listings, recommendation_rate,
traction_score, traction_label, red_flags, score_breakdown, reasoning

CRITICAL: Return ONLY a valid JSON array — no markdown, no explanation."""


async def _prefetch_product_data() -> str:
    """Pre-fetch all product data from DB, return as formatted context string."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        # Get active products — use low threshold so all tracked products get scored
        # (products with little data will simply score low, which is useful signal)
        products = await pool.fetch(
            "SELECT id, canonical_name, category, total_mentions, aliases "
            "FROM discovered_products WHERE status = 'active' AND total_mentions >= 1 "
            "ORDER BY total_mentions DESC LIMIT 50"
        )

        product_data = []
        for p in products:
            pid = p["id"]
            name = p["canonical_name"]
            name_lower = name.lower()
            aliases = json.loads(p["aliases"]) if isinstance(p["aliases"], str) else (p["aliases"] or [])

            # Build ILIKE patterns for matching
            patterns = [f"%{name_lower}%"] + [f"%{a.lower()}%" for a in aliases if a]

            # PH votes
            ph = await pool.fetchrow(
                "SELECT votes_count, comments_count FROM ph_launches "
                "WHERE LOWER(name) LIKE $1 ORDER BY votes_count DESC LIMIT 1",
                f"%{name_lower}%"
            )

            # GitHub — search repo name, full name, and description with all patterns
            gh = None
            for pat in patterns[:3]:  # Try first 3 patterns (name + up to 2 aliases)
                gh = await pool.fetchrow(
                    "SELECT repo_full_name, stars, star_velocity, non_founder_contributors, forks "
                    "FROM github_repos WHERE LOWER(name) LIKE $1 "
                    "OR LOWER(repo_full_name) LIKE $1 OR LOWER(description) LIKE $1 "
                    "ORDER BY stars DESC LIMIT 1",
                    pat
                )
                if gh:
                    break

            # Package downloads (PyPI)
            pypi_dl = await pool.fetchval(
                "SELECT SUM(downloads) FROM package_downloads "
                "WHERE LOWER(package_name) LIKE $1 AND registry = 'pypi'",
                f"%{name_lower}%"
            ) or 0

            # Package downloads (npm)
            npm_dl = await pool.fetchval(
                "SELECT SUM(downloads) FROM package_downloads "
                "WHERE LOWER(package_name) LIKE $1 AND registry = 'npm'",
                f"%{name_lower}%"
            ) or 0

            # Product mentions by type
            mentions = await pool.fetch(
                "SELECT context_type, COUNT(*) as cnt FROM product_mentions "
                "WHERE product_id = $1 GROUP BY context_type",
                pid
            )
            mention_map = {r["context_type"]: r["cnt"] for r in mentions}

            # Self-promo detection
            self_promo = await pool.fetchval(
                "SELECT COUNT(*) FROM product_mentions "
                "WHERE product_id = $1 AND context_type = 'mention'",
                pid
            ) or 0

            # Job listings — search title, description, and tags
            jobs = await pool.fetchval(
                "SELECT COUNT(*) FROM job_listings "
                "WHERE LOWER(title) LIKE $1 OR LOWER(description) LIKE $1 "
                "OR tags::text ILIKE $1",
                f"%{name_lower}%"
            ) or 0

            # Recommendation rate
            recs = mention_map.get("recommendation", 0)
            complaints = mention_map.get("complaint", 0)
            total_context = recs + complaints + mention_map.get("comparison", 0)
            rec_rate = round(recs / total_context * 100, 1) if total_context > 0 else 0

            entry = {
                "product_name": name,
                "category": p["category"],
                "total_community_mentions": p["total_mentions"],
                "ph_votes": ph["votes_count"] if ph else 0,
                "ph_comments": ph["comments_count"] if ph else 0,
                "gh_repo": gh["repo_full_name"] if gh else None,
                "gh_stars": gh["stars"] if gh else 0,
                "gh_star_velocity": float(gh["star_velocity"] or 0) if gh else 0,
                "gh_non_founder_contributors": gh["non_founder_contributors"] if gh else 0,
                "gh_forks": gh["forks"] if gh else 0,
                "pypi_downloads": int(pypi_dl),
                "npm_downloads": int(npm_dl),
                "organic_mentions": mention_map.get("mention", 0),
                "recommendations": recs,
                "complaints": complaints,
                "comparisons": mention_map.get("comparison", 0),
                "self_promo_mentions": int(self_promo),
                "job_listings": int(jobs),
                "recommendation_rate": rec_rate,
            }
            product_data.append(entry)

        return json.dumps(product_data, indent=2, default=str)
    finally:
        await pool.close()


def create_traction_scorer_agent() -> Agent:
    model_name = AGENT_MODELS["traction_scorer"]

    return Agent(
        name="Traction Scorer",
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


async def run_traction_scorer() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    product_data = await _prefetch_product_data()
    agent = create_traction_scorer_agent()
    message = f"Score ALL of these products. Here is the pre-computed data:\n\n{product_data}"
    response = await agent.arun(message)
    return response.content
