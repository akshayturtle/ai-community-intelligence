"""Fiverr gig scraper — uses residential proxies (DataImpulse).

Scrapes Fiverr gig listings to analyze what services are being offered:
popular AI/tech categories, pricing tiers, seller levels.
Useful for understanding the supply side of the freelance market.

Requires: DATAIMPULSE_HOST, DATAIMPULSE_PORT, DATAIMPULSE_USER, DATAIMPULSE_PASS
"""

import json
import re
from datetime import datetime, timezone

import structlog

from scrapers.base_scraper import BaseScraper
from scrapers.proxy import proxy_client, random_headers, is_configured

logger = structlog.get_logger()

SEARCH_QUERIES = [
    "AI agent", "ChatGPT automation", "LLM fine tuning",
    "Python developer", "machine learning model",
    "web scraping", "React app", "FastAPI",
    "data analysis", "computer vision",
    "blockchain smart contract", "NFT development",
    "mobile app", "DevOps AWS", "chatbot",
]

FIVERR_SEARCH = "https://www.fiverr.com/search/gigs"


class FiverrScraper(BaseScraper):
    """
    Scrapes Fiverr gig listings via residential proxy.
    Captures: gig title, seller info, pricing, category, rating.
    """

    def __init__(self):
        super().__init__(scraper_name="fiverr_scraper", request_delay=4.0)

    async def scrape(self, **kwargs):
        if not is_configured():
            self.log.warning(
                "fiverr_no_proxy",
                hint="Set DATAIMPULSE_* env vars to enable Fiverr scraping.",
            )
            return

        seen_ids: set[str] = set()

        for query in SEARCH_QUERIES:
            await self.rate_limit()
            await self._scrape_query(query, seen_ids)

    async def _scrape_query(self, query: str, seen_ids: set[str]):
        session_id = re.sub(r"[^a-z0-9]", "", query.lower())[:12]

        async with proxy_client(sticky_session=session_id) as client:
            try:
                url = f"{FIVERR_SEARCH}?query={query.replace(' ', '%20')}&sort_by=rating"
                resp = await client.get(url, headers=random_headers())

                if resp.status_code != 200:
                    self.log.warning("fiverr_fetch_failed", query=query, status=resp.status_code)
                    return

                gigs = self._parse_gigs(resp.text)

                for gig in gigs:
                    gig_id = str(gig.get("id") or gig.get("gig_id") or "")
                    if not gig_id or gig_id in seen_ids:
                        continue
                    seen_ids.add(gig_id)
                    await self._store_gig(gig, query)

            except Exception as e:
                self.log.warning("fiverr_scrape_failed", query=query, error=str(e))

    def _parse_gigs(self, html: str) -> list[dict]:
        """Extract gigs from Next.js __NEXT_DATA__ or JSON-LD in page."""
        gigs = []

        # Try __NEXT_DATA__ first
        try:
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if m:
                data = json.loads(m.group(1))
                items = (
                    data.get("props", {})
                        .get("pageProps", {})
                        .get("gigListings", {})
                        .get("gigs", [])
                )
                if items:
                    return items
        except Exception:
            pass

        # Fall back: look for inline JSON arrays with gig data patterns
        try:
            m = re.search(r'"gigs"\s*:\s*(\[.*?\])', html, re.S)
            if m:
                gigs = json.loads(m.group(1))
                return gigs
        except Exception:
            pass

        # Last resort: scrape Open Graph / structured data for basic info
        try:
            titles = re.findall(r'data-impression-id="([^"]+)"[^>]*title="([^"]+)"', html)
            for gig_id, title in titles[:50]:
                gigs.append({"id": gig_id, "title": title})
        except Exception:
            pass

        return gigs

    async def _store_gig(self, gig: dict, query: str):
        title = gig.get("title") or gig.get("gig_title") or ""
        if not title:
            return

        gig_id   = str(gig.get("id") or gig.get("gig_id") or "")
        seller   = gig.get("sellerName") or gig.get("seller", {}).get("name") or "Fiverr Seller"
        gig_url  = gig.get("url") or (f"https://www.fiverr.com{gig.get('gigUrl','')}" if gig.get("gigUrl") else "")
        category = gig.get("category") or gig.get("subcategory") or ""
        rating   = gig.get("rating") or gig.get("avgRating") or ""
        reviews  = gig.get("reviewsCount") or gig.get("ratingsCount") or 0

        # Pricing
        price = gig.get("price") or gig.get("packages", [{}])[0].get("price") if gig.get("packages") else gig.get("price")
        price_str = f"${price}" if price else ""

        content = (
            f"{title}\n\n"
            f"Seller: {seller}\n"
            f"Category: {category}\n"
            f"Starting price: {price_str}\n"
            f"Rating: {rating} ({reviews} reviews)\n"
        )

        author = await self.upsert_user(
            platform_name="fiverr",
            platform_user_id=f"seller_{re.sub(r'[^a-z0-9]', '_', seller.lower()[:40])}",
            username=seller,
            display_name=seller,
        )

        await self.upsert_post(
            platform_name="fiverr",
            platform_post_id=f"fiverr_{gig_id}",
            author_id=author,
            title=title,
            content=content[:3000],
            url=gig_url,
            created_at=datetime.now(timezone.utc),
            raw_metadata={
                "source": "fiverr",
                "gig_id": gig_id,
                "category": category,
                "price": price,
                "rating": rating,
                "reviews_count": reviews,
                "query": query,
            },
        )
