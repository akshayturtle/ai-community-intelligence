"""Agent 1: Research Pipeline Tracker — News → GitHub → HF → Community → Product.

Redesigned: Pre-computes all cross-reference data in Python, LLM classifies stages.
Adapted to use news articles (since ArXiv scraper data is not yet available).
"""

import json
import re

import asyncpg
from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from agents.config import (
    DATABASE_URL, AGENT_MODELS,
    AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION,
    get_deployment_for_model,
)

INSTRUCTIONS = """\
You are an AI research analyst tracking how technologies flow from announcement to adoption.

For each technology/news item you receive pre-computed data showing:
- The original article (title, source, date)
- GitHub repos found with matching keywords
- HuggingFace models found
- Community discussion volume and sentiment
- Product Hunt launches
- Stack Overflow questions
- Package downloads

Classify each into a pipeline stage:
- announcement: news only, no code/community found
- experimentation: code exists (<1K HF downloads, <10 community posts)
- early_adoption: >1K HF downloads OR >50 community posts OR >10 SO questions
- growth: >100K HF downloads AND >500 community posts AND jobs appearing
- mainstream: >1M HF downloads, universally discussed, standard job requirement
- commodity: discussion declining, assumed skill

Calculate velocity:
- fast: multiple signals appeared within 30 days
- moderate: signals building over 30-90 days
- slow: 90-180 days between stages
- stalled: >180 days with little progress

OUTPUT: JSON array. Each entry:
{
  "paper_title": "...",
  "arxiv_id": null,
  "published_at": "...",
  "current_stage": "experimentation",
  "github_repos": [{"repo": "owner/name", "stars": 234}],
  "hf_total_downloads": 12000,
  "community_mention_count": 47,
  "community_sentiment": 0.65,
  "ph_launches": [],
  "so_question_count": 3,
  "pipeline_velocity": "fast",
  "days_paper_to_code": null,
  "days_total_pipeline": null
}

Include ALL items that have ANY signal. Aim for 10-20 entries.
CRITICAL: Return ONLY a valid JSON array. No markdown, no explanation."""


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "and", "or", "but", "not", "this",
    "that", "it", "its", "as", "be", "has", "have", "had", "how", "why",
    "what", "when", "where", "which", "who", "new", "says", "could", "will",
    "may", "can", "get", "got", "use", "more", "most", "about", "over",
    "into", "than", "just", "also", "now", "after", "before", "first",
    "last", "back", "up", "out", "all",
}


def _extract_keywords(title: str) -> list[str]:
    """Extract meaningful search keywords from a news title."""
    # Remove common suffixes like "- TechCrunch"
    title = re.sub(r"\s*[-–|]\s*[A-Z][\w\s]+$", "", title)
    words = re.findall(r"[A-Za-z][a-z]{2,}", title)
    keywords = []
    for w in words:
        wl = w.lower()
        if wl not in STOPWORDS and len(wl) > 2:
            keywords.append(wl)
    # Deduplicate preserving order
    seen = set()
    result = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result[:4]  # Max 4 keywords per article


async def _prefetch_research_data() -> str:
    """Pre-compute cross-reference data for research pipeline analysis."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        # Get recent news articles (non-job, non-stackoverflow)
        articles = await pool.fetch("""
            SELECT id, title, source_name, published_at,
                   LEFT(body, 300) as body_preview, sentiment
            FROM news_events
            WHERE source_type = 'news'
            AND title IS NOT NULL
            ORDER BY published_at DESC NULLS LAST
            LIMIT 40
        """)

        items = []
        for article in articles:
            title = article["title"]
            keywords = _extract_keywords(title)
            if len(keywords) < 2:
                continue

            # Build LIKE patterns for cross-referencing
            gh_repos = []
            hf_models = []
            hf_total_dl = 0
            community_count = 0
            community_sentiment = 0
            ph_launches = []
            so_count = 0
            pkg_downloads = 0

            for kw in keywords[:3]:
                pat = f"%{kw}%"

                # GitHub repos
                repos = await pool.fetch(
                    "SELECT repo_full_name, stars, description "
                    "FROM github_repos "
                    "WHERE LOWER(description) LIKE $1 "
                    "OR LOWER(repo_full_name) LIKE $1 "
                    "ORDER BY stars DESC NULLS LAST LIMIT 3",
                    pat
                )
                for r in repos:
                    name = r["repo_full_name"]
                    if not any(g["repo"] == name for g in gh_repos):
                        gh_repos.append({
                            "repo": name,
                            "stars": r["stars"] or 0,
                        })

                # HF models
                models = await pool.fetch(
                    "SELECT model_id, downloads, likes "
                    "FROM hf_models "
                    "WHERE LOWER(model_id) LIKE $1 "
                    "ORDER BY downloads DESC NULLS LAST LIMIT 3",
                    pat
                )
                for m in models:
                    mid = m["model_id"]
                    if not any(h["model_id"] == mid for h in hf_models):
                        hf_models.append({
                            "model_id": mid,
                            "downloads": m["downloads"] or 0,
                        })
                        hf_total_dl += m["downloads"] or 0

                # Community posts
                post_data = await pool.fetchrow(
                    "SELECT COUNT(*) as cnt, "
                    "AVG(COALESCE((raw_metadata->'sentiment'->>'compound')::float, 0)) as avg_sent "
                    "FROM posts WHERE LOWER(title) LIKE $1 OR LOWER(body) LIKE $1",
                    pat
                )
                if post_data:
                    community_count = max(community_count, post_data["cnt"] or 0)
                    if post_data["avg_sent"]:
                        community_sentiment = round(float(post_data["avg_sent"]), 3)

                # PH launches
                launches = await pool.fetch(
                    "SELECT name, votes_count FROM ph_launches "
                    "WHERE LOWER(tagline) LIKE $1 OR LOWER(name) LIKE $1 "
                    "ORDER BY votes_count DESC LIMIT 2",
                    pat
                )
                for pl in launches:
                    if not any(p["name"] == pl["name"] for p in ph_launches):
                        ph_launches.append({
                            "name": pl["name"],
                            "votes": pl["votes_count"] or 0,
                        })

                # SO questions
                so = await pool.fetchval(
                    "SELECT COUNT(*) FROM so_questions "
                    "WHERE LOWER(title) LIKE $1 OR tags::text ILIKE $1",
                    pat
                ) or 0
                so_count = max(so_count, so)

                # Package downloads
                dl = await pool.fetchval(
                    "SELECT SUM(downloads) FROM package_downloads "
                    "WHERE LOWER(package_name) LIKE $1",
                    pat
                ) or 0
                pkg_downloads = max(pkg_downloads, dl)

            # Only include if there's at least SOME signal
            has_signal = (
                len(gh_repos) > 0 or hf_total_dl > 0 or community_count > 5
                or len(ph_launches) > 0 or so_count > 0 or pkg_downloads > 0
            )

            items.append({
                "title": title,
                "source": article["source_name"],
                "published_at": str(article["published_at"]) if article["published_at"] else None,
                "keywords": keywords,
                "has_signal": has_signal,
                "github_repos": gh_repos[:5],
                "hf_models": hf_models[:5],
                "hf_total_downloads": hf_total_dl,
                "community_mention_count": community_count,
                "community_sentiment": community_sentiment,
                "ph_launches": ph_launches,
                "so_question_count": so_count,
                "package_downloads": int(pkg_downloads),
            })

        return json.dumps(items, indent=2, default=str)
    finally:
        await pool.close()


def create_research_pipeline_agent() -> Agent:
    model_name = AGENT_MODELS["research_pipeline"]

    return Agent(
        name="Research Pipeline Tracker",
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


async def run_research_pipeline() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_research_data()
    agent = create_research_pipeline_agent()
    message = f"Classify ALL these technology items into pipeline stages:\n\n{data}"
    response = await agent.arun(message)
    return response.content
