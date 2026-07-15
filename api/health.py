"""Lightweight health/readiness endpoint for the API.

Returns 200 when the process is up and the database is reachable, so load
balancers and uptime checks have a cheap endpoint to poll.
"""
from fastapi import APIRouter
from sqlalchemy import text

from agents.config import get_engine

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Return service and database readiness."""
    db_ok = True
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
