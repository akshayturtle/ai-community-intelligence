"""Agent 8: Talent Flow — Predicts talent market shifts.

Redesigned: Pre-computes all supply-demand data in Python, LLM classifies.
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
You predict talent market shifts by analyzing supply-demand gaps for AI/tech skills.

For each skill, classify into one of:
- skill_gap: high demand + low supply → salary pressure incoming
- emerging: high learning activity + low demand → future demand spike
- oversupply: high supply + declining demand → risk

You will receive pre-computed evidence. Classify each skill.

OUTPUT: A JSON array of skill objects:
[
  {
    "skill": "AI agent development",
    "category": "skill_gap",
    "demand_score": 85,
    "supply_score": 30,
    "gap": 55,
    "salary_pressure": "high",
    "trend": "widening",
    "job_listings_30d": 67,
    "so_questions_30d": 12,
    "reasoning": "67 job listings but only 12 SO questions. YC batch heavy on agents.",
    "prediction": "Salaries will increase 15-20% in next 6 months"
  }
]

salary_pressure: high, moderate, low, none
trend: widening, stable, narrowing
category: skill_gap, emerging, oversupply

CRITICAL: Return ONLY a valid JSON array with ALL skills. No markdown, no explanation."""


SKILL_KEYWORDS = [
    ("AI agent development", ["agent", "agentic", "crew", "autogen"]),
    ("RAG / retrieval", ["rag", "retrieval", "vector", "embedding"]),
    ("LLM fine-tuning", ["fine-tun", "finetuning", "training", "lora"]),
    ("Prompt engineering", ["prompt engineer", "prompt design"]),
    ("MLOps / deployment", ["mlops", "model deploy", "inference server"]),
    ("Computer vision", ["computer vision", "image recognition", "object detection"]),
    ("NLP / text", ["nlp", "natural language", "text processing"]),
    ("Data engineering", ["data engineer", "data pipeline", "etl"]),
    ("Full-stack AI", ["full stack", "fullstack", "ai app"]),
    ("DevOps / platform", ["devops", "platform engineer", "sre", "infrastructure"]),
    ("Security / AI safety", ["ai safety", "security engineer", "red team"]),
    ("Robotics / embodied AI", ["robotics", "robot", "embodied"]),
]


async def _prefetch_talent_data() -> str:
    """Pre-compute supply-demand signals for each skill area."""
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    try:
        skill_data = []

        for skill_name, keywords in SKILL_KEYWORDS:
            # Demand: job listings
            jobs = 0
            for kw in keywords[:3]:
                j = await pool.fetchval(
                    "SELECT COUNT(*) FROM job_listings "
                    "WHERE LOWER(title) LIKE $1",
                    f"%{kw}%"
                ) or 0
                jobs = max(jobs, j)

            # Recent vs older job trend
            recent_jobs = 0
            older_jobs = 0
            for kw in keywords[:2]:
                rj = await pool.fetchval(
                    "SELECT COUNT(*) FROM job_listings "
                    "WHERE LOWER(title) LIKE $1 "
                    "AND COALESCE(published_at, created_at) > NOW() - INTERVAL '14 days'",
                    f"%{kw}%"
                ) or 0
                recent_jobs = max(recent_jobs, rj)
                oj = await pool.fetchval(
                    "SELECT COUNT(*) FROM job_listings "
                    "WHERE LOWER(title) LIKE $1 "
                    "AND COALESCE(published_at, created_at) BETWEEN NOW() - INTERVAL '30 days' AND NOW() - INTERVAL '14 days'",
                    f"%{kw}%"
                ) or 0
                older_jobs = max(older_jobs, oj)

            # Supply: SO questions (people learning)
            so = 0
            for kw in keywords[:3]:
                s = await pool.fetchval(
                    "SELECT COUNT(*) FROM so_questions "
                    "WHERE LOWER(title) LIKE $1 OR tags::text ILIKE $1",
                    f"%{kw}%"
                ) or 0
                so = max(so, s)

            # Supply: package downloads (active practitioners)
            pkg_dl = 0
            for kw in keywords[:2]:
                dl = await pool.fetchval(
                    "SELECT SUM(downloads) FROM package_downloads "
                    "WHERE LOWER(package_name) LIKE $1",
                    f"%{kw}%"
                ) or 0
                pkg_dl = max(pkg_dl, int(dl))

            # GitHub repos (builder activity)
            gh = 0
            for kw in keywords[:2]:
                g = await pool.fetchval(
                    "SELECT COUNT(*) FROM github_repos "
                    "WHERE LOWER(description) LIKE $1",
                    f"%{kw}%"
                ) or 0
                gh = max(gh, g)

            # YC companies in this area (future demand predictor)
            yc = 0
            for kw in keywords[:2]:
                y = await pool.fetchval(
                    "SELECT COUNT(*) FROM yc_companies "
                    "WHERE industries::text ILIKE $1 "
                    "AND batch IN (SELECT DISTINCT batch FROM yc_companies ORDER BY batch DESC LIMIT 2)",
                    f"%{kw}%"
                ) or 0
                yc = max(yc, y)

            # Community discussion volume
            community = 0
            for kw in keywords[:2]:
                c = await pool.fetchval(
                    "SELECT COUNT(*) FROM posts "
                    "WHERE LOWER(body) LIKE $1 "
                    "AND posted_at > NOW() - INTERVAL '30 days'",
                    f"%{kw}%"
                ) or 0
                community = max(community, c)

            # Only include skills with some signal
            if jobs + so + gh + community == 0:
                continue

            skill_data.append({
                "skill": skill_name,
                "evidence": {
                    "job_listings_total": jobs,
                    "job_listings_recent_14d": recent_jobs,
                    "job_listings_older_14d": older_jobs,
                    "so_questions": so,
                    "package_downloads": pkg_dl,
                    "github_repos": gh,
                    "yc_companies_recent": yc,
                    "community_posts_30d": community,
                },
            })

        return json.dumps(skill_data, indent=2, default=str)
    finally:
        await pool.close()


def create_talent_flow_agent() -> Agent:
    model_name = AGENT_MODELS["talent_flow"]

    return Agent(
        name="Talent Flow Analyzer",
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


async def run_talent_flow() -> str:
    """Pre-fetch data, create agent, run with data as context."""
    data = await _prefetch_talent_data()
    agent = create_talent_flow_agent()
    message = f"Analyze talent supply-demand for ALL these skills:\n\n{data}"
    response = await agent.arun(message)
    return response.content
