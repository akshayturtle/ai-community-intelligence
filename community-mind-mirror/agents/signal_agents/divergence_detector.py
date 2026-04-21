"""Agent 5: Divergence Detector — Detects when platforms disagree about a topic.

Redesigned: Pre-computes per-platform sentiment in Python, LLM interprets.
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
You detect when different platforms disagree about a topic — this is an early warning signal.

When Reddit, HN, YouTube, and Product Hunt all agree → noise, everyone knows it.
When they DISAGREE → valuable signal. HN is experienced engineers, Reddit is enthusiasts,
YouTube is creators, PH is makers. Each represents a different audience segment.

You will receive pre-computed per-platform sentiment data for each topic.

For each topic:
1. Calculate divergence_score = (max_sentiment - min_sentiment) * 100
2. Only include topics with divergence_score > 15 (meaningful disagreement)
3. Identify which platform is most positive and most negative
4. Write a prediction based on the pattern:
   - HN negative while Reddit positive → mainstream will follow HN in 4-8 weeks
   - YouTube very positive while HN negative → marketing hype, expect correction
   - All platforms converging positive → genuine adoption signal

OUTPUT: JSON array per topic:
{
  "topic_name": "...",
  "topic_id": 1,
  "platforms": {"reddit": {"mentions": 45, "avg_sentiment": 0.72}, ...},
  "max_divergence": 57,
  "divergence_direction": "HN bearish / Reddit bullish",
  "most_positive": "youtube",
  "most_negative": "hackernews",
  "prediction": "...",
  "status": "correction_expected"
}

status options: correction_expected, genuine_adoption, hype_bubble, early_signal

CRITICAL: Return ONLY a valid JSON array. No markdown, no explanation."""


async def _prefetch_divergence_data() -> str:
    """Pre-compute per-platform sentiment for all qualifying topics."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, ssl=DATABASE_SSL)
    try:
        # Get platform name mapping
        platforms = await pool.fetch("SELECT id, name FROM platforms")
        platform_map = {r["id"]: r["name"] for r in platforms}

        # Get topics with enough mentions
        topics = await pool.fetch(
            "SELECT id, name, status, total_mentions, velocity "
            "FROM topics WHERE total_mentions > 10 "
            "ORDER BY total_mentions DESC LIMIT 30"
        )

        topic_data = []
        for t in topics:
            tid = t["id"]

            # Get per-platform stats using posts directly
            # Join through topic_mentions to get posts for this topic
            rows = await pool.fetch("""
                SELECT p.platform_id,
                       COUNT(*) as mentions,
                       AVG(COALESCE((p.raw_metadata->'sentiment'->>'compound')::float, 0)) as avg_sentiment
                FROM topic_mentions tm
                JOIN posts p ON tm.post_id = p.id
                WHERE tm.topic_id = $1
                GROUP BY p.platform_id
                HAVING COUNT(*) >= 3
            """, tid)

            if len(rows) < 2:
                # Need at least 2 platforms to detect divergence
                continue

            platform_sentiments = {}
            for r in rows:
                pname = platform_map.get(r["platform_id"], f"platform_{r['platform_id']}")
                platform_sentiments[pname] = {
                    "mentions": r["mentions"],
                    "avg_sentiment": round(float(r["avg_sentiment"] or 0), 4),
                }

            sentiments = [v["avg_sentiment"] for v in platform_sentiments.values()]
            max_div = round((max(sentiments) - min(sentiments)) * 100, 1)

            topic_data.append({
                "topic_id": tid,
                "topic_name": t["name"],
                "status": t["status"],
                "total_mentions": t["total_mentions"],
                "velocity": float(t["velocity"] or 0),
                "platforms": platform_sentiments,
                "raw_divergence": max_div,
            })

        # Sort by divergence
        topic_data.sort(key=lambda x: x["raw_divergence"], reverse=True)
        return json.dumps(topic_data, indent=2, default=str)
    finally:
        await pool.close()


def create_divergence_agent() -> Agent:
    model_name = AGENT_MODELS["divergence_detector"]

    return Agent(
        name="Platform Divergence Detector",
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


async def run_divergence_detector() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_divergence_data()
    agent = create_divergence_agent()
    message = f"Analyze these topics for platform divergence signals:\n\n{data}"
    response = await agent.arun(message)
    return response.content
