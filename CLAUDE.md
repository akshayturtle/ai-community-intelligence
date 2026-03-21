# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Community Mind Mirror** — a full-stack community intelligence platform that scrapes AI/tech communities (Reddit, HN, GitHub, ArXiv, job boards, etc.), processes data through LLM-powered agents, and presents insights via a React dashboard.

## Commands

### Backend (Python) — run from `community-mind-mirror/`
```bash
docker-compose up -d                                    # Start PostgreSQL 16 + Redis 7
pip install -r requirements.txt                         # Install Python deps
python init_db.py                                       # Create tables, seed platforms
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000  # Start API server
python run_scrapers_bg.py                               # Run scraper→processor pipeline once
python run_scrapers_bg.py --loop                        # Continuous pipeline
python main.py --scraper reddit                         # Run a single scraper
python main.py --processor sentiment                    # Run a single processor
python main.py --summary                                # Print DB stats
```

### Frontend (React) — run from `community-mind-mirror/dashboard/`
```bash
npm install
npm run dev          # Vite dev server on :5173
npm run build        # tsc -b && vite build
npm run lint         # ESLint
```

### Deployment
Uses PM2 for process management (`cmm-api` running uvicorn on :8000). Nginx serves frontend static files and proxies `/api/` to the backend.

## Architecture

```
Scrapers (25 sources) → PostgreSQL (posts, users) → Processors (LLM analysis) → Signal Agents (cross-source) → API (FastAPI) → Dashboard (React)
```

### Data Pipeline
1. **Scrapers** (`scrapers/`) — Async HTTP via `BaseScraper`. Reddit uses RSS (no API key), HN uses Firebase/Algolia. All write to unified `posts` + `users` tables.
2. **Processors** (`processors/`) — Batch-process posts: sentiment (VADER), topics (LLM), personas, product discovery, pain points, hype index, gig extraction, research analysis. Use `processors/llm_client.py` for OpenAI-compatible API calls.
3. **Signal Agents** (`agents/signal_agents/`) — 9 Agno-framework agents that pre-fetch data in Python then pass to LLM for cross-source pattern analysis (market gaps, competitive threats, talent flow, etc.). Orchestrated by `agents/orchestrator.py`.
4. **API** (`api/`) — FastAPI routes under `api/routes/`. All list endpoints use `PaginatedResponse[T]`. WebSocket at `/api/ws/dashboard` for real-time updates.
5. **Dashboard** (`dashboard/`) — React 19 + TypeScript + Tailwind CSS + TanStack React Query. API client in `api/client.ts`, hooks in `api/hooks.ts`.

### Database (`database/connection.py`)
All models in one file using SQLAlchemy async ORM with `DeclarativeBase`. Key tables:
- **Core:** `platforms`, `users`, `posts` (unified across all sources)
- **Analysis:** `topics`, `topic_mentions`, `discovered_products`, `migrations`, `pain_points`
- **Signals:** `research_pipelines`, `traction_scores`, `market_gaps`, `competitive_threats`, `agent_runs`
- **Custom Research:** `research_projects`, `research_insights`, `research_contacts`
- **Jobs/Gigs:** `gig_posts`, `product_reviews`

Posts use `raw_metadata` (JSONB) for source-specific data. Session factory: `async_session()` (not a context manager — use `async with async_session() as s:`).

### LLM Client (`processors/llm_client.py`)
```python
result = await call_llm(prompt, model="mini", parse_json=True, usage_tracker=usage)
```
Uses OpenAI-compatible API. Models: `"mini"` → gpt-4o-mini, `"turbo"` → gpt-4-turbo. `TokenUsage` class tracks costs.

## Key Patterns

- **Scraper:** Inherit `BaseScraper`, implement `scrape()`. Use `upsert_user()`, `upsert_post()`, `fetch_url()`, `rate_limit()`. Posts deduplicate via `platform_id` unique constraint.
- **Processor:** Class with `async def run()`. Load unprocessed posts in batches, call LLM, store results. Return summary dict.
- **API Route:** FastAPI router, `async_session()` for DB, return Pydantic schemas. Pagination: `page`, `per_page` query params → `PaginatedResponse`.
- **Frontend Hook:** TanStack React Query hook per endpoint in `hooks.ts`. Mutations invalidate related query keys.
- **Background Tasks:** FastAPI `BackgroundTasks` for long-running operations (e.g., research pipeline). Frontend polls with `refetchInterval`.

## Environment Variables

Required in `.env` (copy from `.env.example`):
- `DATABASE_URL` — async PostgreSQL URL (asyncpg driver)
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_DEPLOYMENT_MINI`
- `GITHUB_TOKEN`, `PH_ACCESS_TOKEN`, `SO_API_KEY` — for respective scrapers
- `RESEND_API_KEY`, `NOTIFY_EMAIL` — for pipeline email notifications
- Frontend: `VITE_API_URL` — set to `/api` for production build

## Conventions

- All I/O is async — use `async/await` everywhere
- Logging via `structlog` with bound context
- Reddit scraping via RSS feeds (`reddit.com/r/{sub}/.rss`, `reddit.com/search/.rss?q=...`) — no API key needed
- JSONB columns for flexible metadata — avoid schema migrations for new fields
- Upsert pattern: `pg_insert().on_conflict_do_update()` for idempotent data ingestion
