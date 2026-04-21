"""DataImpulse residential proxy helper.

Set these env vars (Azure App Service → Configuration → App settings):
  DATAIMPULSE_HOST      e.g.  gw.dataimpulse.com
  DATAIMPULSE_PORT      e.g.  823
  DATAIMPULSE_USER      your username
  DATAIMPULSE_PASS      your password

Usage:
    from scrapers.proxy import proxy_client, random_headers

    async with proxy_client() as client:
        resp = await client.get(url, headers=random_headers())
"""

import os
import random
import httpx

PROXY_HOST = os.getenv("DATAIMPULSE_HOST", "gw.dataimpulse.com")
PROXY_PORT = os.getenv("DATAIMPULSE_PORT", "823")
PROXY_USER = os.getenv("DATAIMPULSE_USER", "")
PROXY_PASS = os.getenv("DATAIMPULSE_PASS", "")

# DataImpulse supports sticky sessions via username suffix:
# username-session-XXXXX:password  →  same IP for that session ID
# username:password                →  rotate every request


def proxy_url(sticky_session: str | None = None) -> str:
    """Build the proxy URL. Pass a sticky_session string to pin to one IP."""
    if not PROXY_USER or not PROXY_PASS:
        return ""
    user = f"{PROXY_USER}-session-{sticky_session}" if sticky_session else PROXY_USER
    return f"http://{user}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"


def is_configured() -> bool:
    return bool(PROXY_USER and PROXY_PASS)


# Realistic browser User-Agent pool (rotated per request)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def random_headers(referer: str = "", extra: dict | None = None) -> dict:
    """Return realistic browser-like headers with a random User-Agent."""
    h = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }
    if referer:
        h["Referer"] = referer
        h["Sec-Fetch-Site"] = "same-origin"
    if extra:
        h.update(extra)
    return h


def json_headers(referer: str = "", extra: dict | None = None) -> dict:
    """Headers for XHR/JSON requests (fetch, not navigate)."""
    h = {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    if referer:
        h["Referer"] = referer
    if extra:
        h.update(extra)
    return h


def proxy_client(
    timeout: float = 30.0,
    sticky_session: str | None = None,
    follow_redirects: bool = True,
) -> httpx.AsyncClient:
    """
    Return an httpx.AsyncClient routed through the DataImpulse proxy.
    Falls back to direct connection if proxy is not configured.
    """
    purl = proxy_url(sticky_session)
    proxies = {"http://": purl, "https://": purl} if purl else None
    return httpx.AsyncClient(
        proxies=proxies,
        timeout=timeout,
        follow_redirects=follow_redirects,
        verify=False,       # residential proxies often MITM SSL — disable cert check
    )
