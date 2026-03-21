# Community Mind Mirror

Community intelligence platform that scrapes AI/tech communities, builds persona profiles, and powers a real-time dashboard + simulation engine.

## Quick Start

### 1. Start infrastructure

```bash
docker-compose up -d
```

This starts PostgreSQL 16 and Redis 7.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings (defaults work for local Docker setup)
```

### 4. Initialize database

```bash
python init_db.py
```

Creates all tables and seeds the platforms table.

### 5. Test scrapers

```bash
python run_scrapers.py
```

Runs Reddit scraper on r/artificial and HN scraper on 10 top stories.

## Project Structure

```
community-mind-mirror/
├── config/
│   ├── settings.py          # Environment variables and config
│   └── sources.py           # Target subreddits, channels, feeds
├── scrapers/
│   ├── base_scraper.py      # Abstract base class
│   ├── reddit_scraper.py    # Reddit RSS scraper (no API key)
│   └── hn_scraper.py        # Hacker News Firebase + Algolia
├── processors/              # LLM processing (Phase 2)
├── simulation/              # OASIS simulation (Phase 2)
├── api/                     # FastAPI endpoints (Phase 3)
├── database/
│   └── connection.py        # SQLAlchemy async models
├── init_db.py               # Database initialization
├── run_scrapers.py          # Test runner
├── docker-compose.yml       # PostgreSQL + Redis
└── requirements.txt
```

## Data Sources

| Source | Method | API Key? | Rate Limit |
|--------|--------|----------|------------|
| Reddit | RSS feeds (.rss) | No | ~1 req/5s |
| Hacker News | Firebase API + Algolia | No | None (be polite) |
| YouTube | Data API v3 | Yes | 10K units/day |
| News RSS | feedparser | No | None |
| ArXiv | REST API | No | 1 req/3s |
| Job Market | JobSpy library | No | Varies |
