# Community Mind Mirror — Complete Project Plan

## Project Overview

**Two products, one shared data pipeline:**

- **Product 1 — Community Intelligence Dashboard (Real Data):** "What IS happening right now" — Real scraped data from 6 sources, processed, analyzed, and presented as a live intelligence feed. No simulation. A Bloomberg Terminal for community sentiment.
- **Product 2 — Community Mind Mirror (Simulation):** "What WOULD happen IF..." — Inject hypothetical scenarios into an OASIS-powered simulation with real community personas as agents. Predict collective reactions before they happen.

**Build Order:** Product 1 first (immediate value, validates data pipeline), then Product 2 on top.

**Tech Stack:** Python/FastAPI backend, PostgreSQL + Redis, Azure OpenAI for LLM processing, OASIS simulation engine (for Product 2), React or Flutter frontend for dashboard.

---

## Data Sources (6 for MVP)

| # | Source | Type | Access Method | Rate Limit | Cost |
|---|--------|------|---------------|------------|------|
| 1 | Reddit | Community personas | PRAW (Python Reddit API Wrapper) | 100 req/min (free tier) | Free |
| 2 | Hacker News | Community personas | Firebase API | No rate limit | Free |
| 3 | YouTube | Creator opinions + comments | YouTube Data API v3 + youtube-transcript-api | 10,000 units/day | Free |
| 4 | Google News + Tech RSS | News/world state | RSS feeds (no API key) | No limit | Free |
| 5 | ArXiv | Research signals | ArXiv API | 3 req/sec | Free |
| 6 | Job Market | Workforce evolution | JobSpy (Python library) | Varies by board | Free |

---

## Database Schema (PostgreSQL)

### Core Tables

```sql
-- ============================================
-- TABLE: platforms
-- Enum-like table for data source platforms
-- ============================================
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,        -- 'reddit', 'hackernews', 'youtube', 'twitter', 'linkedin'
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO platforms (name) VALUES
('reddit'), ('hackernews'), ('youtube'), ('twitter'), ('linkedin'),
('producthunt'), ('stackoverflow'), ('discord'), ('mastodon'), ('bluesky');


-- ============================================
-- TABLE: users
-- Every unique person discovered across platforms
-- ============================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    platform_id INT REFERENCES platforms(id),
    platform_user_id VARCHAR(255) NOT NULL,   -- Reddit username, HN username, YT channel ID
    username VARCHAR(255),                     -- Display name
    bio TEXT,                                  -- Profile bio if available
    profile_url TEXT,                          -- Link to their profile
    karma_score INT,                           -- Platform-specific influence metric
    account_created_at TIMESTAMP,              -- When they joined the platform
    last_scraped_at TIMESTAMP,                 -- When we last pulled their data
    is_active BOOLEAN DEFAULT TRUE,            -- Still active on platform
    raw_metadata JSONB,                        -- Platform-specific extra fields
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform_id, platform_user_id)
);

CREATE INDEX idx_users_platform ON users(platform_id);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_last_scraped ON users(last_scraped_at);


-- ============================================
-- TABLE: posts
-- Every piece of content (posts, comments, videos, etc.)
-- ============================================
CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    platform_id INT REFERENCES platforms(id),
    post_type VARCHAR(50) NOT NULL,            -- 'submission', 'comment', 'video', 'transcript', 'reply'
    platform_post_id VARCHAR(255),             -- Platform's own ID for this content
    parent_post_id INT REFERENCES posts(id),   -- For comments/replies — links to parent
    title TEXT,                                 -- Post title (submissions, videos)
    body TEXT NOT NULL,                         -- The actual content text
    url TEXT,                                   -- Link to original
    subreddit VARCHAR(255),                     -- Reddit subreddit or equivalent community
    score INT DEFAULT 0,                        -- Upvotes, likes, etc.
    num_comments INT DEFAULT 0,                 -- Comment count
    posted_at TIMESTAMP,                        -- When originally posted
    raw_metadata JSONB,                         -- Extra fields (awards, flair, tags, etc.)
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform_id, platform_post_id)
);

CREATE INDEX idx_posts_user ON posts(user_id);
CREATE INDEX idx_posts_platform ON posts(platform_id);
CREATE INDEX idx_posts_type ON posts(post_type);
CREATE INDEX idx_posts_subreddit ON posts(subreddit);
CREATE INDEX idx_posts_posted_at ON posts(posted_at);
CREATE INDEX idx_posts_score ON posts(score);


-- ============================================
-- TABLE: personas
-- LLM-extracted personality profiles per user
-- ============================================
CREATE TABLE personas (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) UNIQUE,
    core_beliefs JSONB,                        -- Array of key opinions {"topic": "open source AI", "stance": "strongly supportive", "confidence": 0.9}
    communication_style JSONB,                 -- {"formality": "casual", "sarcasm": "high", "length": "short", "uses_data": true}
    emotional_triggers JSONB,                  -- {"anger": ["corporate AI control", "paywalls"], "excitement": ["open source releases", "benchmarks"]}
    expertise_domains JSONB,                   -- ["machine learning", "python", "startups"] with confidence scores
    influence_type VARCHAR(50),                -- 'opinion_leader', 'domain_expert', 'contrarian', 'follower', 'bridge_builder'
    influence_score FLOAT DEFAULT 0,           -- Calculated: karma + reply frequency + engagement rate
    inferred_location VARCHAR(255),            -- Best guess from timezone, mentions, subreddits
    inferred_role VARCHAR(255),                -- 'developer', 'founder', 'investor', 'researcher', 'student', 'manager'
    personality_summary TEXT,                   -- One paragraph "voice" description
    active_topics JSONB,                       -- Topics they engage with most, ranked
    system_prompt TEXT,                         -- Pre-built OASIS agent system prompt
    validation_score FLOAT,                    -- How well persona matches held-out posts (0-1)
    model_used VARCHAR(100),                   -- Which LLM was used for extraction
    extracted_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_personas_influence ON personas(influence_score DESC);
CREATE INDEX idx_personas_role ON personas(inferred_role);
CREATE INDEX idx_personas_location ON personas(inferred_location);


-- ============================================
-- TABLE: cross_platform_identities
-- Links same person across platforms
-- ============================================
CREATE TABLE cross_platform_identities (
    id SERIAL PRIMARY KEY,
    canonical_user_id INT REFERENCES users(id),  -- The "primary" profile
    linked_user_id INT REFERENCES users(id),     -- The matched profile on another platform
    match_confidence FLOAT,                       -- 0-1 confidence of match
    match_method VARCHAR(50),                     -- 'username_exact', 'username_fuzzy', 'bio_match', 'topic_overlap', 'manual'
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(canonical_user_id, linked_user_id)
);


-- ============================================
-- TABLE: community_graph
-- Social connections between users
-- ============================================
CREATE TABLE community_graph (
    id SERIAL PRIMARY KEY,
    source_user_id INT REFERENCES users(id),
    target_user_id INT REFERENCES users(id),
    interaction_type VARCHAR(50),               -- 'replied_to', 'same_thread', 'same_subreddit', 'mentioned'
    interaction_count INT DEFAULT 1,            -- How many times this interaction occurred
    avg_sentiment FLOAT,                        -- Average sentiment of interactions (-1 to 1)
    first_interaction_at TIMESTAMP,
    last_interaction_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_user_id, target_user_id, interaction_type)
);

CREATE INDEX idx_graph_source ON community_graph(source_user_id);
CREATE INDEX idx_graph_target ON community_graph(target_user_id);


-- ============================================
-- TABLE: news_events
-- World state data (news, papers, jobs)
-- ============================================
CREATE TABLE news_events (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,          -- 'news', 'arxiv', 'job_listing', 'funding', 'github_trending'
    source_name VARCHAR(255),                   -- 'TechCrunch', 'ArXiv', 'Google News', 'Indeed', etc.
    title TEXT NOT NULL,
    body TEXT,                                   -- Full text or abstract
    url TEXT,
    authors JSONB,                              -- List of author names
    published_at TIMESTAMP,
    categories JSONB,                           -- ['AI', 'robotics', 'funding']
    entities JSONB,                             -- Extracted entities {"companies": [...], "people": [...], "technologies": [...]}
    sentiment FLOAT,                            -- -1 to 1 community sentiment
    magnitude VARCHAR(20),                      -- 'low', 'medium', 'high', 'critical'
    raw_metadata JSONB,                         -- Source-specific fields
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_news_source_type ON news_events(source_type);
CREATE INDEX idx_news_published ON news_events(published_at);
CREATE INDEX idx_news_categories ON news_events USING GIN(categories);
CREATE INDEX idx_news_entities ON news_events USING GIN(entities);


-- ============================================
-- TABLE: topics
-- Detected trending topics across all sources
-- ============================================
CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,                 -- 'open source vs closed source', 'AI agents replacing SaaS'
    slug VARCHAR(255) UNIQUE,
    description TEXT,
    keywords JSONB,                             -- Keywords that map to this topic
    first_seen_at TIMESTAMP,
    last_seen_at TIMESTAMP,
    velocity FLOAT DEFAULT 0,                   -- How fast discussion is growing
    total_mentions INT DEFAULT 0,
    sentiment_distribution JSONB,               -- {"positive": 0.4, "negative": 0.35, "neutral": 0.25}
    platforms_active JSONB,                     -- {"reddit": 45, "hackernews": 30, "youtube": 12}
    opinion_camps JSONB,                        -- [{"label": "Pro open source", "percentage": 55, "key_argument": "..."}, ...]
    status VARCHAR(20) DEFAULT 'active',        -- 'emerging', 'active', 'peaking', 'declining', 'dead'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_topics_velocity ON topics(velocity DESC);
CREATE INDEX idx_topics_status ON topics(status);


-- ============================================
-- TABLE: topic_mentions
-- Links posts/news to topics
-- ============================================
CREATE TABLE topic_mentions (
    id SERIAL PRIMARY KEY,
    topic_id INT REFERENCES topics(id),
    post_id INT REFERENCES posts(id) NULL,
    news_event_id INT REFERENCES news_events(id) NULL,
    relevance_score FLOAT,                      -- 0-1 how relevant this mention is
    sentiment FLOAT,                            -- -1 to 1 sentiment in this specific mention
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mentions_topic ON topic_mentions(topic_id);


-- ============================================
-- TABLE: simulations (Product 2 — OASIS)
-- ============================================
CREATE TABLE simulations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    scenario TEXT NOT NULL,                      -- The injected stimulus
    scenario_structured JSONB,                  -- {"event": "...", "sector": "...", "magnitude": "high"}
    agent_count INT,                            -- Number of agents in simulation
    agent_filter JSONB,                         -- How agents were selected {"subreddits": [...], "min_influence": 0.5}
    platform_type VARCHAR(50),                  -- 'reddit_like', 'twitter_like', 'dual'
    time_steps INT,                             -- Number of simulation rounds
    model_config JSONB,                         -- LLM model used, temperature, etc.
    status VARCHAR(20) DEFAULT 'pending',       -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================
-- TABLE: simulation_results
-- Output from completed simulations
-- ============================================
CREATE TABLE simulation_results (
    id SERIAL PRIMARY KEY,
    simulation_id INT REFERENCES simulations(id),
    sentiment_trajectory JSONB,                 -- [{"time_step": 1, "positive": 0.6, "negative": 0.2, "neutral": 0.2}, ...]
    opinion_clusters JSONB,                     -- [{"label": "...", "percentage": 40, "key_arguments": [...], "representative_agents": [...]}]
    influencer_pivots JSONB,                    -- [{"agent_id": 123, "from_stance": "...", "to_stance": "...", "at_time_step": 5}]
    viral_content JSONB,                        -- [{"content": "...", "engagement_score": 95, "spread_pattern": "..."}]
    risk_score FLOAT,                           -- 0-1 overall negative reaction risk
    narrative_summary TEXT,                      -- LLM-generated report
    raw_simulation_log JSONB,                   -- Full OASIS output
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================================
-- TABLE: scraper_runs
-- Track scraper execution for monitoring
-- ============================================
CREATE TABLE scraper_runs (
    id SERIAL PRIMARY KEY,
    scraper_name VARCHAR(100) NOT NULL,         -- 'reddit_scraper', 'hn_scraper', 'youtube_scraper', etc.
    status VARCHAR(20) DEFAULT 'running',       -- 'running', 'completed', 'failed'
    records_fetched INT DEFAULT 0,
    records_new INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    metadata JSONB                              -- Any extra run info
);
```

---

## Scraper Architecture

### Project Structure

```
community-mind-mirror/
├── config/
│   ├── settings.py              # Environment variables, API keys, DB connection
│   └── sources.py               # Target subreddits, channels, RSS feeds, search terms
├── scrapers/
│   ├── base_scraper.py          # Abstract base class with common DB write, logging, rate limiting
│   ├── reddit_scraper.py        # PRAW-based Reddit scraper
│   ├── hn_scraper.py            # Hacker News Firebase API scraper
│   ├── youtube_scraper.py       # YouTube Data API + transcript scraper
│   ├── news_scraper.py          # RSS feed aggregator for news sources
│   ├── arxiv_scraper.py         # ArXiv API scraper
│   └── job_scraper.py           # JobSpy-based job market scraper
├── processors/
│   ├── persona_extractor.py     # LLM-based persona extraction from posts
│   ├── topic_detector.py        # Topic clustering and trend detection
│   ├── sentiment_analyzer.py    # Sentiment analysis on posts and news
│   ├── graph_builder.py         # Community graph construction from interactions
│   ├── news_processor.py        # News event structuring and entity extraction
│   ├── identity_linker.py       # Cross-platform identity matching
│   └── persona_validator.py     # Validate persona quality against held-out posts
├── simulation/
│   ├── oasis_adapter.py         # Convert personas to OASIS agent format
│   ├── scenario_builder.py      # Build simulation scenarios from news events
│   ├── simulation_runner.py     # Run OASIS simulation and collect output
│   └── report_agent.py          # Generate simulation reports from results
├── api/
│   ├── main.py                  # FastAPI app entry point
│   ├── routes/
│   │   ├── dashboard.py         # Dashboard data endpoints
│   │   ├── topics.py            # Topic tracking endpoints
│   │   ├── personas.py          # Persona data endpoints
│   │   ├── news.py              # News and events endpoints
│   │   ├── simulations.py       # Simulation CRUD and run endpoints
│   │   └── search.py            # Search across all data
│   └── models/
│       └── schemas.py           # Pydantic models for API
├── scheduler/
│   └── cron_jobs.py             # APScheduler or Celery beat for scraper scheduling
├── database/
│   ├── connection.py            # SQLAlchemy / asyncpg connection
│   └── migrations/              # Alembic migrations
├── requirements.txt
├── docker-compose.yml           # PostgreSQL + Redis + App
├── .env.example
└── README.md
```

### Scraper Configurations

```python
# config/sources.py

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
    # Startup and SaaS communities
    "startups",
    "SaaS",
    "Entrepreneur",
    "indiehackers",
    # Developer communities
    "programming",
    "webdev",
    "devops",
    # Robotics
    "robotics",
    "ROS",
]

REDDIT_SCRAPE_CONFIG = {
    "posts_per_subreddit": 500,        # Top posts to pull per subreddit
    "time_filter": "month",            # 'day', 'week', 'month', 'year', 'all'
    "comments_per_post": 50,           # Top comments per post
    "min_user_karma": 100,             # Minimum karma to consider as agent
    "min_user_posts": 5,               # Minimum posts to build persona
    "user_history_limit": 100,         # Max posts to pull per user profile
    "scrape_interval_hours": 24,       # How often to re-scrape
}


# ============================================
# HACKER NEWS TARGETS
# ============================================
HN_SCRAPE_CONFIG = {
    "stories_to_fetch": 500,           # Top/best/new stories
    "story_types": ["topstories", "beststories", "newstories", "askstories", "showstories"],
    "comments_per_story": 100,         # Comments to pull per story
    "min_user_karma": 50,
    "min_user_posts": 5,
    "keyword_filter": [                # Only stories matching these keywords
        "AI", "artificial intelligence", "LLM", "GPT", "Claude",
        "machine learning", "deep learning", "neural network",
        "startup", "funding", "YC", "Y Combinator",
        "robotics", "autonomous", "agent", "multi-agent",
        "open source", "API", "developer tools",
    ],
    "scrape_interval_hours": 12,
}


# ============================================
# YOUTUBE TARGETS
# ============================================
YOUTUBE_CHANNELS = [
    # AI/ML explainers
    {"name": "Two Minute Papers", "channel_id": "UCbfYPyITQ-7l4upoX8nvctg"},
    {"name": "Yannic Kilcher", "channel_id": "UCZHmQk67mSJgfCCTn7xBfew"},
    {"name": "AI Explained", "channel_id": "UCNJ1Ymd5yFuUPtn21xtRbbw"},
    {"name": "Matt Wolfe", "channel_id": "UCJMQEDmGRiELkGLLsZSBJjA"},
    {"name": "Fireship", "channel_id": "UCsBjURrPoezykLs9EqgamOA"},
    {"name": "Sentdex", "channel_id": "UCfzlCWGWYyIQ0aLC5w48gBQ"},
    {"name": "3Blue1Brown", "channel_id": "UCYO_jab_esuFRV4b17AJtAw"},
    # Tech/startup commentary
    {"name": "Y Combinator", "channel_id": "UCcefcZRL2oaA_uBNeo5UOWg"},
    {"name": "TechLinked", "channel_id": "UCeeFfhMcJa1kjtfZAGskOCA"},
    {"name": "ColdFusion", "channel_id": "UC4QZ_LsYcvcq7qOsOhpAI4A"},
    {"name": "Lenny's Podcast", "channel_id": "UCLHNx56ekFqxKJdCLaOC3og"},
    # Robotics
    {"name": "Boston Dynamics", "channel_id": "UC7vVhkEfw4nOGp8TyDk7RcQ"},
    {"name": "Undecided with Matt Ferrell", "channel_id": "UCRBwLPbXGsI2cJe9W1zfSjQ"},
]

YOUTUBE_SCRAPE_CONFIG = {
    "videos_per_channel": 20,          # Recent videos to pull
    "comments_per_video": 100,         # Top comments per video
    "extract_transcripts": True,       # Pull full video transcripts
    "scrape_interval_hours": 24,
}


# ============================================
# NEWS RSS FEEDS
# ============================================
NEWS_RSS_FEEDS = [
    # General tech
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "tech_news"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "tech_news"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "category": "tech_news"},
    {"name": "Wired", "url": "https://www.wired.com/feed/rss", "category": "tech_news"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/", "category": "tech_research"},
    {"name": "VentureBeat", "url": "https://venturebeat.com/feed/", "category": "ai_news"},
    # AI specific
    {"name": "Google News AI", "url": "https://news.google.com/rss/search?q=artificial+intelligence+startup", "category": "ai_news"},
    {"name": "Google News LLM", "url": "https://news.google.com/rss/search?q=large+language+model", "category": "ai_news"},
    {"name": "Google News AI Agents", "url": "https://news.google.com/rss/search?q=AI+agents+automation", "category": "ai_news"},
    {"name": "Google News Robotics", "url": "https://news.google.com/rss/search?q=robotics+AI+startup", "category": "robotics"},
    # Startup/funding
    {"name": "Google News Startup Funding", "url": "https://news.google.com/rss/search?q=startup+funding+series+round", "category": "funding"},
    {"name": "TechStartups.com", "url": "https://techstartups.com/feed/", "category": "funding"},
    # Robotics
    {"name": "The Robot Report", "url": "https://www.therobotreport.com/feed/", "category": "robotics"},
]

NEWS_SCRAPE_CONFIG = {
    "scrape_interval_hours": 6,
    "max_age_days": 180,               # Keep 6 months of news
}


# ============================================
# ARXIV TARGETS
# ============================================
ARXIV_SCRAPE_CONFIG = {
    "categories": [
        "cs.AI",      # Artificial Intelligence
        "cs.LG",      # Machine Learning
        "cs.CL",      # Computation and Language (NLP)
        "cs.CV",      # Computer Vision
        "cs.RO",      # Robotics
        "cs.MA",      # Multi-Agent Systems
        "cs.SE",      # Software Engineering
    ],
    "max_results_per_category": 100,
    "sort_by": "submittedDate",
    "sort_order": "descending",
    "scrape_interval_hours": 24,
}


# ============================================
# JOB MARKET TARGETS
# ============================================
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
    "hours_old": 168,                  # Last 7 days
    "scrape_interval_hours": 24,
}
```

---

## Phase-by-Phase Build Plan

### Phase 1 — Data Pipeline (Week 1-2)

**Step 1.1: Project setup and database**
- Initialize Python project with FastAPI
- Set up PostgreSQL with Docker
- Run the SQL schema above to create all tables
- Set up Alembic for future migrations
- Create database connection layer (SQLAlchemy async)
- Create base scraper class with common patterns (DB write, logging, rate limiting, error handling, resume support)

**Step 1.2: Reddit scraper**
- Install PRAW: `pip install praw`
- Authenticate with script app credentials (client_id, client_secret, username, password, user_agent)
- For each target subreddit: pull top posts (last 3-6 months), extract comments, collect unique usernames
- For each discovered user: pull their full submission + comment history (up to 100 items)
- Write to `users` and `posts` tables
- Handle rate limiting (PRAW handles this automatically, but add retry logic)
- Track scraper run in `scraper_runs` table
- Save incrementally so crashes don't lose progress

**Step 1.3: Hacker News scraper**
- Hit Firebase API endpoints (no library needed, just HTTP requests)
- Pull top/best/new/ask/show stories, filter by AI/startup keywords
- For each matching story: pull all comments recursively (stories have `kids` arrays pointing to comment IDs)
- Extract unique usernames from story authors and commenters
- For each user: pull profile from `/v0/user/{username}.json` (includes `submitted` list of all their story/comment IDs)
- Write to `users` and `posts` tables
- No rate limit but add polite delays (100ms between requests)

**Step 1.4: YouTube scraper**
- Set up Google Cloud project, enable YouTube Data API v3, get API key
- For each target channel: pull recent videos (channelId → search → video list)
- For each video: pull video details (title, description, stats) and top comments
- Use `youtube-transcript-api` to extract full transcripts (no quota cost)
- Video transcripts go into `news_events` table (source_type = 'youtube_transcript')
- Commenters go into `users` table, comments go into `posts` table
- Monitor quota usage (10,000 units/day)

**Step 1.5: News RSS scraper**
- Use `feedparser` Python library to parse RSS feeds
- For each RSS feed in config: pull latest entries
- Deduplicate by URL (same story appears on multiple feeds)
- Write to `news_events` table with source_type = 'news'
- Run every 6 hours

**Step 1.6: ArXiv scraper**
- Use ArXiv API (HTTP requests to `export.arxiv.org/api/query`)
- Query by category (cs.AI, cs.LG, etc.) sorted by submission date
- Extract title, abstract, authors, categories, published date
- Write to `news_events` table with source_type = 'arxiv'
- Run daily

**Step 1.7: Job market scraper**
- Install JobSpy: `pip install python-jobspy`
- For each search term + location combo: scrape Indeed, LinkedIn, Google Jobs
- Extract job title, company, location, salary range, description, skills required
- Write to `news_events` table with source_type = 'job_listing'
- Run daily

**Step 1.8: Cron scheduler**
- Use APScheduler or Celery Beat to run scrapers on schedule
- Reddit: every 24 hours
- HN: every 12 hours
- YouTube: every 24 hours
- News RSS: every 6 hours
- ArXiv: every 24 hours
- Jobs: every 24 hours
- Add monitoring: log each run to `scraper_runs`, alert on failures

---

### Phase 2 — LLM Processing Layer (Week 2-3)

**Step 2.1: Persona extraction**
- For each user with 5+ posts: batch their posts/comments
- Send to Azure OpenAI (GPT-4o) or Claude with structured extraction prompt
- Prompt template:

```
You are analyzing a social media user's posting history to build a personality profile.
Here are their last {N} posts and comments:

{posts_json}

Extract the following as JSON:
{
  "core_beliefs": [{"topic": "...", "stance": "...", "confidence": 0.0-1.0}],
  "communication_style": {"formality": "casual/formal/mixed", "sarcasm_level": "none/low/medium/high", "typical_length": "terse/medium/verbose", "uses_data": true/false, "uses_analogies": true/false},
  "emotional_triggers": {"anger": ["..."], "excitement": ["..."], "dismissive": ["..."]},
  "expertise_domains": [{"domain": "...", "depth": "surface/intermediate/expert"}],
  "influence_type": "opinion_leader/domain_expert/contrarian/follower/bridge_builder/troll",
  "inferred_location": "...",
  "inferred_role": "developer/founder/investor/researcher/student/manager/journalist",
  "personality_summary": "One paragraph capturing this person's voice and worldview",
  "active_topics": ["..."]
}
```

- Write output to `personas` table
- Use cheaper model (GPT-4o-mini or DeepSeek) for bulk extraction, expensive model (Claude/GPT-4o) for top-influence users
- Process in batches to manage API costs

**Step 2.2: Sentiment analysis**
- For each post in `posts` table: run sentiment analysis
- Can use a lightweight model (VADER, TextBlob) for bulk, LLM for nuanced cases
- Store sentiment score on the post's `raw_metadata` JSONB field
- Aggregate sentiments by topic for the `topics` table

**Step 2.3: Topic detection and clustering**
- Use LLM to extract topics from recent posts across all platforms
- Cluster similar topics together (embedding similarity)
- Detect trending topics based on velocity (mentions per hour increasing)
- Write to `topics` and `topic_mentions` tables
- Update topic status: emerging → active → peaking → declining → dead

**Step 2.4: Community graph construction**
- Scan all comments in `posts` table
- When user A replies to user B: create/update edge in `community_graph`
- When users appear in the same thread: create weaker "same_thread" edges
- When users are active in the same subreddit: create "same_subreddit" edges
- Calculate interaction sentiment for each edge
- Identify opinion leaders (most replied-to, highest average engagement on their posts)

**Step 2.5: News event processing**
- For each news item in `news_events`: extract structured event data via LLM
- Extract: key entities (companies, people, technologies), sector, sentiment for tech community, magnitude
- Cross-reference with community data: when a news event gets discussed on Reddit/HN, link them via `topic_mentions`

**Step 2.6: Cross-platform identity linking**
- Compare usernames across platforms (exact match, fuzzy match)
- Compare post content topics and writing style for near-matches
- Create links in `cross_platform_identities` table
- Merge persona data for linked profiles (richer persona)

**Step 2.7: Persona validation**
- For each persona: take 5 posts the user actually wrote that weren't used for extraction
- Give the persona (system prompt) a thread context and ask it to generate a response
- Compare generated response with actual response on: topic alignment, tone match, opinion direction
- Score 0-1, store in `personas.validation_score`
- Re-extract personas scoring below 0.6

---

### Phase 3 — Intelligence Dashboard / Product 1 (Week 3-5)

**Step 3.1: FastAPI backend endpoints**

```
GET  /api/dashboard/pulse           → Real-time trending topics with sentiment and velocity
GET  /api/dashboard/debates         → Topics with highest disagreement scores
GET  /api/dashboard/leaders         → Top opinion leaders and their current stances
GET  /api/dashboard/research        → ArXiv trending papers and research signals
GET  /api/dashboard/funding         → Funding news with community reaction
GET  /api/dashboard/jobs            → Job market trends and signals
GET  /api/dashboard/github          → Builder activity signals (future source)
GET  /api/dashboard/news-impact     → News events with cross-platform reaction timeline
GET  /api/dashboard/geo             → Geographic distribution of community activity
GET  /api/dashboard/predictions     → Pattern-based prediction signals

GET  /api/topics                    → List all tracked topics with filters
GET  /api/topics/{id}               → Deep dive on a single topic
GET  /api/topics/{id}/timeline      → Sentiment trajectory over time
GET  /api/topics/{id}/camps         → Opinion camps and arguments

GET  /api/personas                  → List personas with filters (role, location, influence)
GET  /api/personas/{id}             → Individual persona detail
GET  /api/personas/{id}/posts       → All posts by this persona
GET  /api/personas/{id}/graph       → This persona's social connections

GET  /api/news                      → News feed with filters
GET  /api/news/{id}/reaction        → Community reaction to a news event

GET  /api/search?q=...              → Full-text search across all data

GET  /api/stats                     → Platform stats (total users, posts, topics, etc.)
```

**Step 3.2: Dashboard frontend**

Build 10 panels as described earlier:
1. Pulse — real-time sentiment feed across platforms
2. Hot debates — topics with highest disagreement
3. Opinion leaders — influential voices and their positions
4. Research radar — ArXiv trends and breakthroughs
5. Funding signals — startup funding with community reaction
6. Job market — workforce evolution trends
7. Builder activity — GitHub trending (future)
8. News impact — news events with reaction timeline
9. Geographic view — activity map by location
10. Prediction bridge — "Simulate this" button connecting to Product 2

**Step 3.3: Real-time updates**
- WebSocket endpoint for live dashboard updates
- When new scraper data comes in, push to connected dashboard clients
- Redis pub/sub for inter-service communication

---

### Phase 4 — Simulation Engine / Product 2 (Week 5-8)

**Step 4.1: Study OASIS and MiroFish codebases**
- Clone both repos
- Map out: how MiroFish seeds agents → OASIS agent format
- Identify the interface contract: what JSON/config does OASIS expect per agent
- Understand OASIS action space (23 actions: follow, comment, repost, etc.)
- Understand the recommendation system (interest-based, hot-score)

**Step 4.2: OASIS adapter**
- Build `oasis_adapter.py` that converts a `persona` row into OASIS agent config
- System prompt = persona.personality_summary + core beliefs + communication style instructions
- Long-term memory = user's actual post history (last 50 items)
- Social graph = connections from `community_graph` table
- Influence score → OASIS agent weight in recommendation system

**Step 4.3: Scenario builder**
- Build `scenario_builder.py` that creates simulation stimuli
- Input: a headline + context (manually created or auto-generated from news events)
- Output: OASIS-compatible initial post/event to inject
- Template scenarios: product launch, policy change, funding announcement, controversy, technology breakthrough

**Step 4.4: Simulation runner**
- Build `simulation_runner.py` that orchestrates a simulation run
- Select agents (by subreddit, influence, role, location)
- Load into OASIS with social graph
- Inject scenario
- Run N time steps (configurable, default 20 = ~20 simulated hours)
- Dual-platform simulation (Reddit-like + Twitter-like)
- Collect all agent actions, posts, replies, votes at each time step
- Store raw output in `simulation_results`

**Step 4.5: Report agent**
- Build `report_agent.py` that analyzes simulation output
- Generate: sentiment trajectory, opinion clusters, influencer pivots, viral content, risk score
- Write narrative summary using LLM
- Enable post-simulation agent dialogue (chat with any agent to understand their reasoning)

**Step 4.6: Simulation API**
```
POST /api/simulations              → Create and queue a new simulation
GET  /api/simulations              → List all simulations
GET  /api/simulations/{id}         → Simulation details and status
GET  /api/simulations/{id}/results → Full results with charts and narrative
POST /api/simulations/{id}/chat    → Chat with a specific agent post-simulation
```

---

## Dashboard Panels — Data Queries

### Panel 1: Pulse (real-time feed)
```sql
SELECT t.name, t.velocity, t.sentiment_distribution, t.platforms_active,
       t.total_mentions, t.status, t.updated_at
FROM topics t
WHERE t.status IN ('emerging', 'active', 'peaking')
  AND t.last_seen_at > NOW() - INTERVAL '7 days'
ORDER BY t.velocity DESC
LIMIT 20;
```

### Panel 2: Hot debates
```sql
SELECT t.name,
       t.opinion_camps,
       t.sentiment_distribution,
       t.total_mentions,
       ABS(
         (t.sentiment_distribution->>'positive')::float -
         (t.sentiment_distribution->>'negative')::float
       ) as polarization_score
FROM topics t
WHERE t.status IN ('active', 'peaking')
  AND t.total_mentions > 10
ORDER BY polarization_score ASC    -- Most divided first
LIMIT 10;
```

### Panel 3: Opinion leaders
```sql
SELECT u.username, u.platform_id, p.influence_score, p.inferred_role,
       p.personality_summary, p.core_beliefs, p.active_topics,
       p.inferred_location
FROM personas p
JOIN users u ON p.user_id = u.id
WHERE p.influence_score > 0.7
ORDER BY p.influence_score DESC
LIMIT 50;
```

### Panel 4: Research radar
```sql
SELECT title, body AS abstract, authors, published_at, categories,
       raw_metadata->>'arxiv_id' as arxiv_id, url
FROM news_events
WHERE source_type = 'arxiv'
  AND published_at > NOW() - INTERVAL '30 days'
ORDER BY published_at DESC
LIMIT 50;
```

### Panel 5: Funding signals
```sql
SELECT title, body, url, published_at, entities, sentiment, magnitude
FROM news_events
WHERE source_type = 'news'
  AND categories ? 'funding'
  AND published_at > NOW() - INTERVAL '30 days'
ORDER BY published_at DESC;
```

### Panel 6: Job market trends
```sql
SELECT
  raw_metadata->>'job_title' as job_title,
  raw_metadata->>'company' as company,
  raw_metadata->>'location' as location,
  raw_metadata->>'salary_min' as salary_min,
  raw_metadata->>'salary_max' as salary_max,
  published_at
FROM news_events
WHERE source_type = 'job_listing'
  AND published_at > NOW() - INTERVAL '7 days'
ORDER BY published_at DESC;

-- Trend aggregation
SELECT
  raw_metadata->>'job_title' as role_category,
  COUNT(*) as listing_count,
  DATE_TRUNC('week', published_at) as week
FROM news_events
WHERE source_type = 'job_listing'
  AND published_at > NOW() - INTERVAL '90 days'
GROUP BY role_category, week
ORDER BY week, listing_count DESC;
```

### Panel 9: Geographic view
```sql
SELECT p.inferred_location, COUNT(*) as user_count,
       AVG(p.influence_score) as avg_influence,
       ARRAY_AGG(DISTINCT unnest) as top_topics
FROM personas p,
     LATERAL unnest(ARRAY(SELECT jsonb_array_elements_text(p.active_topics))) as unnest
WHERE p.inferred_location IS NOT NULL
GROUP BY p.inferred_location
ORDER BY user_count DESC;
```

---

## LLM Cost Estimation (Monthly)

| Task | Model | Volume | Cost/unit | Monthly Cost |
|------|-------|--------|-----------|-------------|
| Persona extraction | GPT-4o-mini | 2,000 users × avg 2K tokens | ~$0.0003/1K tokens | ~$1.20 |
| Persona extraction (top users) | GPT-4o | 200 users × avg 5K tokens | ~$0.005/1K tokens | ~$5.00 |
| Sentiment analysis | GPT-4o-mini | 50,000 posts × avg 500 tokens | ~$0.0003/1K tokens | ~$7.50 |
| Topic detection | GPT-4o-mini | 1,000 batches × avg 2K tokens | ~$0.0003/1K tokens | ~$0.60 |
| News processing | GPT-4o-mini | 5,000 articles × avg 1K tokens | ~$0.0003/1K tokens | ~$1.50 |
| Simulation (per run) | GPT-4o-mini | 500 agents × 20 steps × 500 tokens | ~$0.0003/1K tokens | ~$1.50/run |
| **Total (without simulation)** | | | | **~$16/month** |
| **Per simulation run** | | | | **~$1.50/run** |

Very affordable for MVP. Scale costs increase linearly with agent count and simulation steps.

---

## Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mind_mirror
REDIS_URL=redis://localhost:6379

# Reddit (PRAW)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USERNAME=your_reddit_username
REDDIT_PASSWORD=your_reddit_password
REDDIT_USER_AGENT=CommunityMindMirror/1.0 by /u/your_username

# YouTube
YOUTUBE_API_KEY=your_youtube_api_key

# LLM (Azure OpenAI)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_DEPLOYMENT_GPT4O=gpt-4o
AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI=gpt-4o-mini

# Or Anthropic
ANTHROPIC_API_KEY=your_key

# Scraper settings
SCRAPE_DELAY_SECONDS=0.5
MAX_CONCURRENT_SCRAPERS=3
LOG_LEVEL=INFO
```

---

## Python Dependencies (requirements.txt)

```
# Web framework
fastapi==0.115.0
uvicorn==0.32.0
pydantic==2.10.0

# Database
sqlalchemy==2.0.36
asyncpg==0.30.0
alembic==1.14.0
psycopg2-binary==2.9.10

# Redis
redis==5.2.0

# Scrapers
praw==7.8.1              # Reddit
feedparser==6.0.11        # RSS feeds
google-api-python-client==2.155.0  # YouTube API
youtube-transcript-api==0.6.3      # YouTube transcripts
python-jobspy==1.1.75     # Job market scraping
requests==2.32.3          # HTTP (HN, ArXiv)
lxml==5.3.0               # XML parsing (ArXiv)

# LLM
openai==1.57.0            # Azure OpenAI
anthropic==0.39.0         # Claude API

# NLP / Analysis
networkx==3.4.2           # Graph analysis
scikit-learn==1.5.2       # Clustering, embeddings
numpy==2.1.3

# Scheduling
apscheduler==3.10.4

# Utilities
python-dotenv==1.0.1
httpx==0.28.0
tenacity==9.0.0           # Retry logic
structlog==24.4.0         # Structured logging
```

---

## Docker Compose

```yaml
version: '3.8'

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: mind_mirror
      POSTGRES_USER: mmuser
      POSTGRES_PASSWORD: mmpass
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  app:
    build: .
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis
    volumes:
      - .:/app

volumes:
  pgdata:
```

---

## Claude Code Instruction Sets

### Instruction Set 1: Phase 1 Kickoff

```
Read through this project plan at /path/to/community-mind-mirror-plan.md

Your task is to set up the project foundation:
1. Create the project directory structure as specified
2. Set up the PostgreSQL database schema (all tables)
3. Create the base scraper class with common patterns
4. Build the Reddit scraper (Step 1.2)
5. Build the Hacker News scraper (Step 1.3)
6. Test both scrapers with a small sample (1 subreddit, 10 HN stories)

Use the exact table schemas from the plan. Use async SQLAlchemy for database operations.
Follow the config/sources.py configuration structure.
Make scrapers resumable — if they crash, they should pick up where they left off.
Log all scraper runs to the scraper_runs table.
```

### Instruction Set 2: Remaining Scrapers

```
Continue building the data pipeline. The project structure and database are set up.
Now build:
1. YouTube scraper (Step 1.4)
2. News RSS scraper (Step 1.5)
3. ArXiv scraper (Step 1.6)
4. Job market scraper (Step 1.7)
5. Cron scheduler that runs all scrapers on their configured intervals

Test each scraper independently before integrating into the scheduler.
```

### Instruction Set 3: LLM Processing

```
Build the LLM processing layer:
1. Persona extractor — takes user posts, calls LLM, writes to personas table
2. Sentiment analyzer — processes posts in bulk
3. Topic detector — clusters posts into topics, tracks velocity
4. Graph builder — constructs community_graph from interactions
5. News processor — structures news events with entity extraction

Use the prompt templates from the plan. Support both Azure OpenAI and Anthropic.
Process in batches to manage API costs. Add cost tracking.
```

---

## Success Metrics

### Data Pipeline Health
- 6 scrapers running on schedule with <5% failure rate
- 2,000+ unique user profiles across Reddit + HN + YouTube
- 500+ personas extracted with >0.6 validation score
- 5,000+ news events in database
- Community graph with 10,000+ edges

### Dashboard (Product 1)
- 10 panels rendering real data
- <2 second page load time
- Real-time updates via WebSocket
- Search working across all data

### Simulation (Product 2)
- Can run a 500-agent simulation in <30 minutes
- Simulation produces all 7 output types (sentiment trajectory, clusters, influencer pivots, viral content, risk score, narrative, agent dialogue)
- Per-simulation cost <$2

---

## Future Data Sources (Post-MVP)

After validating with the 6 MVP sources, expand to:
- Twitter/X (API or Nitter)
- LinkedIn (Proxycurl or scraping)
- Product Hunt (GraphQL API)
- Stack Overflow (free API)
- Discord (bot in AI servers)
- Mastodon/Bluesky (open APIs)
- GitHub Trending (scraping)
- Crunchbase (Pro plan for funding data)
- Patent data (USPTO API)
- Regulatory data (Federal Register API)
