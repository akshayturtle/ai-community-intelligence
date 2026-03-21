"""Package download scraper — tracks PyPI and npm download stats. No API key needed."""

from datetime import date, datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.sources import (
    NPM_PACKAGES_TO_TRACK,
    PACKAGE_SCRAPE_CONFIG,
    PYPI_PACKAGES_TO_TRACK,
)
from database.connection import PackageDownload, async_session
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()


class PackageScraper(BaseScraper):
    """Scrapes PyPI and npm for daily download statistics."""

    def __init__(self):
        super().__init__(
            scraper_name="package_scraper",
            request_delay=PACKAGE_SCRAPE_CONFIG["request_delay"],
        )

    async def scrape(
        self,
        pypi_packages: list[str] | None = None,
        npm_packages: list[str] | None = None,
        **kwargs,
    ):
        """Scrape download stats for PyPI and npm packages."""
        pypi = pypi_packages or PYPI_PACKAGES_TO_TRACK
        npm = npm_packages or NPM_PACKAGES_TO_TRACK

        self.log.info("package_scrape_start", pypi_count=len(pypi), npm_count=len(npm))

        async with httpx.AsyncClient(timeout=60.0) as client:
            for package in pypi:
                await self._scrape_pypi(client, package)
                await self.rate_limit()

            for package in npm:
                await self._scrape_npm(client, package)
                await self.rate_limit()

        self.log.info(
            "package_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
        )

    # ------------------------------------------------------------------
    # PyPI
    # ------------------------------------------------------------------

    async def _scrape_pypi(self, client: httpx.AsyncClient, package: str):
        """Fetch daily download stats for a PyPI package."""
        url = f"https://pypistats.org/api/packages/{package}/overall?mirrors=false"

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("pypi_fetch_failed", package=package, error=str(e))
            return

        data = response.json()
        entries = data.get("data", [])

        if not entries:
            self.log.debug("pypi_no_data", package=package)
            return

        # Aggregate daily totals from category breakdowns
        daily_totals: dict[str, int] = {}
        for entry in entries:
            entry_date = entry.get("date")
            downloads = entry.get("downloads", 0)
            if not entry_date:
                continue
            daily_totals[entry_date] = daily_totals.get(entry_date, 0) + downloads

        for day_str, total_downloads in daily_totals.items():
            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                continue

            await self._upsert_download(package, "pypi", day, total_downloads)

        self.log.info("pypi_done", package=package, days=len(daily_totals))

    # ------------------------------------------------------------------
    # npm
    # ------------------------------------------------------------------

    async def _scrape_npm(self, client: httpx.AsyncClient, package: str):
        """Fetch daily download stats for an npm package over the last 30 days."""
        end = date.today()
        start = end - timedelta(days=30)
        url = f"https://api.npmjs.org/downloads/range/{start}:{end}/{package}"

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("npm_fetch_failed", package=package, error=str(e))
            return

        data = response.json()
        downloads_list = data.get("downloads", [])

        if not downloads_list:
            self.log.debug("npm_no_data", package=package)
            return

        for entry in downloads_list:
            day_str = entry.get("day")
            downloads = entry.get("downloads", 0)
            if not day_str:
                continue

            try:
                day = date.fromisoformat(day_str)
            except ValueError:
                continue

            await self._upsert_download(package, "npm", day, downloads)

        self.log.info("npm_done", package=package, days=len(downloads_list))

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    async def _upsert_download(
        self, package_name: str, registry: str, download_date: date, downloads: int
    ):
        """Insert or update a daily download record."""
        async with async_session() as session:
            stmt = pg_insert(PackageDownload).values(
                package_name=package_name,
                registry=registry,
                date=download_date,
                downloads=downloads,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="package_downloads_package_name_registry_date_key",
                set_={
                    "downloads": stmt.excluded.downloads,
                },
            )
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount > 0:
                self.records_fetched += 1
                self.records_new += 1
