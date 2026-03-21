"""USAJobs scraper — free API, requires API key (registration)."""

from datetime import datetime

import httpx
import structlog

from config.sources import USAJOBS_SCRAPE_CONFIG
from config.settings import USAJOBS_API_KEY, USAJOBS_EMAIL, USER_AGENT
from scrapers.base_scraper import BaseScraper

logger = structlog.get_logger()


class USAJobsScraper(BaseScraper):
    """Scrapes job listings from USAJobs.gov API."""

    def __init__(self):
        super().__init__(
            scraper_name="usajobs_scraper",
            request_delay=USAJOBS_SCRAPE_CONFIG.get("request_delay", 1.0),
        )

    async def scrape(self, **kwargs):
        if not USAJOBS_API_KEY or not USAJOBS_EMAIL:
            self.log.warning(
                "usajobs_skipped",
                reason="USAJOBS_API_KEY or USAJOBS_EMAIL not set",
            )
            return

        api_url = USAJOBS_SCRAPE_CONFIG["api_url"]
        keywords = USAJOBS_SCRAPE_CONFIG.get("keywords", [])
        max_pages = USAJOBS_SCRAPE_CONFIG.get("max_pages", 5)

        self.log.info("usajobs_scrape_start", keywords=len(keywords))

        headers = {
            "Authorization-Key": USAJOBS_API_KEY,
            "User-Agent": USAJOBS_EMAIL,
            "Host": "data.usajobs.gov",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for keyword in keywords:
                await self._scrape_keyword(client, api_url, keyword, max_pages, headers)
                await self.rate_limit()

        self.log.info(
            "usajobs_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    async def _scrape_keyword(
        self,
        client: httpx.AsyncClient,
        api_url: str,
        keyword: str,
        max_pages: int,
        headers: dict,
    ):
        for page in range(1, max_pages + 1):
            self.log.debug("usajobs_page", keyword=keyword, page=page)

            try:
                response = await client.get(
                    api_url,
                    params={
                        "Keyword": keyword,
                        "ResultsPerPage": 25,
                        "Page": page,
                    },
                    headers=headers,
                )
                response.raise_for_status()
            except Exception as e:
                self.log.warning(
                    "usajobs_fetch_failed",
                    keyword=keyword,
                    page=page,
                    error=str(e),
                )
                break

            data = response.json()
            search_result = data.get("SearchResult", {})
            items = search_result.get("SearchResultItems", [])
            if not items:
                break

            for item in items:
                matched = item.get("MatchedObjectDescriptor", {})
                if not matched:
                    continue

                title_raw = matched.get("PositionTitle", "")
                org = matched.get("OrganizationName", "")
                if not title_raw:
                    continue

                job_url = matched.get("PositionURI", "")
                if not job_url:
                    apply_url_obj = matched.get("ApplyURI", [])
                    if apply_url_obj:
                        job_url = apply_url_obj[0] if isinstance(apply_url_obj, list) else str(apply_url_obj)
                if not job_url:
                    continue

                published_at = None
                start_date = matched.get("PositionStartDate", "")
                if start_date:
                    try:
                        published_at = datetime.fromisoformat(
                            start_date.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

                # Salary
                salary_min = None
                salary_max = None
                salary_currency = "USD"
                remuneration = matched.get("PositionRemuneration", [])
                if remuneration and isinstance(remuneration, list):
                    rem = remuneration[0]
                    try:
                        salary_min = float(rem.get("MinimumRange", 0))
                        salary_max = float(rem.get("MaximumRange", 0))
                    except (ValueError, TypeError):
                        pass

                location = matched.get("PositionLocationDisplay", "")
                description = matched.get("QualificationSummary", "")

                # Detect remote
                location_lower = (location or "").lower()
                is_remote = "remote" in location_lower or "telework" in location_lower

                title = f"{title_raw} at {org}" if org else title_raw

                await self.upsert_job_listing(
                    source="usajobs",
                    title=title,
                    url=job_url,
                    company=org,
                    location=location,
                    salary_min=salary_min if salary_min else None,
                    salary_max=salary_max if salary_max else None,
                    salary_currency=salary_currency,
                    remote=is_remote,
                    tags=[keyword, "government"],
                    description=description,
                    apply_url=job_url,
                    published_at=published_at,
                    raw_metadata={
                        "position_id": matched.get("PositionID"),
                        "department": matched.get("DepartmentName", ""),
                        "job_grade": matched.get("JobGrade", []),
                    },
                )
                self.records_fetched += 1

            # Check total results to know when to stop
            total = int(search_result.get("SearchResultCount", 0))
            if page * 25 >= total:
                break
            await self.rate_limit()
