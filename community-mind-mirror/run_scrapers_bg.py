"""Background pipeline runner: Scrapers → Processors → Agents → Email.

Usage:
    python3 run_scrapers_bg.py                    # Full pipeline once
    python3 run_scrapers_bg.py --loop             # Loop forever (6h interval)
    python3 run_scrapers_bg.py --scraper reddit   # Single scraper only
    python3 run_scrapers_bg.py --analyze-only     # Skip scrapers, run processors + agents
    python3 run_scrapers_bg.py --loop --interval 3  # Custom interval
"""

import asyncio
import os
import time
import traceback
from datetime import datetime, timezone

import httpx

from spending_tracker import (
    is_over_budget, get_spending_summary, get_spending_html, get_remaining,
)

# ── Timeouts (seconds) ──────────────────────────────────────────────
SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "600"))       # 10 min per scraper
PROCESSOR_TIMEOUT = int(os.getenv("PROCESSOR_TIMEOUT", "300"))   # 5 min per processor
AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "300"))           # 5 min per agent

# ── Config ──────────────────────────────────────────────────────────
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")


# ── Email helper ────────────────────────────────────────────────────
def send_email(subject: str, body_html: str):
    """Send email via Resend API (sync)."""
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [NOTIFY_EMAIL],
                "subject": subject,
                "html": body_html,
            },
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            print(f"[email] Sent: {subject}")
        else:
            print(f"[email] Failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[email] Error: {e}")


# ── HTML formatters ─────────────────────────────────────────────────
def _table_rows(results: dict, columns: list[str]) -> str:
    rows = ""
    for name, info in results.items():
        status = info.get("status", "unknown")
        color = "#22c55e" if status == "ok" else "#ef4444"
        cells = ""
        for col in columns:
            val = info.get(col, "-")
            if col == "error" and val and val != "-":
                cells += f"<td style='color:#ef4444;font-size:12px'>{str(val)[:80]}</td>"
            elif col == "status":
                cells += f"<td style='color:{color}'>{val}</td>"
            elif isinstance(val, (int, float)):
                cells += f"<td>{val:,}</td>"
            else:
                cells += f"<td>{val}</td>"
        rows += f"<tr><td><b>{name}</b></td>{cells}</tr>"
    return rows


def format_full_report_html(
    scraper_results: dict,
    processor_results: dict,
    agent_results: dict,
    total_duration_s: float,
    db_stats: dict,
) -> str:
    mins = int(total_duration_s // 60)
    secs = int(total_duration_s % 60)

    # Scraper table
    scraper_rows = _table_rows(scraper_results, ["status", "fetched", "new", "error"])
    total_new = sum(r.get("new", 0) for r in scraper_results.values())

    # Processor table
    proc_rows = _table_rows(processor_results, ["status", "result", "duration_s", "error"])

    # Agent table
    agent_rows = _table_rows(agent_results, ["status", "records", "duration_s", "error"])

    # DB stats
    db_lines = "".join(
        f"<tr><td>{k}</td><td><b>{v:,}</b></td></tr>" for k, v in db_stats.items()
    )

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:750px;margin:0 auto;">

        <h2 style="color:#1e40af;margin-bottom:4px;">CMM Pipeline Complete</h2>
        <p style="color:#64748b;margin-top:0;">
            {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} &bull;
            Duration: {mins}m {secs}s &bull;
            {total_new:,} new scraped records
        </p>

        <h3 style="color:#0f172a;">1. Scrapers</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Scraper</th><th>Status</th><th>Fetched</th><th>New</th><th>Error</th></tr>
            {scraper_rows}
        </table>

        <h3 style="color:#0f172a;">2. Processors</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Processor</th><th>Status</th><th>Result</th><th>Time (s)</th><th>Error</th></tr>
            {proc_rows}
        </table>

        <h3 style="color:#0f172a;">3. Signal Agents</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Agent</th><th>Status</th><th>Records</th><th>Time (s)</th><th>Error</th></tr>
            {agent_rows}
        </table>

        <h3 style="color:#0f172a;">4. Database Totals</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Table</th><th>Rows</th></tr>
            {db_lines}
        </table>

    </div>
    """


# ── Scraper registry ───────────────────────────────────────────────
SCRAPER_ORDER = [
    "reddit", "hn", "news", "arxiv", "github", "huggingface",
    "stackoverflow", "paperswithcode", "packages", "yc",
    "youtube", "producthunt", "product_reddit",
    # Job scrapers
    "jobs", "remoteok", "himalayas", "remotive", "themuse",
    "arbeitnow", "greenhouse", "lever", "ashby", "hn_hiring", "usajobs",
]


def get_scraper(name: str):
    if name == "reddit":
        from scrapers.reddit_scraper import RedditScraper
        return RedditScraper()
    elif name == "hn":
        from scrapers.hn_scraper import HNScraper
        return HNScraper()
    elif name == "news":
        from scrapers.news_scraper import NewsScraper
        return NewsScraper()
    elif name == "arxiv":
        from scrapers.arxiv_scraper import ArxivScraper
        return ArxivScraper()
    elif name == "github":
        from scrapers.github_scraper import GitHubScraper
        return GitHubScraper()
    elif name == "huggingface":
        from scrapers.huggingface_scraper import HuggingFaceScraper
        return HuggingFaceScraper()
    elif name == "stackoverflow":
        from scrapers.stackoverflow_scraper import StackOverflowScraper
        return StackOverflowScraper()
    elif name == "paperswithcode":
        from scrapers.paperswithcode_scraper import PapersWithCodeScraper
        return PapersWithCodeScraper()
    elif name == "packages":
        from scrapers.package_scraper import PackageScraper
        return PackageScraper()
    elif name == "yc":
        from scrapers.yc_scraper import YCScraper
        return YCScraper()
    elif name == "youtube":
        from scrapers.youtube_scraper import YouTubeScraper
        return YouTubeScraper()
    elif name == "producthunt":
        from scrapers.producthunt_scraper import ProductHuntScraper
        return ProductHuntScraper()
    elif name == "jobs":
        from scrapers.job_scraper import JobScraper
        return JobScraper()
    elif name == "remoteok":
        from scrapers.remoteok_scraper import RemoteOKScraper
        return RemoteOKScraper()
    elif name == "himalayas":
        from scrapers.himalayas_scraper import HimalayasScraper
        return HimalayasScraper()
    elif name == "remotive":
        from scrapers.remotive_scraper import RemotiveScraper
        return RemotiveScraper()
    elif name == "themuse":
        from scrapers.themuse_scraper import TheMuseScraper
        return TheMuseScraper()
    elif name == "arbeitnow":
        from scrapers.arbeitnow_scraper import ArbeitnowScraper
        return ArbeitnowScraper()
    elif name == "greenhouse":
        from scrapers.ats_job_scraper import GreenhouseJobScraper
        return GreenhouseJobScraper()
    elif name == "lever":
        from scrapers.ats_job_scraper import LeverJobScraper
        return LeverJobScraper()
    elif name == "ashby":
        from scrapers.ats_job_scraper import AshbyJobScraper
        return AshbyJobScraper()
    elif name == "hn_hiring":
        from scrapers.hn_hiring_scraper import HNHiringScraper
        return HNHiringScraper()
    elif name == "usajobs":
        from scrapers.usajobs_scraper import USAJobsScraper
        return USAJobsScraper()
    elif name == "product_reddit":
        from scrapers.product_reddit_scraper import ProductRedditScraper
        return ProductRedditScraper()
    else:
        raise ValueError(f"Unknown scraper: {name}")


# ── Phase 1: Scrapers ──────────────────────────────────────────────
async def run_scrapers(scraper_names: list[str] | None = None) -> dict:
    names = scraper_names or SCRAPER_ORDER
    results = {}

    for name in names:
        print(f"\n{'='*50}\n  Scraper: {name}\n{'='*50}")
        t0 = time.time()
        try:
            scraper = get_scraper(name)
            await asyncio.wait_for(scraper.run(), timeout=SCRAPER_TIMEOUT)
            results[name] = {
                "status": "ok",
                "fetched": scraper.records_fetched,
                "new": scraper.records_new,
                "duration_s": round(time.time() - t0, 1),
            }
            print(f"  {name}: OK — {scraper.records_fetched} fetched, {scraper.records_new} new")
        except asyncio.TimeoutError:
            elapsed = round(time.time() - t0, 1)
            results[name] = {
                "status": "timeout", "fetched": getattr(scraper, "records_fetched", 0),
                "new": getattr(scraper, "records_new", 0),
                "error": f"Timed out after {SCRAPER_TIMEOUT}s",
                "duration_s": elapsed,
            }
            print(f"  {name}: TIMEOUT after {elapsed}s — skipping")
        except Exception as e:
            results[name] = {
                "status": "error", "fetched": 0, "new": 0,
                "error": str(e), "duration_s": round(time.time() - t0, 1),
            }
            print(f"  {name}: ERROR — {e}")
            traceback.print_exc()

    return results


# ── Phase 2: Processors ────────────────────────────────────────────
PROCESSOR_ORDER = [
    "sentiment", "topics", "news", "products", "personas",
    "migrations", "pain_points", "hype_index",
    "leader_shifts", "funding", "platform_tones", "graph",
    "product_reviews", "gig_posts",
]


async def run_processors() -> dict:
    from processors.run_processors import PROCESSOR_MAP
    results = {}

    for name in PROCESSOR_ORDER:
        if name not in PROCESSOR_MAP:
            continue
        print(f"\n  Processor: {name}")
        t0 = time.time()
        try:
            result = await asyncio.wait_for(PROCESSOR_MAP[name](), timeout=PROCESSOR_TIMEOUT)
            elapsed = round(time.time() - t0, 1)
            result_summary = ", ".join(f"{k}={v}" for k, v in result.items()) if result else "done"
            results[name] = {
                "status": "ok",
                "result": result_summary[:60],
                "duration_s": elapsed,
            }
            print(f"    OK ({elapsed}s): {result_summary}")
        except asyncio.TimeoutError:
            elapsed = round(time.time() - t0, 1)
            results[name] = {
                "status": "timeout", "result": "-",
                "error": f"Timed out after {PROCESSOR_TIMEOUT}s",
                "duration_s": elapsed,
            }
            print(f"    TIMEOUT after {elapsed}s — skipping")
        except Exception as e:
            results[name] = {
                "status": "error", "result": "-",
                "error": str(e), "duration_s": round(time.time() - t0, 1),
            }
            print(f"    ERROR: {e}")
            traceback.print_exc()

    return results


# ── Phase 3: Signal Agents ─────────────────────────────────────────
AGENT_ORDER = [
    "research_pipeline", "traction_scorer", "market_gap_detector",
    "competitive_threat", "divergence_detector", "lifecycle_mapper",
    "smart_money_tracker", "talent_flow", "product_discoverer",
    "narrative_shift", "insight_synthesizer",
]


async def run_agents() -> dict:
    from agents.orchestrator import CrossSourceOrchestrator
    orchestrator = CrossSourceOrchestrator()
    results = {}

    for name in AGENT_ORDER:
        print(f"\n  Agent: {name}")
        t0 = time.time()
        try:
            output = await asyncio.wait_for(orchestrator.run_single(name), timeout=AGENT_TIMEOUT)
            elapsed = round(time.time() - t0, 1)
            records = 0
            if output:
                import json as _json
                try:
                    data = _json.loads(output)
                    records = len(data) if isinstance(data, list) else 1
                except Exception:
                    records = 1 if len(output) > 10 else 0
            results[name] = {
                "status": "ok",
                "records": records,
                "duration_s": elapsed,
            }
            print(f"    OK ({elapsed}s): {records} records")
        except asyncio.TimeoutError:
            elapsed = round(time.time() - t0, 1)
            results[name] = {
                "status": "timeout", "records": 0,
                "error": f"Timed out after {AGENT_TIMEOUT}s",
                "duration_s": elapsed,
            }
            print(f"    TIMEOUT after {elapsed}s — skipping")
        except Exception as e:
            results[name] = {
                "status": "error", "records": 0,
                "error": str(e), "duration_s": round(time.time() - t0, 1),
            }
            print(f"    ERROR: {e}")
            traceback.print_exc()

    return results


# ── DB Stats ────────────────────────────────────────────────────────
async def get_db_stats() -> dict:
    from sqlalchemy import select, func
    from database.connection import (
        async_session, User, Post, NewsEvent, Persona, Topic,
        DiscoveredProduct, Migration, PainPoint, GithubRepo,
        HFModel, PHLaunch, SOQuestion, YCCompany, AgentRun,
    )
    stats = {}
    async with async_session() as session:
        for name, model in [
            ("Users", User), ("Posts", Post), ("News Events", NewsEvent),
            ("Personas", Persona), ("Topics", Topic),
            ("Products", DiscoveredProduct), ("Migrations", Migration),
            ("Pain Points", PainPoint), ("GitHub Repos", GithubRepo),
            ("HF Models", HFModel), ("PH Launches", PHLaunch),
            ("SO Questions", SOQuestion), ("YC Companies", YCCompany),
            ("Agent Runs", AgentRun),
        ]:
            count = (await session.execute(select(func.count(model.id)))).scalar()
            stats[name] = count or 0
    return stats


# ── Step email helper ──────────────────────────────────────────────
def _phase_email(phase_name: str, results: dict, columns: list[str]):
    """Send an email after each pipeline phase completes."""
    ok = sum(1 for r in results.values() if r.get("status") == "ok")
    err = sum(1 for r in results.values() if r.get("status") == "error")
    rows = _table_rows(results, columns)
    header_cols = "".join(f"<th>{c.title()}</th>" for c in columns)

    budget_html = get_spending_html()
    status_icon = "OK" if err == 0 else "WARN"
    subject = f"[{status_icon}] CMM {phase_name}: {ok} ok, {err} errors | Budget: {get_spending_summary()}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
        <h2 style="color:#1e40af;">{phase_name} Complete</h2>
        <p style="color:#64748b;">{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Name</th>{header_cols}</tr>
            {rows}
        </table>
        {budget_html}
    </div>
    """
    send_email(subject, html)


# ── Full pipeline ───────────────────────────────────────────────────
async def run_full_pipeline(
    scraper_names: list[str] | None = None,
    skip_scrapers: bool = False,
):
    """Run: Scrapers → Processors → Agents → Email report."""
    pipeline_start = time.time()

    send_email(
        "CMM Pipeline Starting",
        f"<p>Pipeline started at {datetime.now(timezone.utc).strftime('%H:%M UTC')}</p>"
        f"<p>Steps: {'Scrapers -> ' if not skip_scrapers else ''}Processors -> Agents -> Report</p>"
        f"<p>Budget: {get_spending_summary()}</p>",
    )

    # Phase 1: Scrapers (no LLM cost)
    scraper_results = {}
    if not skip_scrapers:
        print(f"\n{'#'*60}\n  PHASE 1: SCRAPERS\n{'#'*60}")
        scraper_results = await run_scrapers(scraper_names)
        _phase_email("Phase 1: Scrapers", scraper_results, ["status", "fetched", "new", "error"])

    # Phase 2: Processors (uses LLM — check budget)
    processor_results = {}
    if is_over_budget():
        msg = f"Budget cap reached: {get_spending_summary()}"
        print(f"\n  BUDGET EXCEEDED — skipping processors. {msg}")
        send_email("CMM Budget Exceeded — Skipping Processors", f"<p>{msg}</p><p>Processors and agents skipped.</p>")
    else:
        print(f"\n{'#'*60}\n  PHASE 2: PROCESSORS (analysis)\n{'#'*60}")
        print(f"  Budget: {get_spending_summary()}")
        processor_results = await run_processors()
        _phase_email("Phase 2: Processors", processor_results, ["status", "result", "duration_s", "error"])

    # Phase 3: Signal Agents (uses LLM — check budget)
    agent_results = {}
    if is_over_budget():
        if processor_results:  # only email if processors ran (didn't already send budget email)
            msg = f"Budget cap reached after processors: {get_spending_summary()}"
            print(f"\n  BUDGET EXCEEDED — skipping agents. {msg}")
            send_email("CMM Budget Exceeded — Skipping Agents", f"<p>{msg}</p><p>Agents skipped.</p>")
    else:
        print(f"\n{'#'*60}\n  PHASE 3: SIGNAL AGENTS (intelligence)\n{'#'*60}")
        print(f"  Budget: {get_spending_summary()}")
        agent_results = await run_agents()
        _phase_email("Phase 3: Signal Agents", agent_results, ["status", "records", "duration_s", "error"])

    # Get DB stats
    db_stats = await get_db_stats()

    total_duration = time.time() - pipeline_start

    # Send comprehensive final report
    html = format_full_report_html(
        scraper_results, processor_results, agent_results,
        total_duration, db_stats,
    )
    html += get_spending_html()

    total_new = sum(r.get("new", 0) for r in scraper_results.values())
    total_errors = (
        sum(1 for r in scraper_results.values() if r.get("status") == "error")
        + sum(1 for r in processor_results.values() if r.get("status") == "error")
        + sum(1 for r in agent_results.values() if r.get("status") == "error")
    )

    subject = f"CMM Pipeline Done: {total_new:,} new | Budget: {get_spending_summary()}"
    if total_errors > 0:
        subject += f" ({total_errors} errors)"

    send_email(subject, html)

    print(f"\n{'='*60}")
    print(f"  PIPELINE COMPLETE — {int(total_duration//60)}m {int(total_duration%60)}s")
    print(f"  Budget: {get_spending_summary()}")
    print(f"  DB: {db_stats.get('Posts', 0):,} posts, {db_stats.get('Users', 0):,} users")
    print(f"{'='*60}")


async def run_loop(
    scraper_names: list[str] | None = None,
    interval_hours: float = 6,
    skip_scrapers: bool = False,
):
    """Run the full pipeline in a loop forever."""
    cycle = 0
    while True:
        cycle += 1
        print(f"\n{'#'*60}")
        print(f"  CYCLE {cycle} — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"{'#'*60}")

        try:
            await run_full_pipeline(scraper_names, skip_scrapers)
        except Exception as e:
            print(f"\n  CYCLE {cycle} FAILED: {e}")
            traceback.print_exc()
            send_email(
                f"CMM Pipeline FAILED (cycle {cycle})",
                f"<p style='color:red'>Pipeline crashed: {str(e)[:200]}</p>",
            )

        print(f"\nSleeping {interval_hours}h until next cycle...")
        await asyncio.sleep(interval_hours * 3600)


# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CMM Background Pipeline Runner")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=float, default=6, help="Hours between cycles (default: 6)")
    parser.add_argument("--scraper", type=str, help="Run specific scraper only")
    parser.add_argument("--analyze-only", action="store_true", help="Skip scrapers, run processors + agents only")
    args = parser.parse_args()

    names = [args.scraper] if args.scraper else None

    if args.loop:
        asyncio.run(run_loop(names, args.interval, skip_scrapers=args.analyze_only))
    else:
        asyncio.run(run_full_pipeline(names, skip_scrapers=args.analyze_only))
