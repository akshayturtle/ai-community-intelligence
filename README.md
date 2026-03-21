# AI Community Intelligence

**Open-source community intelligence platform that monitors 25+ AI/tech data sources, processes signals through LLM-powered agents, and surfaces actionable market intelligence — from trending topics and product traction to talent gaps and billion-dollar market opportunities.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![React 19](https://img.shields.io/badge/React-19-61dafb.svg)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com)

### Dashboard Overview — Trending topics, cross-source highlights, hype vs reality
![Dashboard Overview](screenshots/dashboard-overview.png)

### Pain Points & Job Market Intelligence
![Pain Points & Jobs](screenshots/dashboard-painpoints-jobs.png)

### Cross-Source Signals — Traction, market gaps, threats, talent flow
![Signals](screenshots/signals-overview.png)

### AI Gig Board — 2,600+ freelance & hiring opportunities
![Gig Board](screenshots/gig-board.png)

### Competitive Intelligence — Product landscape, migrations, reviews
![Product Intelligence](screenshots/intelligence-products.png)

<details>
<summary><b>View all screenshots (24 total)</b></summary>

#### Topics — Trending discussions with velocity & sentiment
![Topics](screenshots/topics.png)

#### Topic Deep Dive — Sentiment timeline, opinion camps, platform breakdown
![Topic Detail](screenshots/topic-detail.png)

#### Persona Profile — Core beliefs, communication style, expertise
![Persona Detail](screenshots/persona-detail.png)

#### Product Reviews — Pros, cons, use cases, competitor comparisons from Reddit
![Product Reviews](screenshots/intelligence-product-reviews.png)

#### Migration Patterns — What users switch FROM → TO
![Migrations](screenshots/intelligence-migrations.png)

#### Unmet Needs — Community frustrations with no solution
![Unmet Needs](screenshots/intelligence-unmet-needs.png)

#### Job Market — Salary insights, top hiring companies, geographic distribution
![Job Market](screenshots/intelligence-job-market.png)
![Job Market Skills & Culture](screenshots/intelligence-job-market-3.png)

#### Traction Scoring — Anti-hype, unfakeable signals only
![Traction](screenshots/signals-traction.png)

#### Technology Lifecycle — Research → Experimentation → Adoption → Growth → Mainstream
![Lifecycle](screenshots/signals-lifecycle.png)

#### Market Gap Detection — High pain + zero solutions = startup opportunity
![Market Gaps](screenshots/signals-market-gaps.png)

#### Competitive Threats — Migration patterns, GitHub velocity, hiring signals
![Competitive Threats](screenshots/signals-competitive-threats.png)

#### Platform Divergence — When Reddit disagrees with HN (early warning signal)
![Divergence](screenshots/signals-divergence.png)

#### Smart Money Tracker — Where YC, VCs, and builders converge
![Smart Money](screenshots/signals-smart-money.png)

#### Talent Flow — Skill supply vs demand with salary pressure
![Talent Flow](screenshots/signals-talent-flow.png)

#### Narrative Shifts — When the dominant story about a topic changes
![Narratives](screenshots/signals-narratives.png)

#### News & Intelligence — RSS feeds with entity extraction and sentiment
![News](screenshots/news.png)

#### System Monitor — Agent status, scraper health, performance
![System](screenshots/system-monitor.png)

</details>

---

## Why Community Mind Mirror?

Every day, thousands of developers, founders, and investors share unfiltered opinions across Reddit, Hacker News, GitHub, ArXiv, YouTube, and job boards. **This raw signal is more honest than any market report** — but it's scattered across 25+ platforms and impossible to track manually.

Community Mind Mirror **automates the entire intelligence pipeline**: scraping, processing, cross-referencing, and presenting insights that would take a research team weeks to compile.

---

## Who Is This For?

### For VCs & Investors
- **Smart Money Tracking** — See where YC, VC funding, and builder activity converge on emerging sectors
- **Traction Scoring** — Cut through hype with unfakeable signals (GitHub velocity, package downloads, organic mentions, job listings)
- **Market Gap Detection** — Find billion-dollar opportunities where high pain meets zero solutions
- **Research Pipeline** — Track papers from ArXiv to GitHub to production adoption (days-to-commercialization)

### For Founders & Startup Teams
- **Competitive Threat Analysis** — Know when users are migrating away from competitors (or from you)
- **Pain Point Discovery** — Find what developers are frustrated about — each pain point is a potential product
- **Product Reviews** — Deep community sentiment analysis for any YC/ProductHunt product from Reddit discussions
- **Narrative Shift Detection** — Catch when the community story about your space is changing

### For Product Managers & Analysts
- **Technology Lifecycle Mapping** — Know if a technology is in research, experimentation, early adoption, growth, or mainstream
- **Platform Divergence** — Detect when Reddit builders disagree with HN engineers — early warning for market corrections
- **Hype vs Reality Index** — Quantified gap between press/VC excitement and builder sentiment per sector
- **Opinion Leader Tracking** — 3,400+ profiled community leaders with stance tracking and shift detection

### For Recruiters & HR Teams
- **Gig Board** — 1,400+ AI/ML freelance and hiring opportunities extracted from 21 subreddits using LLM classification
- **Talent Flow Prediction** — Skill supply-demand gaps with salary pressure indicators
- **Job Intelligence** — Salary trends, hiring patterns, and tech stack demand from 10+ job boards and 57 ATS company feeds
- **Skill Gap Analysis** — Which skills are in demand vs oversupply, and where salaries are under pressure

### For Financial Advisors
- **Funding Round Tracking** — Company funding with community reaction sentiment (are builders excited or skeptical?)
- **Sector Classification** — Hot, emerging, or quiet sectors based on multi-signal convergence
- **Technology Adoption Curves** — Data-driven lifecycle stage for every tracked technology

---

## Intelligence Capabilities

### 1. Data Collection — 25 Sources, 200K+ Records

| Category | Sources | What We Collect |
|---|---|---|
| **Communities** | Reddit (55 subs), Hacker News, YouTube (29 channels) | Posts, comments, transcripts, upvotes, sentiment |
| **Code & Research** | GitHub (675+ repos), ArXiv (7 categories), HuggingFace, Papers with Code | Stars, forks, velocity, papers, models, downloads |
| **Job Market** | RemoteOK, Remotive, Himalayas, TheMuse, Arbeitnow, USAJobs, HN Hiring | Listings, salaries, skills, companies, locations |
| **ATS Feeds** | 57 companies via Greenhouse/Lever/Ashby (OpenAI, Anthropic, Figma, Notion, Vercel, Databricks...) | Structured job data with role/salary/tech stack |
| **Ecosystem** | ProductHunt, Y Combinator (W25), Stack Overflow (14 tags), PyPI (16 packages), npm (6 packages) | Launches, companies, Q&A trends, download velocity |
| **News** | TechCrunch, The Verge, VentureBeat, MIT Tech Review, Google News + 8 more | Articles, entities, funding announcements |

### 2. Analysis Pipeline — 3-Layer Processing

**Layer 1 — Pattern Matching (No LLM)**
- VADER sentiment scoring on every post
- Regex-based product mention detection (18 seed products + dynamic discovery)
- Migration pattern extraction ("switched from X to Y", "replaced X with Y")
- Complaint clustering by 50+ keyword categories

**Layer 2 — Statistical Analysis**
- Topic velocity calculation (24h mentions vs 6-day average)
- Hype vs Reality Index (builder sentiment vs press/VC sentiment per sector)
- Influence scoring: `(karma × 0.4) + (post_volume × 0.3) + (avg_score × 0.3)`
- Platform divergence scoring (cross-platform sentiment disagreement)

**Layer 3 — LLM-Powered Deep Analysis**
- **Topic Extraction** — 5-10 distinct topics per batch with opinion camps and stance distribution
- **Persona Profiling** — Core beliefs, communication style, expertise domains, influence type for 3,400+ community leaders
- **Pain Point Synthesis** — Clustered frustrations with intensity scores, solution availability, and affected products
- **Funding Reaction Analysis** — Community sentiment within ±7 days of funding news
- **Leader Shift Detection** — When opinion leaders change their stance on a topic (what shifted, why)
- **Gig Classification** — LLM classifies every post as gig/not-gig with structured extraction (title, skills, pay, tech stack, apply method)
- **Job Intelligence** — Structured extraction: role category, seniority, salary (normalized to annual USD), tech stack, company stage, culture signals
- **Product Review Synthesis** — Deep analysis of Reddit discussions per product (pros, cons, use cases, churn reasons, competitor comparisons)

### 3. Cross-Source Signal Agents — 10 Intelligence Agents

These agents combine signals from community, technical, market, and hiring data to produce intelligence that no single source can provide:

| Agent | What It Detects | Key Metric |
|---|---|---|
| **Traction Scorer** | Real product traction (anti-hype) | Weighted score: GitHub stars/velocity (30%), downloads (20%), organic mentions (15%), jobs (10%), recommendation rate (10%) |
| **Market Gap Detector** | Unmet needs with no solution | `pain_score × (1 / existing_products) × (1 + job_postings/100)` |
| **Competitive Threat** | Emerging competitors | Migration patterns + GitHub velocity + hiring + sentiment |
| **Platform Divergence** | When platforms disagree | `(max_sentiment - min_sentiment) × 100` across Reddit/HN/YouTube/PH |
| **Technology Lifecycle** | Adoption stage mapping | Research → Experimentation → Early Adoption → Growth → Mainstream → Commodity |
| **Narrative Shift** | Changing community stories | Older frame vs recent frame comparison with shift velocity |
| **Smart Money Tracker** | Where capital is flowing | YC batch % + VC articles + builder repos + community volume |
| **Talent Flow** | Skill supply-demand gaps | Demand score vs supply score with salary pressure indicator |
| **Research Pipeline** | Paper-to-product tracking | Days from ArXiv → GitHub → HuggingFace → Community → ProductHunt → Jobs |
| **Divergence Detector** | Early warning signals | Status: correction_expected / genuine_adoption / hype_bubble / early_signal |

### 4. Real-Time Dashboard — 14 Views

- **Overview** — Key metrics, trending topics, top leaders, latest news, scraper health
- **Signals** — All agent outputs: traction scores, market gaps, threats, lifecycle, divergence
- **Intelligence** — Product landscape, migration flows, pain points, hype index
- **Topics** — Trending discussion topics with velocity, sentiment, opinion camps
- **People** — Opinion leader profiles with core beliefs, expertise, influence scores
- **Gig Board** — AI/ML freelance and hiring opportunities with filters
- **Research** — Paper-to-product pipeline tracking
- **News** — News feed with entity extraction and community reaction
- **Geographic** — User/job/company distribution
- **System** — Scraper runs, agent logs, performance monitoring
- **WebSocket** — Real-time updates for topic velocity, agent completions, scraper status

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA SOURCES (25)                        │
│  Reddit · HN · GitHub · ArXiv · YouTube · ProductHunt       │
│  YC · StackOverflow · PyPI · npm · HuggingFace · News       │
│  RemoteOK · Remotive · Himalayas · TheMuse · Arbeitnow      │
│  USAJobs · Greenhouse · Lever · Ashby · HN Hiring           │
│  Papers with Code · Product Reddit Search                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   SCRAPERS (async Python)                     │
│  BaseScraper → upsert_user() + upsert_post()                │
│  Deduplication via platform_id unique constraint             │
│  Rate limiting · Retry logic · JSONB raw_metadata            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL (45 tables)                     │
│  posts · users · topics · personas · products · migrations   │
│  pain_points · hype_index · funding_rounds · gig_posts       │
│  job_intelligence · traction_scores · market_gaps · ...      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              PROCESSORS (13 analysis engines)                 │
│  Sentiment (VADER) · Topics (LLM) · Personas (LLM)          │
│  Products · Migrations · Pain Points · Hype Index            │
│  Funding · Leader Shifts · Platform Tones · Gigs (LLM)      │
│  Job Intelligence (LLM) · Product Reviews (LLM)             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│            SIGNAL AGENTS (10 cross-source agents)            │
│  Traction · Market Gaps · Competitive Threats · Divergence   │
│  Technology Lifecycle · Narrative Shifts · Smart Money        │
│  Talent Flow · Research Pipeline · Product Discovery         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 API (FastAPI + WebSocket)                     │
│  50+ endpoints · Pagination · Real-time updates              │
│  Background tasks · Full-text search                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              DASHBOARD (React 19 + TypeScript)               │
│  14 pages · TanStack React Query · Tailwind CSS              │
│  Real-time WebSocket · Responsive design                     │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy (async), Agno framework |
| **Database** | PostgreSQL 14+ (45 tables, JSONB columns), Redis |
| **LLM** | OpenAI-compatible API (Azure OpenAI / OpenAI / any compatible endpoint) |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS, TanStack React Query |
| **Deployment** | PM2, Nginx, systemd |
| **Cost Tracking** | Built-in LLM spending tracker with budget caps |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+
- An OpenAI-compatible API key

### 1. Clone & Configure

```bash
git clone https://github.com/akshayturtle/ai-community-intelligence.git
cd community-mind-mirror/community-mind-mirror

# Copy the example env file and fill in your keys
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Required — PostgreSQL (must use asyncpg driver)
DATABASE_URL=postgresql+asyncpg://cmm:cmm@localhost:5432/cmm

# Required — LLM API (Azure OpenAI or any OpenAI-compatible endpoint)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o            # For deep analysis
AZURE_OPENAI_DEPLOYMENT_MINI=gpt-4o-mini  # For bulk processing (cheaper)

# Optional — Enables additional scrapers
GITHUB_TOKEN=ghp_...                      # Higher GitHub API rate limits
YOUTUBE_API_KEY=AIza...                   # YouTube Data API v3
PH_ACCESS_TOKEN=...                       # ProductHunt API
SO_API_KEY=...                            # Stack Overflow API

# Optional — Pipeline email notifications
RESEND_API_KEY=re_...
NOTIFY_EMAIL=you@example.com
```

> **Note:** Most scrapers (Reddit, HN, ArXiv, all job boards, PyPI, npm, HuggingFace, Papers with Code) work without any API keys. You only need the LLM API key + database to get started.

### 2. Start Database & Redis

```bash
# Using Docker (recommended)
docker-compose up -d

# This starts:
#   PostgreSQL 16 on port 5432 (user: cmm, password: cmm, db: cmm)
#   Redis 7 on port 6379
```

Or use an existing PostgreSQL instance — just update `DATABASE_URL` in `.env`.

### 3. Install Dependencies & Initialize

```bash
# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Create all 45 database tables and seed platform registry
python init_db.py
```

### 4. Start the API Server

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Verify it's running: `curl http://localhost:8000/api/health`

### 5. Start the Frontend Dashboard

```bash
cd dashboard
npm install

# Set API URL for local development
echo "VITE_API_URL=http://localhost:8000/api" > .env

npm run dev
# Dashboard opens at http://localhost:5173
```

### 6. Run the Intelligence Pipeline

```bash
# Go back to the project root
cd ..

# Option A: Full pipeline (scrape → process → run agents)
python run_scrapers_bg.py

# Option B: Continuous mode — runs every 6 hours
python run_scrapers_bg.py --loop

# Option C: Skip scraping, just run analysis on existing data
python run_scrapers_bg.py --analyze-only
```

---

## Running Individual Components

### Scrapers

Run a single scraper to collect data from one source:

```bash
python main.py --scraper reddit           # Reddit (55 subreddits via RSS)
python main.py --scraper hackernews       # Hacker News (Firebase/Algolia API)
python main.py --scraper github           # GitHub repos + search
python main.py --scraper arxiv            # ArXiv papers (7 CS categories)
python main.py --scraper youtube          # YouTube (29 channels)
python main.py --scraper producthunt      # ProductHunt launches
python main.py --scraper yc              # Y Combinator companies
python main.py --scraper stackoverflow    # Stack Overflow (14 tags)
python main.py --scraper huggingface      # HuggingFace models
python main.py --scraper packages         # PyPI + npm download tracking
python main.py --scraper paperswithcode   # Papers with Code
python main.py --scraper news             # News RSS feeds (13 sources)
python main.py --scraper jobs             # All job board scrapers
python main.py --scraper hn_hiring        # HN "Who is hiring?" threads
```

### Processors

Run individual analysis processors on scraped data:

```bash
python main.py --processor sentiment      # VADER sentiment (no LLM, fast)
python main.py --processor topics         # LLM topic extraction
python main.py --processor personas       # User personality profiling (LLM)
python main.py --processor products       # Product discovery + mentions
python main.py --processor migrations     # Product switch detection
python main.py --processor pain_points    # Community frustration extraction
python main.py --processor hype           # Hype vs Reality Index
python main.py --processor funding        # Funding + community reaction
python main.py --processor leader_shifts  # Opinion leader stance changes
python main.py --processor gigs           # Gig/hiring classification (LLM)
python main.py --processor job_intel      # Structured job extraction (LLM)
python main.py --processor product_reviews # Product sentiment synthesis
```

### Signal Agents

Run cross-source intelligence agents (these combine data from multiple tables):

```bash
python main.py --agent traction           # Product traction scoring
python main.py --agent market_gaps        # Market opportunity detection
python main.py --agent competitive        # Competitive threat analysis
python main.py --agent divergence         # Platform disagreement detection
python main.py --agent lifecycle          # Technology adoption mapping
python main.py --agent narrative          # Narrative shift detection
python main.py --agent smart_money        # VC + builder signal tracking
python main.py --agent talent_flow        # Skill supply-demand gaps
python main.py --agent research_pipeline  # Paper-to-product tracking
python main.py --agent product_discovery  # Emerging product detection
```

### Database Stats

```bash
# Print record counts for all 45 tables
python main.py --summary
```

---

## Production Deployment

### 1. Build the Frontend

```bash
cd dashboard

# Set API URL to use nginx proxy
echo "VITE_API_URL=/api" > .env

npm run build
# Output: dashboard/dist/ (static files)
```

### 2. Start the API with PM2

```bash
cd ..  # Back to project root

# Install PM2 globally
npm install -g pm2

# Start API server
pm2 start "uvicorn api.main:app --host 127.0.0.1 --port 8000" --name cmm-api

# Start continuous pipeline (optional)
pm2 start "python run_scrapers_bg.py --loop" --name cmm-pipeline

# Save PM2 config for auto-restart on reboot
pm2 save
pm2 startup
```

### 3. Configure Nginx

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Serve React frontend
    root /path/to/community-mind-mirror/dashboard/dist;
    index index.html;

    # Proxy API requests to FastAPI
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }

    # WebSocket support
    location /api/ws/ {
        proxy_pass http://127.0.0.1:8000/api/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # API docs (optional)
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # SPA fallback — serve index.html for all frontend routes
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```bash
# Enable site and restart nginx
sudo ln -s /etc/nginx/sites-available/cmm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Set Up SSL (Optional but Recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Troubleshooting

### Common Issues

**Database connection errors**
```
sqlalchemy.exc.OperationalError: could not connect to server
```
- Make sure PostgreSQL is running: `docker-compose ps`
- Check `DATABASE_URL` in `.env` — must use `postgresql+asyncpg://` prefix
- Verify the database exists: `docker exec -it cmm-postgres psql -U cmm -c '\l'`

**LLM API errors**
```
openai.AuthenticationError: Incorrect API key
```
- Check `AZURE_OPENAI_API_KEY` in `.env`
- For Azure OpenAI, ensure `AZURE_OPENAI_ENDPOINT` includes the full URL with trailing `/`
- For standard OpenAI, set `OPENAI_API_KEY` instead

**Frontend shows "no data"**
- Verify the API is running: `curl http://localhost:8000/api/health`
- Check `VITE_API_URL` in `dashboard/.env`
- For production: ensure nginx is proxying `/api/` correctly
- Rebuild frontend after changing env: `npm run build`

**Reddit scraper returns 0 posts**
- Reddit RSS feeds may rate-limit. The scraper includes automatic retry logic.
- Check if Reddit is blocking your IP (try from a different network)
- Posts are deduplicated — if you ran the scraper before, duplicate posts are skipped

**Processor returns 0 results**
- Run scrapers first to populate the `posts` table
- Check that posts have `body` content (some RSS feeds only return titles)
- Run `python main.py --summary` to see current record counts

**Budget exceeded**
```
Spending limit reached
```
- The built-in spending tracker pauses processing when daily budget is hit
- Adjust limits in `spending_tracker.py`
- Check current spending: tracked per processor/agent run

---

## Data Sources — 25 Integrations

### Community Platforms
| Source | Method | Data Collected | Auth Required |
|---|---|---|---|
| **Reddit** (55 subreddits) | RSS feeds | Posts, comments, votes, subreddit | No |
| **Hacker News** | Firebase/Algolia API | Stories, comments, karma, user data | No |
| **YouTube** (29 channels) | Data API v3 | Videos, comments, transcripts, views | API key |

### Code & Research
| Source | Method | Data Collected | Auth Required |
|---|---|---|---|
| **GitHub** (675+ repos) | REST API | Stars, forks, velocity, contributors, language | Token (optional) |
| **ArXiv** (7 CS categories) | OAI-PMH | Papers, abstracts, authors, categories | No |
| **HuggingFace** | API | Models, downloads, likes, pipeline tags | No |
| **Papers with Code** | API | Papers, methods, trending research | No |
| **Stack Overflow** (14 tags) | API | Questions, views, answers, scores | API key (optional) |
| **PyPI** (16 packages) | API | Daily download counts | No |
| **npm** (6 packages) | API | Weekly download counts | No |

### Startup Ecosystem
| Source | Method | Data Collected | Auth Required |
|---|---|---|---|
| **Y Combinator** | Web scraping | Companies, batches, industries, team size | No |
| **ProductHunt** | API | Launches, votes, comments, makers | Access token |

### Job Market (10+ sources)
| Source | Method | Data Collected | Auth Required |
|---|---|---|---|
| **57 companies** (Greenhouse/Lever/Ashby) | ATS APIs | Structured job listings | No |
| **RemoteOK** | API | Remote jobs, salary, tags | No |
| **Remotive** | API | Remote jobs across 6 categories | No |
| **Himalayas** | API | Remote jobs | No |
| **TheMuse** | API | Engineering, data, IT roles | No |
| **Arbeitnow** | API | Global job listings | No |
| **USAJobs** | API | Federal AI/ML/cyber roles | No |
| **HN Who's Hiring** | Algolia API | Monthly hiring threads | No |

### News & Media
| Source | Method | Data Collected | Auth Required |
|---|---|---|---|
| **13 RSS feeds** (TechCrunch, The Verge, VentureBeat, MIT Tech Review, Wired, Google News...) | RSS | Articles, entities, sentiment | No |

---

## Project Structure

```
community-mind-mirror/
├── agents/                      # Cross-source signal agents
│   ├── orchestrator.py          # Agent runner & scheduler
│   └── signal_agents/           # 10 intelligence agents
│       ├── traction_scorer.py
│       ├── market_gap_detector.py
│       ├── competitive_threat.py
│       ├── divergence_detector.py
│       ├── lifecycle_mapper.py
│       ├── narrative_shift.py
│       ├── smart_money_tracker.py
│       ├── talent_flow.py
│       ├── research_pipeline.py
│       └── product_discoverer.py
├── api/                         # FastAPI backend (50+ endpoints)
│   ├── main.py
│   ├── models/schemas.py        # Pydantic models
│   └── routes/                  # 13 route modules
├── dashboard/                   # React 19 frontend
│   └── src/
│       ├── api/                 # API client + React Query hooks
│       ├── components/          # Reusable UI components
│       └── pages/               # 14 page views
├── database/
│   └── connection.py            # 45 SQLAlchemy models
├── processors/                  # 13 analysis engines
│   ├── sentiment_analyzer.py    # VADER sentiment (no LLM)
│   ├── topic_detector.py        # LLM topic extraction
│   ├── persona_extractor.py     # User profiling
│   ├── product_processor.py     # Product discovery
│   ├── migration_processor.py   # Product switch detection
│   ├── pain_point_processor.py  # Frustration extraction
│   ├── hype_processor.py        # Hype vs Reality Index
│   ├── funding_processor.py     # Funding + community reaction
│   ├── gig_post_processor.py    # Gig/hiring classification
│   ├── job_intelligence_processor.py  # Structured job extraction
│   ├── product_review_processor.py    # Product sentiment synthesis
│   └── llm_client.py           # OpenAI-compatible LLM client
├── scrapers/                    # 25 data source scrapers
│   ├── base_scraper.py          # Base class with upsert/rate-limit
│   ├── reddit_scraper.py        # 55 subreddits + gig subs
│   ├── hn_scraper.py            # Hacker News
│   ├── github_scraper.py        # GitHub repos + search
│   ├── arxiv_scraper.py         # ArXiv papers
│   └── ...                      # 20+ more scrapers
├── config/                      # Source lists, settings
│   ├── settings.py
│   └── sources.py               # Subreddits, channels, repos, etc.
├── run_scrapers_bg.py           # Pipeline runner (scrape → process → agents → email)
├── spending_tracker.py          # LLM cost tracking with budget caps
├── docker-compose.yml           # PostgreSQL + Redis
└── requirements.txt
```

---

## Use Cases

### Market Research Report Generation
Run the full pipeline and get a structured intelligence report covering:
- What technologies are gaining/losing traction
- Where the talent market is heading
- Which sectors have unfilled market gaps
- What community leaders are saying about emerging trends

### Competitive Intelligence
Track any product or technology and get:
- Real-time sentiment from builders (not press releases)
- Migration patterns (who's switching to/from what)
- Competitive threat scores based on unfakeable signals
- Community pain points your product could solve

### Due Diligence for Investments
Before investing, check:
- Traction score (are people actually using it, or just talking about it?)
- Hype vs Reality gap for the sector
- Community reaction to funding rounds
- Technology lifecycle stage (too early? already commoditized?)

### Talent Strategy
For hiring teams:
- Which skills are in shortage vs oversupply
- Salary pressure indicators by skill
- Geographic distribution of talent
- Where companies are hiring aggressively (from ATS feeds of 57 companies including OpenAI, Anthropic, Figma, Notion)

### Product Development
For product teams:
- What are developers complaining about? (pain points = features)
- Which integrations are most requested?
- How does community sentiment differ across platforms?
- What are the top feature requests for competing products?

---

## Environment Variables

See `.env.example` for the full list. Most scrapers work without API keys (Reddit, HN, ArXiv, GitHub, job boards use public endpoints).

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection (asyncpg driver) |
| `AZURE_OPENAI_API_KEY` | Yes | OpenAI-compatible API key for LLM analysis |
| `AZURE_OPENAI_ENDPOINT` | Yes | API endpoint URL |
| `GITHUB_TOKEN` | No | Higher GitHub API rate limits |
| `YOUTUBE_API_KEY` | No | YouTube Data API v3 |
| `PH_ACCESS_TOKEN` | No | ProductHunt API |
| `SO_API_KEY` | No | Stack Overflow API |
| `RESEND_API_KEY` | No | Pipeline email notifications |

---

## Legal & Compliance

### Data Collection Practices

Community Mind Mirror collects **publicly available data** from public APIs, RSS feeds, and open web endpoints. The platform:

- **Respects `robots.txt`** — All scrapers honor robots.txt directives
- **Uses official APIs** — GitHub, YouTube, ProductHunt, StackOverflow, HuggingFace, and job boards are accessed through their official public APIs
- **Uses public RSS feeds** — Reddit and news sources are accessed via their public RSS endpoints
- **Implements rate limiting** — All scrapers include configurable delays between requests to avoid overloading source servers
- **Does not bypass authentication** — No login credentials are used or stored for scraping; only publicly accessible content is collected
- **Does not scrape private content** — Only publicly posted content (public subreddits, public repositories, public job listings) is collected

### Data Usage & Privacy

- **No personal data collection** — The platform tracks public usernames and public posting activity only. No emails, passwords, real names, or private messages are collected.
- **Persona analysis** — User profiles are built from publicly posted content only. No private data is inferred or stored beyond what users have publicly shared.
- **Aggregation focus** — The primary purpose is aggregate intelligence (trends, sentiment, market signals), not individual user tracking.
- **Right to erasure** — Users can request removal of their data by opening an issue.

### Third-Party API Terms

Users of this software are responsible for:
- Complying with the terms of service of each data source they enable
- Obtaining necessary API keys and adhering to rate limits
- Ensuring their use case complies with applicable data protection regulations (GDPR, CCPA, etc.)

### Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND. THE AUTHORS ARE NOT RESPONSIBLE FOR HOW THIS SOFTWARE IS USED. Users are solely responsible for ensuring their use of this software complies with all applicable laws, regulations, and third-party terms of service. This software is intended for market research, competitive intelligence, and academic purposes using publicly available data.

---

## Cost Management

The platform includes a built-in **spending tracker** that monitors LLM API costs in real-time:

- Per-call token tracking with cost calculation
- Configurable daily/monthly budget caps
- Pipeline automatically pauses when budget is exceeded
- Email notifications for budget alerts
- Cost breakdown per processor and agent

Typical costs for a full pipeline run: **~$0.50-2.00** (using gpt-4o-mini for most analysis).

---

## Contributing

Contributions are welcome! Whether it's adding new data sources, improving analysis agents, or enhancing the dashboard.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-scraper`)
3. Commit your changes
4. Push and open a Pull Request

### Adding a New Scraper

```python
from scrapers.base_scraper import BaseScraper

class MyNewScraper(BaseScraper):
    async def scrape(self):
        data = await self.fetch_url("https://api.example.com/data")
        for item in data:
            user = await self.upsert_user(platform_name="example", ...)
            await self.upsert_post(user_id=user.id, ...)
            await self.rate_limit()  # Respect rate limits
```

### Adding a New Signal Agent

Agents pre-compute data in Python, then send to LLM for cross-source analysis. See `agents/signal_agents/traction_scorer.py` for the pattern.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Built By

**[Turtle Techsai](https://turtletechsai.com)** — Building AI-powered intelligence tools.

For custom deployments, enterprise features, or consulting inquiries: **akshay.gupta@turtletechsai.com**
