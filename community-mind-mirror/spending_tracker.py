"""Persistent spending tracker — caps total Azure OpenAI spend.

Stores cumulative spending in a JSON file so it survives restarts.
Checks before each LLM-using phase to prevent overspend.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

SPEND_FILE = Path(__file__).parent / ".spending.json"
DEFAULT_CAP = float(os.getenv("LLM_SPEND_CAP_USD", "200.0"))

# Azure OpenAI pricing (per 1M tokens)
PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def _load() -> dict:
    if SPEND_FILE.exists():
        try:
            return json.loads(SPEND_FILE.read_text())
        except Exception:
            pass
    return {
        "total_spent_usd": 0.0,
        "cap_usd": DEFAULT_CAP,
        "history": [],
    }


def _save(data: dict):
    SPEND_FILE.write_text(json.dumps(data, indent=2, default=str))


def get_total_spent() -> float:
    return _load().get("total_spent_usd", 0.0)


def get_cap() -> float:
    return _load().get("cap_usd", DEFAULT_CAP)


def get_remaining() -> float:
    data = _load()
    return data.get("cap_usd", DEFAULT_CAP) - data.get("total_spent_usd", 0.0)


def is_over_budget() -> bool:
    return get_remaining() <= 0


def record_spend(phase: str, cost_usd: float, details: str = ""):
    """Record a spending event and update the cumulative total."""
    data = _load()
    data["total_spent_usd"] = round(data.get("total_spent_usd", 0.0) + cost_usd, 4)
    data["history"].append({
        "phase": phase,
        "cost_usd": round(cost_usd, 4),
        "cumulative_usd": data["total_spent_usd"],
        "details": details,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # Keep last 500 entries
    data["history"] = data["history"][-500:]
    _save(data)


def set_cap(cap_usd: float):
    data = _load()
    data["cap_usd"] = cap_usd
    _save(data)


def get_spending_summary() -> str:
    data = _load()
    total = data.get("total_spent_usd", 0.0)
    cap = data.get("cap_usd", DEFAULT_CAP)
    remaining = cap - total
    pct = (total / cap * 100) if cap > 0 else 0
    return f"${total:.2f} / ${cap:.2f} ({pct:.1f}% used, ${remaining:.2f} remaining)"


def get_spending_html() -> str:
    data = _load()
    total = data.get("total_spent_usd", 0.0)
    cap = data.get("cap_usd", DEFAULT_CAP)
    remaining = cap - total
    pct = (total / cap * 100) if cap > 0 else 0
    bar_color = "#22c55e" if pct < 70 else "#f59e0b" if pct < 90 else "#ef4444"

    recent = data.get("history", [])[-10:]
    rows = ""
    for h in reversed(recent):
        rows += f"<tr><td>{h['phase']}</td><td>${h['cost_usd']:.4f}</td><td>${h['cumulative_usd']:.2f}</td><td style='font-size:11px'>{h.get('details','')[:40]}</td></tr>"

    return f"""
    <div style="margin:10px 0;padding:10px;background:#f8fafc;border-radius:6px;">
        <h4 style="margin:0 0 8px 0;">Budget: ${total:.2f} / ${cap:.2f} ({pct:.1f}%)</h4>
        <div style="background:#e2e8f0;border-radius:4px;height:16px;width:100%;">
            <div style="background:{bar_color};border-radius:4px;height:16px;width:{min(pct,100):.0f}%;"></div>
        </div>
        <p style="margin:4px 0 0;color:#64748b;font-size:12px;">${remaining:.2f} remaining</p>
        {f'''<table border="1" cellpadding="3" cellspacing="0" style="border-collapse:collapse;font-size:12px;margin-top:8px;width:100%;">
            <tr style="background:#f1f5f9;"><th>Phase</th><th>Cost</th><th>Cumulative</th><th>Details</th></tr>
            {rows}
        </table>''' if rows else ''}
    </div>
    """
