"""Shared exponential-backoff retry helper for scrapers.

Used by the Twitter/Nitter path (and any scraper that hits 429/403 rate
limits) to retry with jittered exponential backoff instead of failing on
the first throttle.
"""
import asyncio
import random
from typing import Awaitable, Callable, Iterable, TypeVar

T = TypeVar("T")

# HTTP statuses we treat as "retry after a wait" rather than a hard failure.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


async def with_backoff(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_on: Iterable[int] = RETRYABLE_STATUS,
) -> T:
    """Call ``fn`` with jittered exponential backoff.

    Retries when ``fn`` raises an exception carrying a ``.status_code`` in
    ``retry_on``. Re-raises immediately for non-retryable errors, and re-raises
    the last error once ``max_attempts`` is exhausted.
    """
    retry_on = frozenset(retry_on)
    attempt = 0
    while True:
        attempt += 1
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - inspected below
            status = getattr(exc, "status_code", None)
            if status not in retry_on or attempt >= max_attempts:
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.25)  # jitter
            await asyncio.sleep(delay)
