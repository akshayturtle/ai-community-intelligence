"""Y Combinator company scraper — fetches batch data from yc-oss API. No API key needed."""

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.sources import YC_SCRAPE_CONFIG
from database.connection import YCCompany, async_session
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

YC_API_BASE = "https://yc-oss.github.io/api/batches"


class YCScraper(BaseScraper):
    """Scrapes Y Combinator company data from the yc-oss open API."""

    def __init__(self):
        super().__init__(
            scraper_name="yc_scraper",
            request_delay=1.0,
        )

    async def scrape(
        self,
        latest_batch: str | None = None,
        **kwargs,
    ):
        """Scrape all YC companies and highlight the latest batch."""
        batch = latest_batch or YC_SCRAPE_CONFIG["latest_batch"]

        self.log.info("yc_scrape_start", latest_batch=batch)

        async with httpx.AsyncClient(timeout=60.0) as client:
            await self._scrape_all_companies(client)
            await self.rate_limit()
            await self._scrape_batch(client, batch)

        self.log.info(
            "yc_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
        )

    # ------------------------------------------------------------------
    # All companies
    # ------------------------------------------------------------------

    async def _scrape_all_companies(self, client: httpx.AsyncClient):
        """Fetch the full list of YC companies."""
        url = f"{YC_API_BASE}/all.json"
        self.log.info("fetching_all_yc_companies")

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("yc_all_fetch_failed", error=str(e))
            return

        companies = response.json()
        if not isinstance(companies, list):
            self.log.warning("yc_unexpected_format", type=type(companies).__name__)
            return

        for company in companies:
            await self._upsert_company(company)

        self.log.info("all_companies_done", count=len(companies))

    # ------------------------------------------------------------------
    # Single batch
    # ------------------------------------------------------------------

    async def _scrape_batch(self, client: httpx.AsyncClient, batch: str):
        """Fetch companies from a specific YC batch."""
        url = f"{YC_API_BASE}/{batch}.json"
        self.log.info("fetching_yc_batch", batch=batch)

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("yc_batch_fetch_failed", batch=batch, error=str(e))
            return

        companies = response.json()
        if not isinstance(companies, list):
            self.log.warning("yc_batch_unexpected_format", batch=batch, type=type(companies).__name__)
            return

        for company in companies:
            await self._upsert_company(company, batch_override=batch)

        self.log.info("batch_done", batch=batch, count=len(companies))

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def _upsert_company(self, company: dict, batch_override: str | None = None):
        """Insert or update a YC company record."""
        slug = (company.get("slug") or "").strip()
        if not slug:
            return

        name = (company.get("name") or "").strip()
        now = _utc_naive()

        # Build values dict, keeping only non-None fields from the API
        values = {
            "slug": slug,
            "name": name or slug,
            "description": company.get("one_liner") or company.get("description"),
            "long_description": company.get("long_description"),
            "batch": batch_override or company.get("batch"),
            "status": company.get("status"),
            "industries": company.get("industries") or company.get("tags"),
            "regions": company.get("regions"),
            "team_size": str(company.get("team_size")) if company.get("team_size") else None,
            "website": company.get("website") or company.get("url"),
            "raw_metadata": {
                k: v
                for k, v in company.items()
                if k not in ("slug", "name", "one_liner", "description", "long_description",
                             "batch", "status", "industries", "tags", "regions",
                             "team_size", "website", "url")
                and v is not None
            },
            "updated_at": now,
        }

        async with async_session() as session:
            stmt = pg_insert(YCCompany).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "long_description": stmt.excluded.long_description,
                    "batch": stmt.excluded.batch,
                    "status": stmt.excluded.status,
                    "industries": stmt.excluded.industries,
                    "regions": stmt.excluded.regions,
                    "team_size": stmt.excluded.team_size,
                    "website": stmt.excluded.website,
                    "raw_metadata": stmt.excluded.raw_metadata,
                    "updated_at": now,
                },
            )
            result = await session.execute(stmt)
            await session.commit()

            self.records_fetched += 1
            if result.rowcount > 0:
                self.records_new += 1
