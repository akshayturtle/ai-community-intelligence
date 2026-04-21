"""Fiverr gig scraper — residential proxy + tls_client for Cloudflare bypass.

Uses DataImpulse residential proxies so requests appear as real users.
tls_client mimics a real browser's TLS fingerprint, bypassing JS-challenge bot
detection that plain httpx fails against.

Requires: DATAIMPULSE_HOST, DATAIMPULSE_PORT, DATAIMPULSE_USER, DATAIMPULSE_PASS
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from functools import partial

import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.proxy import proxy_url as get_proxy_url, is_configured, random_headers

logger = structlog.get_logger()

SEARCH_QUERIES = [
    "AI agent",
    "ChatGPT automation",
    "LLM fine tuning",
    "Python developer",
    "machine learning model",
    "web scraping",
    "React app",
    "FastAPI",
    "data analysis",
    "computer vision",
    "blockchain smart contract",
    "mobile app",
    "DevOps AWS",
    "chatbot",
    "RAG system",
    "AI automation",
    "n8n workflow",
    "data pipeline",
]

FIVERR_SEARCH = "https://www.fiverr.com/search/gigs"

# Fallback to httpx if tls_client not available
try:
    import tls_client as _tls_client
    _TLS_AVAILABLE = True
except ImportError:
    _TLS_AVAILABLE = False


def _sync_fetch(url: str, proxy_str: str | None, headers: dict) -> tuple[int, str]:
    """Synchronous fetch using tls_client (run in executor)."""
    if _TLS_AVAILABLE:
        session = _tls_client.Session(
            client_identifier="chrome_120",
            random_tls_extension_order=True,
        )
        kwargs: dict = {"headers": headers}
        if proxy_str:
            kwargs["proxy"] = proxy_str
        resp = session.get(url, **kwargs)
        return resp.status_code, resp.text
    else:
        import httpx
        with httpx.Client(
            proxy=proxy_str,
            timeout=30.0,
            follow_redirects=True,
            verify=False,
        ) as client:
            resp = client.get(url, headers=headers)
            return resp.status_code, resp.text


class FiverrScraper(BaseScraper):
    """
    Scrapes Fiverr gig listings using residential proxies + tls_client.
    Captures: gig title, seller, pricing, category, rating.
    """

    def __init__(self):
        super().__init__(scraper_name="fiverr_scraper", request_delay=4.0)

    async def scrape(self, **kwargs):
        if not is_configured():
            self.log.warning(
                "fiverr_no_proxy",
                hint="Set DATAIMPULSE_HOST/PORT/USER/PASS env vars to enable Fiverr scraping.",
            )
            return

        proxy_str = get_proxy_url()  # e.g. http://user:pass@host:port
        seen_ids: set[str] = set()
        loop = asyncio.get_event_loop()

        for query in SEARCH_QUERIES:
            await self.rate_limit()
            try:
                url = (
                    f"{FIVERR_SEARCH}"
                    f"?query={query.replace(' ', '%20')}"
                    f"&offset=0&filter=rating&type=auto"
                )
                headers = {
                    **random_headers(),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": "https://www.fiverr.com/",
                    "DNT": "1",
                }

                status, text = await loop.run_in_executor(
                    None, partial(_sync_fetch, url, proxy_str, headers)
                )

                if status != 200:
                    self.log.warning("fiverr_fetch_failed", query=query, status=status)
                    continue

                gigs = self._parse_gigs(text)
                for gig in gigs:
                    gid = str(gig.get("id") or gig.get("gig_id") or "")
                    if not gid or gid in seen_ids:
                        continue
                    seen_ids.add(gid)
                    await self._store_gig(gig, query)

            except Exception as e:
                self.log.warning("fiverr_scrape_error", query=query, error=str(e))

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_gigs(self, html: str) -> list[dict]:
        """Try multiple extraction strategies against Fiverr's HTML."""
        # Strategy 1: __NEXT_DATA__
        gigs = self._from_next_data(html)
        if gigs:
            return gigs

        # Strategy 2: window.__fiverr_data__ or similar globals
        gigs = self._from_window_data(html)
        if gigs:
            return gigs

        # Strategy 3: JSON blob with "gigs" key
        gigs = self._from_json_blobs(html)
        if gigs:
            return gigs

        # Strategy 4: HTML attribute scraping (data-impression-id)
        gigs = self._from_html_attrs(html)
        return gigs

    def _from_next_data(self, html: str) -> list[dict]:
        try:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if not m:
                return []
            data = json.loads(m.group(1))
            pp = data.get("props", {}).get("pageProps", {})
            gigs = (
                pp.get("gigListings", {}).get("gigs", [])
                or pp.get("listings", {}).get("gigs", [])
                or pp.get("gigs", [])
                or []
            )
            return gigs
        except Exception:
            return []

    def _from_window_data(self, html: str) -> list[dict]:
        """Extract from window.__FIVERR_DATA__, window.__gigData__, etc."""
        patterns = [
            r'window\.__FIVERR_DATA__\s*=\s*(\{.*?\});',
            r'window\.__gigData__\s*=\s*(\{.*?\});',
            r'"gigListings"\s*:\s*\{"gigs"\s*:\s*(\[.*?\])\}',
        ]
        for pat in patterns:
            try:
                m = re.search(pat, html, re.S)
                if m:
                    blob = json.loads(m.group(1))
                    if isinstance(blob, list):
                        return blob
                    gigs = (
                        blob.get("gigs", [])
                        or blob.get("gigListings", {}).get("gigs", [])
                        or []
                    )
                    if gigs:
                        return gigs
            except Exception:
                continue
        return []

    def _from_json_blobs(self, html: str) -> list[dict]:
        """Scan for any JSON blob that looks like a gig list."""
        try:
            m = re.search(r'"gigs"\s*:\s*(\[.*?\])', html, re.S)
            if m:
                return json.loads(m.group(1))
        except Exception:
            pass
        return []

    def _from_html_attrs(self, html: str) -> list[dict]:
        """Last resort: parse gig cards from HTML attributes."""
        gigs = []
        # Match patterns like: data-impression-id="..." title="..."
        for m in re.finditer(
            r'data-impression-id="([^"]+)"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)',
            html, re.S
        )[:50]:
            gigs.append({
                "id": m.group(1),
                "gigUrl": m.group(2),
                "title": m.group(3).strip(),
            })
        # Also try: <img alt="gig title" data-gig-id="...">
        for m in re.finditer(
            r'data-gig-id="(\d+)"[^>]+alt="([^"]+)"',
            html
        )[:50]:
            gigs.append({"id": m.group(1), "title": m.group(2)})
        return gigs

    # ── Storage ──────────────────────────────────────────────────────────────

    async def _store_gig(self, gig: dict, query: str):
        title = gig.get("title") or gig.get("gig_title") or gig.get("gigTitle") or ""
        if not title:
            return

        gig_id   = str(gig.get("id") or gig.get("gig_id") or "")
        seller   = (
            gig.get("sellerName")
            or (gig.get("seller") or {}).get("name")
            or gig.get("username")
            or "fiverr_seller"
        )
        gig_url  = gig.get("url") or gig.get("gigUrl") or ""
        if gig_url and not gig_url.startswith("http"):
            gig_url = f"https://www.fiverr.com{gig_url}"

        category = gig.get("category") or gig.get("subcategory") or ""
        rating   = gig.get("rating") or gig.get("avgRating") or gig.get("score") or ""
        reviews  = gig.get("reviewsCount") or gig.get("ratingsCount") or 0

        packages = gig.get("packages") or []
        price    = (
            gig.get("price")
            or (packages[0].get("price") if packages else None)
            or gig.get("minPrice")
        )
        price_str = f"${price}" if price else ""

        body = (
            f"{title}\n\n"
            f"Seller: {seller}\n"
            f"Category: {category}\n"
            f"Starting from: {price_str}\n"
            f"Rating: {rating} ({reviews} reviews)\n"
            f"Query: {query}"
        )

        author = await self.upsert_user(
            platform_name="fiverr",
            platform_user_id=f"seller_{re.sub(r'[^a-z0-9]', '_', str(seller).lower()[:40])}",
            username=str(seller)[:80],
        )

        await self.upsert_post(
            user_id=author,
            platform_name="fiverr",
            post_type="post",
            platform_post_id=f"fiverr_{gig_id}",
            body=body[:3000],
            title=title,
            url=gig_url,
            posted_at=datetime.now(timezone.utc),
            raw_metadata={
                "source": "fiverr",
                "gig_id": gig_id,
                "category": category,
                "price": price,
                "rating": str(rating),
                "reviews_count": reviews,
                "query": query,
            },
        )
