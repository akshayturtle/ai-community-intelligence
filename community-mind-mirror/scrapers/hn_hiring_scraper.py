"""HN Who's Hiring scraper — parses monthly hiring thread comments via Algolia API."""

import re
from datetime import datetime

import httpx
import structlog

from config.sources import HN_HIRING_SCRAPE_CONFIG
from config.settings import USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()

# Patterns for parsing pipe-delimited HN hiring comments
SALARY_PATTERN = re.compile(
    r"\$\s*([\d,]+)\s*[kK]?\s*[-–to]+\s*\$?\s*([\d,]+)\s*[kK]?", re.IGNORECASE
)
REMOTE_PATTERN = re.compile(r"\b(remote|work from home|wfh|distributed|anywhere)\b", re.IGNORECASE)
URL_PATTERN = re.compile(r"https?://[^\s<>\"']+")


def _parse_hn_comment(text: str) -> dict:
    """Parse an HN hiring comment into structured fields.

    Most comments follow: Company | Role | Location | Remote | Salary | URL
    """
    result = {
        "company": "",
        "role": "",
        "location": "",
        "remote": False,
        "salary_min": None,
        "salary_max": None,
        "url": "",
    }

    if not text:
        return result

    # Strip HTML
    clean = re.sub(r"<[^>]+>", "\n", text)
    clean = re.sub(r"&[a-z]+;", " ", clean)
    lines = [l.strip() for l in clean.split("\n") if l.strip()]
    if not lines:
        return result

    first_line = lines[0]

    # Try pipe-delimited format
    parts = [p.strip() for p in first_line.split("|")]
    if len(parts) >= 2:
        result["company"] = parts[0][:100]
        result["role"] = parts[1][:200]
        if len(parts) >= 3:
            result["location"] = parts[2][:200]
    else:
        # Fallback: first line might just be company name
        result["company"] = first_line[:100]

    # Check for remote
    full_text = "\n".join(lines)
    if REMOTE_PATTERN.search(full_text):
        result["remote"] = True

    # Extract salary
    m = SALARY_PATTERN.search(full_text)
    if m:
        try:
            lo = float(m.group(1).replace(",", ""))
            hi = float(m.group(2).replace(",", ""))
            if lo < 1000:
                lo *= 1000
            if hi < 1000:
                hi *= 1000
            result["salary_min"] = lo
            result["salary_max"] = hi
        except (ValueError, TypeError):
            pass

    # Extract URL
    url_match = URL_PATTERN.search(full_text)
    if url_match:
        result["url"] = url_match.group(0)

    return result


class HNHiringScraper(BaseScraper):
    """Scrapes the monthly HN 'Who is Hiring' thread comments."""

    def __init__(self):
        super().__init__(
            scraper_name="hn_hiring_scraper",
            request_delay=HN_HIRING_SCRAPE_CONFIG.get("request_delay", 0.2),
        )

    async def scrape(self, **kwargs):
        algolia_url = HN_HIRING_SCRAPE_CONFIG["algolia_url"]
        max_comments = HN_HIRING_SCRAPE_CONFIG.get("max_comments", 500)
        self.log.info("hn_hiring_scrape_start")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Find the latest "Who is hiring" thread
            thread_id = await self._find_latest_thread(client, algolia_url)
            if not thread_id:
                self.log.warning("hn_hiring_no_thread_found")
                return

            self.log.info("hn_hiring_thread_found", thread_id=thread_id)

            # Step 2: Fetch comments from that thread
            await self._fetch_comments(client, algolia_url, thread_id, max_comments)

        self.log.info(
            "hn_hiring_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _find_latest_thread(
        self, client: httpx.AsyncClient, algolia_url: str
    ) -> str | None:
        """Find the most recent 'Who is hiring' Ask HN thread."""
        try:
            response = await client.get(
                f"{algolia_url}/search",
                params={
                    "query": '"Ask HN: Who is hiring"',
                    "tags": "ask_hn",
                    "hitsPerPage": 5,
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
        except Exception as e:
            self.log.error("hn_hiring_thread_search_failed", error=str(e))
            return None

        data = response.json()
        hits = data.get("hits", [])

        for hit in hits:
            title = hit.get("title", "")
            if "who is hiring" in title.lower():
                return hit.get("objectID")

        return None

    async def _fetch_comments(
        self,
        client: httpx.AsyncClient,
        algolia_url: str,
        thread_id: str,
        max_comments: int,
    ):
        """Paginate through comments on the hiring thread."""
        page = 0
        fetched = 0
        hits_per_page = 100

        while fetched < max_comments:
            try:
                response = await client.get(
                    f"{algolia_url}/search",
                    params={
                        "tags": f"comment,story_{thread_id}",
                        "hitsPerPage": hits_per_page,
                        "page": page,
                    },
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
            except Exception as e:
                self.log.warning("hn_hiring_comments_failed", page=page, error=str(e))
                break

            data = response.json()
            hits = data.get("hits", [])
            if not hits:
                break

            for hit in hits:
                comment_text = hit.get("comment_text", "")
                if not comment_text or len(comment_text) < 20:
                    continue

                # Skip reply comments (top-level only)
                if hit.get("parent_id") and str(hit.get("parent_id")) != thread_id:
                    continue

                parsed = _parse_hn_comment(comment_text)
                company = parsed["company"]
                role = parsed["role"]

                if not company:
                    continue

                comment_id = hit.get("objectID", "")
                hn_url = f"https://news.ycombinator.com/item?id={comment_id}"

                published_at = None
                created = hit.get("created_at", "")
                if created:
                    try:
                        published_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass

                title = f"{role} at {company}" if role else f"Job at {company}"

                # Clean description
                description = re.sub(r"<[^>]+>", "\n", comment_text)
                description = re.sub(r"&[a-z]+;", " ", description)
                description = re.sub(r"\s+", " ", description).strip()

                await self.upsert_job_listing(
                    source="hn_hiring",
                    title=title,
                    url=hn_url,
                    company=company,
                    location=parsed["location"],
                    remote=parsed["remote"],
                    salary_min=parsed["salary_min"],
                    salary_max=parsed["salary_max"],
                    salary_currency="USD" if parsed["salary_min"] else "",
                    description=description,
                    apply_url=parsed["url"] or hn_url,
                    published_at=published_at,
                    raw_metadata={
                        "hn_comment_id": comment_id,
                        "thread_id": thread_id,
                    },
                )
                self.records_fetched += 1
                fetched += 1

            page += 1
            await self.rate_limit()
