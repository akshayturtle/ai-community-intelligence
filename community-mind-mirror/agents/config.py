"""Agent configuration — model selection, table permissions, schedules."""

import os

from dotenv import load_dotenv

load_dotenv()

# asyncpg needs the raw postgres:// URL (not postgresql+asyncpg://)
_raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cmm_user:cmm_password_dev@localhost:5433/community_mind_mirror",
)
DATABASE_URL = _raw_url.replace("postgresql+asyncpg://", "postgresql://")

# Azure OpenAI config
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_DEPLOYMENT_MINI = os.getenv("AZURE_OPENAI_DEPLOYMENT_MINI", "")

# Model selection per agent — cost optimization
AGENT_MODELS = {
    "research_pipeline": "gpt-4o-mini",
    "traction_scorer": "gpt-4o-mini",
    "market_gap_detector": "gpt-4o",
    "competitive_threat": "gpt-4o-mini",
    "divergence_detector": "gpt-4o-mini",
    "lifecycle_mapper": "gpt-4o-mini",
    "smart_money_tracker": "gpt-4o",
    "talent_flow": "gpt-4o-mini",
    "product_discoverer": "gpt-4o-mini",
    "narrative_shift": "gpt-4o-mini",
    "insight_synthesizer": "gpt-4o",
}


def get_deployment_for_model(model_name: str) -> str:
    """Map model name to Azure deployment."""
    if model_name == "gpt-4o":
        return AZURE_OPENAI_DEPLOYMENT
    return AZURE_OPENAI_DEPLOYMENT_MINI


# Table permissions per agent — principle of least privilege
AGENT_TABLE_PERMISSIONS = {
    "research_pipeline": [
        "news_events", "github_repos", "hf_models", "posts",
        "ph_launches", "so_questions", "topic_mentions", "platforms",
    ],
    "traction_scorer": [
        "discovered_products", "ph_launches", "github_repos",
        "package_downloads", "product_mentions", "posts",
        "news_events", "users",
    ],
    "market_gap_detector": [
        "pain_points", "discovered_products", "product_mentions",
        "ph_launches", "news_events", "yc_companies", "posts",
    ],
    "competitive_threat": [
        "discovered_products", "product_mentions", "migrations",
        "github_repos", "news_events", "personas", "posts", "users",
        "ph_launches",
    ],
    "divergence_detector": [
        "topics", "topic_mentions", "posts", "platforms", "users",
    ],
    "lifecycle_mapper": [
        "news_events", "github_repos", "hf_models", "so_questions",
        "posts", "package_downloads", "topics",
    ],
    "smart_money_tracker": [
        "yc_companies", "news_events", "github_repos", "posts", "topics",
        "funding_rounds",
    ],
    "talent_flow": [
        "news_events", "so_questions", "github_repos", "posts",
        "yc_companies", "package_downloads",
    ],
    "product_discoverer": [
        "posts", "discovered_products", "news_events", "users", "platforms",
    ],
    "narrative_shift": [
        "topics", "posts", "topic_mentions", "news_events", "platforms", "users",
    ],
    "insight_synthesizer": [
        "research_pipeline", "traction_scores", "technology_lifecycle",
        "market_gaps", "competitive_threats", "platform_divergence",
        "topics", "news_events", "posts", "discovered_products",
        "yc_companies", "pain_points", "agent_runs",
    ],
}

# Schedule configuration
AGENT_SCHEDULES = {
    "research_pipeline": {"interval_hours": 24},
    "traction_scorer": {"interval_hours": 24},
    "market_gap_detector": {"interval_hours": 24},
    "competitive_threat": {"interval_hours": 24},
    "divergence_detector": {"interval_hours": 12},
    "lifecycle_mapper": {"interval_hours": 24},
    "smart_money_tracker": {"interval_hours": 168},
    "talent_flow": {"interval_hours": 24},
    "product_discoverer": {"interval_hours": 12},
    "narrative_shift": {"interval_hours": 48},
    "insight_synthesizer": {"interval_hours": 12},
}
