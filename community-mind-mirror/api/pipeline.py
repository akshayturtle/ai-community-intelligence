"""Pipeline state manager — tracks and broadcasts real-time scraper progress."""

import asyncio
import os
import re
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Awaitable

import structlog

logger = structlog.get_logger()

# ── Static manifests (mirrors run_scrapers_bg.py) ────────────────────────────
SCRAPERS = [
    "reddit", "hn", "news", "arxiv", "github", "huggingface",
    "stackoverflow", "paperswithcode", "packages", "yc",
    "youtube", "producthunt", "product_reddit",
    "jobs", "remoteok", "himalayas", "remotive", "themuse",
    "arbeitnow", "greenhouse", "lever", "ashby", "hn_hiring", "usajobs",
    "web3career", "adzuna",
    "freelancer", "peopleperhour",
    "upwork", "fiverr", "twitter",
]
PROCESSORS = [
    "sentiment", "topics", "news", "products", "personas",
    "migrations", "pain_points", "hype_index",
    "leader_shifts", "funding", "platform_tones", "graph",
    "product_reviews", "gig_posts",
]
AGENTS = [
    "research_pipeline", "traction_scorer", "market_gap_detector",
    "competitive_threat", "divergence_detector", "lifecycle_mapper",
    "smart_money_tracker", "talent_flow", "product_discoverer",
    "narrative_shift", "insight_synthesizer",
]

ALL_STEPS: dict[str, str] = (
    {s: "scraper" for s in SCRAPERS}
    | {p: "processor" for p in PROCESSORS}
    | {a: "agent" for a in AGENTS}
)

# ── Mutable state (single process, thread-safe enough for asyncio) ───────────
_state: dict = {}
_log: deque = deque(maxlen=300)
_broadcast: Callable[[dict], Awaitable[None]] | None = None
_running = False


def set_broadcast(fn: Callable[[dict], Awaitable[None]]):
    global _broadcast
    _broadcast = fn


def _blank_step(kind: str) -> dict:
    base = {"type": kind, "status": "pending", "duration_s": None, "error": None}
    if kind == "scraper":
        base.update(fetched=0, new=0)
    elif kind == "processor":
        base.update(result=None)
    elif kind == "agent":
        base.update(records=0)
    return base


def _reset():
    global _state, _log
    _state = {
        "running": False,
        "phase": "idle",       # idle | scrapers | processors | agents | done
        "current_steps": [],   # list — can be many during parallel scraping
        "started_at": None,
        "finished_at": None,
        "steps": {name: _blank_step(kind) for name, kind in ALL_STEPS.items()},
    }
    _log = deque(maxlen=300)


_reset()


async def _emit(event_type: str, payload: dict):
    if _broadcast:
        try:
            await _broadcast({"type": event_type, "data": payload})
        except Exception:
            pass


# ── Line parser ──────────────────────────────────────────────────────────────
_RE_SCRAPER_START  = re.compile(r'Scraper:\s+(\S+)')
_RE_PROC_START     = re.compile(r'Processor:\s+(\S+)')
_RE_AGENT_START    = re.compile(r'Agent:\s+(\S+)')
# scraper done lines include the name:  "  reddit: OK — 150 fetched, 42 new"
_RE_SCRAPER_OK     = re.compile(r'(\S+):\s+OK\s+[—\-]+\s+(\d+)\s+fetched,\s+(\d+)\s+new')
_RE_SCRAPER_TOUT   = re.compile(r'(\S+):\s+TIMEOUT\s+after\s+([\d.]+)s')
_RE_SCRAPER_ERR    = re.compile(r'(\S+):\s+ERROR\s+[—\-]+\s+(.+)')
# processor/agent done lines DON'T include name (context-dependent):
#   "    OK (2.3s): result_summary" or "    OK (2.3s): 5 records"
_RE_STEP_OK        = re.compile(r'OK\s+\(([\d.]+)s\)(?::\s+(.*))?')
_RE_STEP_TOUT      = re.compile(r'TIMEOUT\s+after\s+([\d.]+)s')
_RE_STEP_ERR       = re.compile(r'ERROR:\s+(.+)')
# phase header lines
_RE_PHASE1         = re.compile(r'Phase\s+1|SCRAPERS', re.I)
_RE_PHASE2         = re.compile(r'Phase\s+2|PROCESSORS', re.I)
_RE_PHASE3         = re.compile(r'Phase\s+3|AGENTS', re.I)


def _process_line(line: str, ctx: dict) -> list[tuple[str, dict]]:
    """
    Parse one stdout line.  ctx holds mutable parse context:
      ctx["phase"], ctx["step"]  (name of current step being processed)
    Returns list of (step_name, patch) pairs to apply to state.
    """
    s = line.strip()
    events = []

    # Phase transitions
    if _RE_PHASE1.search(s):
        ctx["phase"] = "scrapers"
    elif _RE_PHASE2.search(s):
        ctx["phase"] = "processors"
    elif _RE_PHASE3.search(s):
        ctx["phase"] = "agents"

    # Step start
    for regex, phase in [
        (_RE_SCRAPER_START, "scrapers"),
        (_RE_PROC_START, "processors"),
        (_RE_AGENT_START, "agents"),
    ]:
        m = regex.search(s)
        if m:
            name = m.group(1)
            ctx["step"] = name
            ctx["phase"] = phase
            events.append((name, {"status": "running"}))
            return events

    # Scraper completion (name in line)
    m = _RE_SCRAPER_OK.search(s)
    if m:
        name = m.group(1)
        events.append((name, {"status": "ok", "fetched": int(m.group(2)), "new": int(m.group(3))}))
        ctx["step"] = None
        return events

    m = _RE_SCRAPER_TOUT.search(s)
    if m:
        name = m.group(1)
        events.append((name, {"status": "timeout", "duration_s": float(m.group(2)),
                               "error": f"Timed out after {m.group(2)}s"}))
        ctx["step"] = None
        return events

    m = _RE_SCRAPER_ERR.search(s)
    if m:
        name = m.group(1)
        if name in ALL_STEPS:
            events.append((name, {"status": "error", "error": m.group(2)}))
            ctx["step"] = None
            return events

    # Processor / agent completion (use context for name)
    if ctx.get("step"):
        m = _RE_STEP_OK.search(s)
        if m:
            patch = {"status": "ok", "duration_s": float(m.group(1))}
            result_str = (m.group(2) or "").strip()
            # Detect "N records" for agents
            rec_m = re.match(r'(\d+)\s+record', result_str)
            if rec_m:
                patch["records"] = int(rec_m.group(1))
            else:
                patch["result"] = result_str[:80]
            events.append((ctx["step"], patch))
            ctx["step"] = None
            return events

        m = _RE_STEP_TOUT.search(s)
        if m:
            events.append((ctx["step"], {"status": "timeout", "duration_s": float(m.group(1)),
                                          "error": f"Timed out after {m.group(1)}s"}))
            ctx["step"] = None
            return events

        m = _RE_STEP_ERR.search(s)
        if m:
            events.append((ctx["step"], {"status": "error", "error": m.group(1)[:120]}))
            ctx["step"] = None
            return events

    return events


# ── Main runner ──────────────────────────────────────────────────────────────
async def run_pipeline() -> bool:
    global _running
    if _running:
        logger.warning("pipeline_skipped", reason="already_running")
        return False

    _running = True
    _reset()
    _state["running"] = True
    _state["phase"] = "scrapers"
    _state["current_steps"] = []
    _state["started_at"] = datetime.now(timezone.utc).isoformat()

    await _emit("pipeline_started", {
        "started_at": _state["started_at"],
        "scrapers": SCRAPERS,
        "processors": PROCESSORS,
        "agents": AGENTS,
    })
    logger.info("pipeline_started", trigger="manual_or_scheduler")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ctx = {"phase": "scrapers", "step": None}

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "run_scrapers_bg.py",
            cwd=root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            _log.append(line)

            # Update phase on state
            _state["phase"] = ctx["phase"]

            # Parse and apply patches
            patches = _process_line(line, ctx)
            _active: set = set(_state["current_steps"])
            for step_name, patch in patches:
                if step_name in _state["steps"]:
                    _state["steps"][step_name].update(patch)
                    if patch.get("status") == "running":
                        _active.add(step_name)
                    else:
                        _active.discard(step_name)
            _state["current_steps"] = sorted(_active)

            # Broadcast log line + any step updates
            await _emit("log_line", {"line": line, "phase": _state["phase"]})
            for step_name, patch in patches:
                if step_name in _state["steps"]:
                    await _emit("step_update", {
                        "step": step_name,
                        "phase": _state["phase"],
                        "update": _state["steps"][step_name],
                        "current_steps": _state["current_steps"],
                    })

        await proc.wait()
        logger.info("pipeline_finished", returncode=proc.returncode)

    except Exception as e:
        logger.error("pipeline_error", error=str(e))
        _log.append(f"[pipeline error] {e}")
    finally:
        _running = False
        _state["running"] = False
        _state["phase"] = "done"
        _state["current_steps"] = []
        _state["finished_at"] = datetime.now(timezone.utc).isoformat()

        await _emit("pipeline_finished", {
            "finished_at": _state["finished_at"],
            "steps": _state["steps"],
        })

    return True


def get_state() -> dict:
    """Snapshot of current pipeline state (safe to JSON-serialize)."""
    return {
        **_state,
        "log": list(_log)[-100:],    # last 100 lines
        "scrapers": SCRAPERS,
        "processors": PROCESSORS,
        "agents": AGENTS,
    }


def is_running() -> bool:
    return _running
