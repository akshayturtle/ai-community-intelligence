"""Agent 6: Lifecycle Mapper — Maps technology adoption stage.

Redesigned: Pre-computes all evidence in Python, LLM classifies stages.
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
You determine exactly where each technology sits on the adoption lifecycle.

Stages: Research → Experimentation → Early Adoption → Growth → Mainstream → Commodity

Evidence per stage:
- Research: ArXiv papers only. Zero GitHub, zero community, zero jobs.
- Experimentation: GitHub repos appearing. SO questions say "what is X". HF models uploaded.
- Early Adoption: Growing Reddit threads. "I built X" posts. First job listings. SO: "how to use X". PyPI downloads starting.
- Growth: Jobs exploding. SO: "how to optimize X". PyPI hockey-sticking. Complaints appear (= real usage).
- Mainstream: Jobs stable. SO: "best practices". Standard job requirement.
- Commodity: Discussion declining. "X is boring". Basic assumed skill.

You will receive pre-computed evidence data for each technology. Classify each one.

OUTPUT: A JSON array of objects, one per technology. Example:
[
  {
    "technology_name": "RAG",
    "current_stage": "growth",
    "stage_evidence": {
      "arxiv_papers": 45, "github_repos": 120, "github_total_stars": 50000,
      "hf_models": 30, "hf_downloads": 500000, "so_questions": 89,
      "community_posts_30d": 340, "package_downloads_30d": 2000000, "job_listings": 67
    },
    "arxiv_paper_count": 45,
    "github_repo_count": 120,
    "hf_model_count": 30,
    "so_question_count": 89,
    "job_listing_count": 67,
    "community_mention_count": 340,
    "stage_confidence": "high",
    "reasoning": "Strong across all signals...",
    "trend": "accelerating"
  },
  {
    "technology_name": "LangChain",
    "current_stage": "early_adoption",
    "stage_evidence": { ... },
    "arxiv_paper_count": 5,
    "github_repo_count": 30,
    "hf_model_count": 2,
    "so_question_count": 15,
    "job_listing_count": 8,
    "community_mention_count": 120,
    "stage_confidence": "medium",
    "reasoning": "Growing community interest...",
    "trend": "accelerating"
  }
]

trend options: accelerating, stable, decelerating

CRITICAL: Return ONLY a valid JSON array with ALL technologies. Not a single object — an ARRAY.
No markdown, no explanation. Score ALL technologies provided — do not skip any."""


async def _prefetch_lifecycle_data() -> str:
    """Pre-compute evidence for all technologies from multiple sources."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        # Get technologies from topics + discovered products
        topics = await pool.fetch(
            "SELECT name, total_mentions, velocity FROM topics "
            "WHERE total_mentions > 10 ORDER BY total_mentions DESC LIMIT 25"
        )

        # Also add key products as technologies
        products = await pool.fetch(
            "SELECT canonical_name, total_mentions FROM discovered_products "
            "WHERE status = 'active' AND total_mentions > 20 "
            "ORDER BY total_mentions DESC LIMIT 15"
        )

        # Merge and deduplicate
        tech_names = []
        seen = set()
        for t in topics:
            name = t["name"]
            if name.lower() not in seen:
                tech_names.append({"name": name, "mentions": t["total_mentions"], "velocity": float(t["velocity"] or 0)})
                seen.add(name.lower())
        for p in products:
            name = p["canonical_name"]
            if name.lower() not in seen:
                tech_names.append({"name": name, "mentions": p["total_mentions"], "velocity": 0})
                seen.add(name.lower())

        # Helper: extract search-friendly keywords from topic names
        def get_search_keywords(name: str) -> list[str]:
            """Extract meaningful keywords, filtering out generic stopwords."""
            stopwords = {
                "ai", "in", "the", "of", "and", "for", "with", "a", "to", "is",
                "on", "by", "its", "an", "or", "as", "at", "vs", "about",
            }
            words = [w for w in name.lower().split() if w not in stopwords and len(w) > 2]
            return words if words else [name.lower()]

        tech_data = []
        for tech in tech_names[:30]:
            name = tech["name"]
            keywords = get_search_keywords(name)

            # Also try the full name as a pattern for products (e.g., "LangChain")
            patterns = [f"%{kw}%" for kw in keywords]
            full_pat = f"%{name.lower()}%"
            if full_pat not in patterns:
                patterns.append(full_pat)

            # Aggregate across all keyword patterns
            arxiv = 0
            gh_cnt, gh_stars, gh_velocity = 0, 0, 0.0
            hf_cnt, hf_dl = 0, 0
            so = 0
            pkg_dl = 0
            jobs = 0

            for pat in patterns[:4]:
                # News articles (proxy for arxiv/research)
                a = await pool.fetchval(
                    "SELECT COUNT(*) FROM news_events WHERE LOWER(title) LIKE $1 "
                    "AND source_name NOT IN ('indeed', 'stackoverflow')",
                    pat
                ) or 0
                arxiv = max(arxiv, a)

                # GitHub repos
                gh = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(stars), 0) as total_stars, "
                    "COALESCE(AVG(star_velocity), 0) as avg_velocity "
                    "FROM github_repos WHERE LOWER(repo_full_name) LIKE $1 OR LOWER(description) LIKE $1",
                    pat
                )
                if gh and gh["cnt"] > gh_cnt:
                    gh_cnt = int(gh["cnt"])
                    gh_stars = int(gh["total_stars"])
                    gh_velocity = round(float(gh["avg_velocity"] or 0), 1)

                # HF models
                hf = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(downloads), 0) as total_dl "
                    "FROM hf_models WHERE LOWER(model_id) LIKE $1",
                    pat
                )
                if hf and hf["cnt"] > hf_cnt:
                    hf_cnt = int(hf["cnt"])
                    hf_dl = int(hf["total_dl"])

                # SO questions
                s = await pool.fetchval(
                    "SELECT COUNT(*) FROM so_questions WHERE LOWER(title) LIKE $1 OR tags::text ILIKE $1",
                    pat
                ) or 0
                so = max(so, s)

                # Package downloads
                dl = await pool.fetchval(
                    "SELECT SUM(downloads) FROM package_downloads WHERE LOWER(package_name) LIKE $1",
                    pat
                ) or 0
                pkg_dl = max(pkg_dl, int(dl))

                # Job listings
                j = await pool.fetchval(
                    "SELECT COUNT(*) FROM job_listings WHERE LOWER(title) LIKE $1",
                    pat
                ) or 0
                jobs = max(jobs, j)

            # Community posts — use topic_mentions for topics (more accurate than LIKE)
            community = tech["mentions"]  # Already have from topics table

            tech_data.append({
                "technology": name,
                "community_mentions": community,
                "velocity": tech["velocity"],
                "evidence": {
                    "arxiv_papers": arxiv,
                    "github_repos": gh_cnt,
                    "github_total_stars": gh_stars,
                    "github_avg_velocity": gh_velocity,
                    "hf_models": hf_cnt,
                    "hf_downloads": hf_dl,
                    "so_questions": so,
                    "community_posts": community,
                    "package_downloads": pkg_dl,
                    "job_listings": jobs,
                },
            })

        return json.dumps(tech_data, indent=2, default=str)
    finally:
        await pool.close()


def create_lifecycle_agent() -> Agent:
    model_name = AGENT_MODELS["lifecycle_mapper"]

    return Agent(
        name="Technology Lifecycle Mapper",
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


async def run_lifecycle_mapper() -> str:
    """Pre-fetch data, create agent, run in batches to ensure all get classified."""
    raw_data = await _prefetch_lifecycle_data()
    all_techs = json.loads(raw_data)

    if not all_techs:
        return "[]"

    # Process in batches of 8 to avoid LLM truncation
    BATCH_SIZE = 8
    all_results = []
    agent = create_lifecycle_agent()

    for i in range(0, len(all_techs), BATCH_SIZE):
        batch = all_techs[i:i + BATCH_SIZE]
        batch_json = json.dumps(batch, indent=2, default=str)
        message = (
            f"Classify ALL {len(batch)} technologies below into lifecycle stages. "
            f"Return a JSON array with exactly {len(batch)} objects.\n\n{batch_json}"
        )
        response = await agent.arun(message)
        content = response.content

        # Parse batch result
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                all_results.extend(parsed)
            elif isinstance(parsed, dict):
                all_results.append(parsed)
        except (json.JSONDecodeError, TypeError):
            # Try to extract JSON from text
            import re
            match = re.search(r'\[[\s\S]*\]', content)
            if match:
                try:
                    parsed = json.loads(match.group())
                    all_results.extend(parsed)
                except (json.JSONDecodeError, TypeError):
                    pass

    return json.dumps(all_results, default=str)
