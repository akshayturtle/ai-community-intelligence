"""Agent 10: Narrative Shift — Tracks how community framing evolves.

Redesigned: Pre-computes temporal post data in Python, LLM interprets shifts.
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
You detect how the community's mental model of a topic CHANGES over time.

Track the FRAMING — not just sentiment, but the metaphor/frame being used.
Example shifts:
- "AI will replace developers" (fear) → "AI is a productivity tool" (tool) → "AI is a junior dev you manage" (colleague)
- "Open source can't compete" (dismissive) → "Open source is catching up" (competitive) → "Open source won" (victory)

You will receive pre-computed data with sample posts per topic across time periods.

For each topic, analyze:
1. The dominant framing in each period
2. How it shifted (shift_type: hype_to_pragmatism, fear_to_acceptance, dismissal_to_adoption, etc.)
3. Whether media leads or follows the community

OUTPUT: JSON array:
{
  "topic_name": "...",
  "topic_id": 1,
  "narrative_timeline": [
    {"period": "older", "dominant_frame": "...", "tone": "...", "sample": "..."},
    {"period": "recent", "dominant_frame": "...", "tone": "...", "sample": "..."}
  ],
  "shift_type": "hype_to_pragmatism",
  "shift_velocity": "fast",
  "media_alignment": "media lagging community by ~3 weeks",
  "prediction": "...",
  "confidence": "high"
}

CRITICAL: Return ONLY a valid JSON array. No markdown, no explanation.
Analyze ALL topics provided."""


async def _prefetch_narrative_data() -> str:
    """Pre-compute temporal post data for narrative analysis."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, ssl=DATABASE_SSL)
    try:
        # Get topics with enough mentions
        topics = await pool.fetch(
            "SELECT id, name, status, total_mentions, velocity "
            "FROM topics WHERE total_mentions > 10 "
            "ORDER BY total_mentions DESC LIMIT 15"
        )

        topic_data = []
        for t in topics:
            tid = t["id"]

            # Get older posts (>7 days)
            older_posts = await pool.fetch("""
                SELECT p.title, LEFT(p.body, 200) as body_preview,
                       p.score, p.subreddit
                FROM topic_mentions tm
                JOIN posts p ON tm.post_id = p.id
                WHERE tm.topic_id = $1
                ORDER BY p.score DESC NULLS LAST
                OFFSET 10 LIMIT 10
            """, tid)

            # Get recent posts (first 10 by score = most popular)
            recent_posts = await pool.fetch("""
                SELECT p.title, LEFT(p.body, 200) as body_preview,
                       p.score, p.subreddit
                FROM topic_mentions tm
                JOIN posts p ON tm.post_id = p.id
                WHERE tm.topic_id = $1
                ORDER BY p.score DESC NULLS LAST
                LIMIT 10
            """, tid)

            # Get news headlines for this topic
            name_lower = t["name"].lower()
            news = await pool.fetch(
                "SELECT title, source_name FROM news_events "
                "WHERE LOWER(title) LIKE $1 ORDER BY id DESC LIMIT 5",
                f"%{name_lower}%"
            )

            if not recent_posts:
                continue

            topic_data.append({
                "topic_id": tid,
                "topic_name": t["name"],
                "status": t["status"],
                "total_mentions": t["total_mentions"],
                "velocity": float(t["velocity"] or 0),
                "older_posts": [
                    {"title": p["title"][:80] if p["title"] else "", "body": p["body_preview"] or "", "score": p["score"], "sub": p["subreddit"]}
                    for p in older_posts
                ],
                "recent_posts": [
                    {"title": p["title"][:80] if p["title"] else "", "body": p["body_preview"] or "", "score": p["score"], "sub": p["subreddit"]}
                    for p in recent_posts
                ],
                "news_headlines": [
                    {"title": n["title"], "source": n["source_name"]}
                    for n in news
                ],
            })

        return json.dumps(topic_data, indent=2, default=str)
    finally:
        await pool.close()


def create_narrative_shift_agent() -> Agent:
    model_name = AGENT_MODELS["narrative_shift"]

    return Agent(
        name="Narrative Shift Detector",
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


async def run_narrative_shift() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_narrative_data()
    agent = create_narrative_shift_agent()
    message = f"Analyze narrative shifts for ALL these topics:\n\n{data}"
    response = await agent.arun(message)
    return response.content
