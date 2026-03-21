import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cmm_user:cmm_password_dev@localhost:5433/community_mind_mirror",
)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://cmm_user:cmm_password_dev@localhost:5433/community_mind_mirror",
)

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_DEPLOYMENT_MINI = os.getenv("AZURE_OPENAI_DEPLOYMENT_MINI", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Product Hunt
PH_ACCESS_TOKEN = os.getenv("PH_ACCESS_TOKEN", "")

# Stack Overflow
SO_API_KEY = os.getenv("SO_API_KEY", "")

# USAJobs
USAJOBS_API_KEY = os.getenv("USAJOBS_API_KEY", "")
USAJOBS_EMAIL = os.getenv("USAJOBS_EMAIL", "")

# Scraper settings
SCRAPER_LOG_LEVEL = os.getenv("SCRAPER_LOG_LEVEL", "INFO")
REDDIT_REQUEST_DELAY = float(os.getenv("REDDIT_REQUEST_DELAY", "5.0"))
HN_REQUEST_DELAY = float(os.getenv("HN_REQUEST_DELAY", "0.1"))

# Common HTTP headers
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) CommunityMindMirror/1.0"
