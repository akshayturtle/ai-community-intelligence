# ============================================
# REDDIT TARGETS
# ============================================
REDDIT_SUBREDDITS = [
    # AI and ML communities
    "artificial",
    "MachineLearning",
    "LocalLLaMA",
    "singularity",
    "ChatGPT",
    "ClaudeAI",
    "StableDiffusion",
    "OpenAI",
    "Bard",
    "deeplearning",
    "agi",
    "mlops",
    "datascience",
    "learnmachinelearning",
    "GPT3",
    "midjourney",
    "comfyui",
    # Startup and SaaS communities
    "startups",
    "SaaS",
    "Entrepreneur",
    "indiehackers",
    "smallbusiness",
    "venturecapital",
    "growmybusiness",
    # Developer communities
    "programming",
    "webdev",
    "devops",
    "ExperiencedDevs",
    "cscareerquestions",
    "golang",
    "rust",
    "Python",
    "typescript",
    "react",
    "nextjs",
    "node",
    # Robotics & Hardware
    "robotics",
    "ROS",
    "arduino",
    "raspberry_pi",
    "3Dprinting",
    # Tech industry
    "technology",
    "Futurology",
    "cybersecurity",
    "selfhosted",
]

REDDIT_SCRAPE_CONFIG = {
    "posts_per_subreddit": 500,
    "sort_modes": ["top", "hot", "new"],
    "time_filter": "month",
    "comments_per_post": 200,
    "comment_depth": 6,
    "min_user_karma": 100,
    "min_user_posts": 5,
    "user_history_limit": 100,
    "max_users_per_subreddit": 50,
    "max_comment_posts_per_sub": 20,
    "scrape_interval_hours": 24,
}


# ============================================
# HACKER NEWS TARGETS
# ============================================
HN_SCRAPE_CONFIG = {
    "stories_to_fetch": 500,
    "story_types": [
        "topstories",
        "beststories",
        "newstories",
        "askstories",
        "showstories",
    ],
    "comments_per_story": 100,
    "min_user_karma": 50,
    "min_user_posts": 5,
    "keyword_filter": [
        "AI",
        "artificial intelligence",
        "LLM",
        "GPT",
        "Claude",
        "machine learning",
        "deep learning",
        "neural network",
        "startup",
        "funding",
        "YC",
        "Y Combinator",
        "robotics",
        "autonomous",
        "agent",
        "multi-agent",
        "open source",
        "API",
        "developer tools",
    ],
    "scrape_interval_hours": 12,
}


# ============================================
# YOUTUBE TARGETS
# ============================================
YOUTUBE_CHANNELS = [
    # AI / ML explainers
    {"name": "Two Minute Papers", "channel_id": "UCbfYPyITQ-7l4upoX8nvctg"},
    {"name": "Yannic Kilcher", "channel_id": "UCZHmQk67mSJgfCCTn7xBfew"},
    {"name": "AI Explained", "channel_id": "UCNJ1Ymd5yFuUPtn21xtRbbw"},
    {"name": "Matt Wolfe", "channel_id": "UCJMQEDmGRiELkGLLsZSBJjA"},
    {"name": "Sentdex", "channel_id": "UCfzlCWGWYyIQ0aLC5w48gBQ"},
    {"name": "3Blue1Brown", "channel_id": "UCYO_jab_esuFRV4b17AJtAw"},
    {"name": "Andrej Karpathy", "channel_id": "UCXUPKJO5MZQN11PqgIvyuvQ"},
    {"name": "StatQuest", "channel_id": "UCtYLUTtgS3k1Fg4y5tAhLbw"},
    {"name": "DeepMind", "channel_id": "UCP7jMXSY2xbc3KCAE0MHQ-A"},
    {"name": "OpenAI", "channel_id": "UCXZCJLdBC09xxGZ6gcdrc6A"},
    {"name": "Anthropic", "channel_id": "UCkSBf1J-kKV0yedMbWMK5JA"},
    {"name": "Google DeepMind", "channel_id": "UCP7jMXSY2xbc3KCAE0MHQ-A"},
    {"name": "Weights & Biases", "channel_id": "UCBcFALbCT4cHNga-0d4cOHg"},
    {"name": "HuggingFace", "channel_id": "UCHlPHOJnJRJhh0E57WJaJtg"},
    # Developer / Tech
    {"name": "Fireship", "channel_id": "UCsBjURrPoezykLs9EqgamOA"},
    {"name": "TechLinked", "channel_id": "UCeeFfhMcJa1kjtfZAGskOCA"},
    {"name": "ColdFusion", "channel_id": "UC4QZ_LsYcvcq7qOsOhpAI4A"},
    {"name": "Traversy Media", "channel_id": "UC29ju8bIPH5as8OGnQzwJyA"},
    {"name": "ThePrimeagen", "channel_id": "UC8ENHE5xdFSwx71u3fDH5Xw"},
    {"name": "NetworkChuck", "channel_id": "UC9x0AN7BWHpCDHSm9NiJFJQ"},
    {"name": "Jeff Geerling", "channel_id": "UCR-DXc1voovS8nhAvccRZhg"},
    # Startups / Business / VC
    {"name": "Y Combinator", "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg"},
    {"name": "Lenny's Podcast", "channel_id": "UCLHNx56ekFqxKJdCLaOC3og"},
    {"name": "a]6z", "channel_id": "UCFKkFKIMJrUkbYiZ0p-l6pg"},
    {"name": "Garry Tan", "channel_id": "UCIBgYfDjtWlbJhg--Z4sOgQ"},
    {"name": "All-In Podcast", "channel_id": "UCESLZhusAkFfsNsApnjF_Cg"},
    # Robotics / Hardware
    {"name": "Boston Dynamics", "channel_id": "UC7vVhkEfw4nOGp8TyDk7RcQ"},
    {"name": "Undecided with Matt Ferrell", "channel_id": "UCRBwLPbXGsI2cJe9W1zfSjQ"},
    {"name": "Simone Giertz", "channel_id": "UC3KEoMzNz8eYnwBC34RaKCQ"},
    {"name": "Stuff Made Here", "channel_id": "UCj1VqrHhDte54oLgPG4xpuQ"},
    {"name": "Mark Rober", "channel_id": "UCY1kMZp36IQSyNx_9h4mpCg"},
]

YOUTUBE_SCRAPE_CONFIG = {
    "videos_per_channel": 20,
    "comments_per_video": 100,
    "extract_transcripts": True,
    "scrape_interval_hours": 24,
}


# ============================================
# NEWS RSS FEEDS
# ============================================
NEWS_RSS_FEEDS = [
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tech_news"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tech_news"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tech_news"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech_news"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/", "category": "tech_research"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/", "category": "ai_news"},
    {"name": "Google News AI", "url": "https://news.google.com/rss/search?q=artificial+intelligence+startup", "category": "ai_news"},
    {"name": "Google News LLM", "url": "https://news.google.com/rss/search?q=large+language+model", "category": "ai_news"},
    {"name": "Google News AI Agents", "url": "https://news.google.com/rss/search?q=AI+agents+automation", "category": "ai_news"},
    {"name": "Google News Robotics", "url": "https://news.google.com/rss/search?q=robotics+AI+startup", "category": "robotics"},
    {"name": "Google News Startup Funding", "url": "https://news.google.com/rss/search?q=startup+funding+series+round", "category": "funding"},
    {"name": "TechStartups.com", "url": "https://techstartups.com/feed/", "category": "funding"},
    {"name": "The Robot Report", "url": "https://www.therobotreport.com/feed/", "category": "robotics"},
]

NEWS_SCRAPE_CONFIG = {
    "scrape_interval_hours": 6,
    "max_age_days": 180,
}


# ============================================
# ARXIV TARGETS
# ============================================
ARXIV_SCRAPE_CONFIG = {
    "categories": [
        "cs.AI",
        "cs.LG",
        "cs.CL",
        "cs.CV",
        "cs.RO",
        "cs.MA",
        "cs.SE",
    ],
    "max_results_per_category": 100,
    "sort_by": "submittedDate",
    "sort_order": "descending",
    "scrape_interval_hours": 24,
}


# ============================================
# JOB MARKET TARGETS
# ============================================
# ============================================
# GITHUB TARGETS
# ============================================
GITHUB_WATCHLIST_REPOS = [
    "crewAIInc/crewAI",
    "langchain-ai/langchain",
    "langchain-ai/langgraph",
    "microsoft/autogen",
    "modelcontextprotocol/servers",
    "camel-ai/oasis",
    "666ghj/MiroFish",
    "huggingface/transformers",
    "vllm-project/vllm",
    "ollama/ollama",
]

GITHUB_SEARCH_QUERIES = [
    "topic:ai+topic:machine-learning",
    "ai agent",
    "llm",
    "multi-agent",
    "langchain",
    "crewai",
    "mcp server",
]

GITHUB_SCRAPE_CONFIG = {
    "results_per_query": 100,
    "scrape_interval_hours": 24,
    "request_delay": 1.0,
}


# ============================================
# HUGGING FACE TARGETS
# ============================================
HF_PIPELINE_TAGS = [
    "text-generation",
    "text-to-image",
    "automatic-speech-recognition",
    "object-detection",
]

HF_SCRAPE_CONFIG = {
    "models_per_query": 100,
    "spaces_limit": 50,
    "scrape_interval_hours": 24,
    "request_delay": 0.5,
}


# ============================================
# PRODUCT HUNT TARGETS
# ============================================
PH_TOPICS_TO_TRACK = [
    "artificial-intelligence",
    "developer-tools",
    "saas",
    "machine-learning",
    "productivity",
]

PH_SCRAPE_CONFIG = {
    "top_launches_vote_threshold": 100,
    "ai_launches_limit": 50,
    "scrape_interval_hours": 24,
}


# ============================================
# STACK OVERFLOW TARGETS
# ============================================
SO_TAGS_TO_TRACK = [
    "langchain",
    "openai-api",
    "huggingface",
    "llm",
    "chatgpt-api",
    "pytorch",
    "transformers",
    "crewai",
    "vector-database",
    "pinecone",
    "chromadb",
    "rag",
    "ai-agent",
    "mcp",
]

SO_TREND_KEYWORDS = [
    "llm",
    "agent",
    "rag",
    "embedding",
    "transformer",
    "mcp",
]

SO_SCRAPE_CONFIG = {
    "questions_per_tag": 50,
    "scrape_interval_hours": 24,
    "request_delay": 1.0,
}


# ============================================
# PAPERS WITH CODE TARGETS
# ============================================
PWC_SCRAPE_CONFIG = {
    "papers_limit": 50,
    "trending_methods_limit": 30,
    "scrape_interval_hours": 24,
    "request_delay": 1.0,
}


# ============================================
# PACKAGE DOWNLOAD TRACKING
# ============================================
PYPI_PACKAGES_TO_TRACK = [
    "crewai", "langchain", "langgraph", "autogen-agentchat", "openai",
    "anthropic", "praw", "transformers", "huggingface-hub", "chromadb",
    "pinecone-client", "weaviate-client", "llama-index", "agno",
    "fastapi", "streamlit", "gradio", "vllm",
]

NPM_PACKAGES_TO_TRACK = [
    "langchain", "@langchain/core", "openai", "@anthropic-ai/sdk",
    "ai", "@huggingface/inference",
]

PACKAGE_SCRAPE_CONFIG = {
    "scrape_interval_hours": 24,
    "request_delay": 0.5,
}


# ============================================
# YC COMPANIES
# ============================================
YC_SCRAPE_CONFIG = {
    "latest_batch": "w25",
    "scrape_interval_hours": 168,  # weekly
}


JOB_SCRAPE_CONFIG = {
    "search_terms": [
        "AI engineer",
        "machine learning engineer",
        "LLM engineer",
        "AI agent developer",
        "robotics engineer",
        "prompt engineer",
        "AI safety researcher",
        "MLOps engineer",
        "AI product manager",
        "full stack AI",
        "AI architect",
    ],
    "locations": [
        "San Francisco, CA",
        "New York, NY",
        "London, UK",
        "Bangalore, India",
        "Berlin, Germany",
        "Singapore",
        "Remote",
    ],
    "sites": ["indeed", "linkedin", "google"],
    "results_per_search": 50,
    "hours_old": 168,
    "scrape_interval_hours": 24,
}


# ============================================
# REMOTEOK
# ============================================
REMOTEOK_SCRAPE_CONFIG = {
    "api_url": "https://remoteok.com/api",
    "scrape_interval_hours": 12,
    "request_delay": 2.0,
}


# ============================================
# HIMALAYAS
# ============================================
HIMALAYAS_SCRAPE_CONFIG = {
    "api_url": "https://himalayas.app/jobs/api",
    "max_pages": 50,
    "scrape_interval_hours": 12,
    "request_delay": 1.0,
}


# ============================================
# REMOTIVE
# ============================================
REMOTIVE_SCRAPE_CONFIG = {
    "api_url": "https://remotive.com/api/remote-jobs",
    "categories": [
        "software-dev", "data", "devops", "machine-learning",
        "product", "qa",
    ],
    "scrape_interval_hours": 12,
    "request_delay": 1.0,
}


# ============================================
# THE MUSE
# ============================================
THEMUSE_SCRAPE_CONFIG = {
    "api_url": "https://www.themuse.com/api/public/jobs",
    "categories": ["Data Science", "Engineering", "IT"],
    "levels": ["Mid Level", "Senior Level"],
    "max_pages": 20,
    "scrape_interval_hours": 12,
    "request_delay": 1.0,
}


# ============================================
# ARBEITNOW
# ============================================
ARBEITNOW_SCRAPE_CONFIG = {
    "api_url": "https://www.arbeitnow.com/api/job-board-api",
    "max_pages": 10,
    "scrape_interval_hours": 12,
    "request_delay": 1.5,
}


# ============================================
# ATS (Greenhouse, Lever, Ashby)
# ============================================
ATS_SCRAPE_CONFIG = {
    "scrape_interval_hours": 24,
    "request_delay": 1.0,
    "greenhouse_slugs": [
        "openai", "anthropic", "figma", "notion", "vercel", "databricks",
        "anyscale", "cohere", "inflectionai", "characterai", "mistralai",
        "stabilityai", "huggingface", "deepmind", "scale", "mosaicml",
        "runway", "replit", "midjourney", "perplexityai", "pinecone",
        "weaviate", "qdrant", "langchain", "modal", "weights-and-biases",
        "arize-ai", "dbt-labs", "prefect", "posthog", "stripe", "rippling",
    ],
    "lever_slugs": [
        "openai", "anthropic", "figma", "databricks", "anyscale",
        "cohere", "runway", "replit", "scale", "together-ai",
        "perplexityai", "pinecone", "langchain", "posthog", "brex",
    ],
    "ashby_slugs": [
        "anthropic", "vercel", "notion", "linear", "livekit",
        "replit", "supabase", "resend", "cal-com", "clerk", "inngest",
    ],
}


# ============================================
# HN WHO IS HIRING
# ============================================
HN_HIRING_SCRAPE_CONFIG = {
    "algolia_url": "https://hn.algolia.com/api/v1",
    "max_comments": 500,
    "scrape_interval_hours": 168,
    "request_delay": 0.2,
}


# ============================================
# USAJOBS
# ============================================
USAJOBS_SCRAPE_CONFIG = {
    "api_url": "https://data.usajobs.gov/api/search",
    "keywords": [
        "artificial intelligence", "machine learning", "data scientist",
        "software engineer", "cybersecurity", "cloud engineer",
    ],
    "max_pages": 5,
    "scrape_interval_hours": 12,
    "request_delay": 1.0,
}


# ============================================
# PRODUCT-TARGETED REDDIT SEARCH
# ============================================
PRODUCT_REDDIT_CONFIG = {
    "max_products_per_run": 50,
    "search_time_filter": "month",
    "search_sort": "relevance",
    "search_limit": 100,
    "min_product_mentions": 3,
    "request_delay": 3.0,
    "scrape_interval_hours": 24,
}


# ============================================
# AI GIG / HIRING POST SEARCH
# ============================================
GIG_SUBREDDITS = [
    # Major hiring/freelance boards
    "forhire", "remotejobs", "freelance", "freelance_forhire",
    "jobbit", "hireadev", "GigWork",
    # AI/ML job boards
    "AIJobs", "MachineLearningJobs", "PythonJobs",
    "AIdatatrainingjobs",
    # AI/agent communities (hiring posts)
    "AI_Agents", "AiAutomations", "AiBuilders",
    "AI_developers", "developers",
    # Cofounder / startup hiring
    "cofounderhunt", "WebDeveloperJobs",
    # Regional
    "Indiajobs", "FreelanceIndia",
    # Remote work
    "remotework",
]

GIG_SEARCH_TERMS = []

GIG_SCRAPE_CONFIG = {
    "search_sort": "new",
    "search_time_filter": "month",
    "search_limit": 100,
    "request_delay": 3.0,
    "scrape_interval_hours": 12,
}
