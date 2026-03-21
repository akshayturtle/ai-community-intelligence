"""Hugging Face scraper -- fetches trending models, top downloads, and spaces. No API key needed."""

from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config.sources import HF_PIPELINE_TAGS, HF_SCRAPE_CONFIG
from database.connection import async_session, HFModel
from scrapers.base_scraper import BaseScraper, _utc_naive

logger = structlog.get_logger()

HF_API_BASE = "https://huggingface.co/api"


class HuggingFaceScraper(BaseScraper):
    """Scrapes Hugging Face for trending models, top downloads, and spaces."""

    def __init__(self):
        super().__init__(
            scraper_name="huggingface_scraper",
            request_delay=HF_SCRAPE_CONFIG["request_delay"],
        )

    # ------------------------------------------------------------------
    # Main scrape entry point
    # ------------------------------------------------------------------

    async def scrape(self, **kwargs):
        """Fetch models (trending, most downloaded, per-pipeline) and trending spaces."""
        models_limit = HF_SCRAPE_CONFIG["models_per_query"]
        spaces_limit = HF_SCRAPE_CONFIG["spaces_limit"]

        self.log.info(
            "hf_scrape_start",
            models_limit=models_limit,
            spaces_limit=spaces_limit,
            pipeline_tags=len(HF_PIPELINE_TAGS),
        )

        seen_model_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Trending models
            await self._fetch_models(
                client, params={"sort": "trending", "direction": "-1", "limit": models_limit},
                label="trending", seen=seen_model_ids,
            )

            # 2. Most downloaded models
            await self._fetch_models(
                client, params={"sort": "downloads", "direction": "-1", "limit": models_limit},
                label="most_downloaded", seen=seen_model_ids,
            )

            # 3. Models by pipeline tag
            for tag in HF_PIPELINE_TAGS:
                await self._fetch_models(
                    client,
                    params={
                        "pipeline_tag": tag,
                        "sort": "trending",
                        "direction": "-1",
                        "limit": models_limit,
                    },
                    label=f"pipeline_{tag}",
                    seen=seen_model_ids,
                )

            # 4. Trending spaces
            await self._fetch_spaces(client, limit=spaces_limit)

        self.log.info(
            "hf_scrape_complete",
            fetched=self.records_fetched,
            new=self.records_new,
            updated=self.records_updated,
        )

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    async def _fetch_models(
        self,
        client: httpx.AsyncClient,
        params: dict,
        label: str,
        seen: set[str],
    ):
        """Fetch a list of models from the HF API and upsert them."""
        url = f"{HF_API_BASE}/models"
        self.log.info("hf_fetch_models", label=label, params=params)

        try:
            response = await self.fetch_url(client, url + "?" + "&".join(f"{k}={v}" for k, v in params.items()))
        except Exception as e:
            self.log.warning("hf_models_fetch_failed", label=label, error=str(e))
            return

        await self.rate_limit()

        models = response.json()
        if not isinstance(models, list):
            self.log.warning("hf_unexpected_response", label=label)
            return

        self.log.info("hf_models_received", label=label, count=len(models))

        for model_data in models:
            model_id = model_data.get("modelId") or model_data.get("id")
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)

            await self._upsert_model(model_data, model_id)

    async def _upsert_model(self, data: dict, model_id: str):
        """Upsert a single model into the hf_models table."""
        downloads = data.get("downloads", 0) or 0
        likes = data.get("likes", 0) or 0
        pipeline_tag = data.get("pipeline_tag")
        tags = data.get("tags") or []
        library_name = data.get("library_name")
        trending_score = data.get("trendingScore") or data.get("trending_score")

        # Parse last_modified
        last_modified = None
        raw_last_modified = data.get("lastModified") or data.get("last_modified")
        if raw_last_modified:
            try:
                last_modified = _utc_naive(datetime.fromisoformat(raw_last_modified.replace("Z", "+00:00")))
            except (ValueError, AttributeError):
                pass

        # Calculate downloads_last_week by comparing with existing record
        downloads_last_week = await self._calc_downloads_last_week(model_id, downloads)

        now = _utc_naive()

        async with async_session() as session:
            stmt = pg_insert(HFModel).values(
                model_id=model_id,
                pipeline_tag=pipeline_tag,
                downloads=downloads,
                likes=likes,
                tags=tags,
                library_name=library_name,
                last_modified=last_modified,
                downloads_last_week=downloads_last_week,
                trending_score=trending_score,
                raw_metadata=data,
                first_scraped_at=now,
                last_scraped_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["model_id"],
                set_={
                    "pipeline_tag": stmt.excluded.pipeline_tag,
                    "downloads": stmt.excluded.downloads,
                    "likes": stmt.excluded.likes,
                    "tags": stmt.excluded.tags,
                    "library_name": stmt.excluded.library_name,
                    "last_modified": stmt.excluded.last_modified,
                    "downloads_last_week": stmt.excluded.downloads_last_week,
                    "trending_score": stmt.excluded.trending_score,
                    "raw_metadata": stmt.excluded.raw_metadata,
                    "last_scraped_at": stmt.excluded.last_scraped_at,
                },
            )
            result = await session.execute(stmt)
            await session.commit()

        self.records_fetched += 1
        if result.rowcount > 0:
            # Determine new vs updated by checking if first_scraped_at was set
            # (on_conflict_do_update means it already existed)
            if downloads_last_week is None:
                self.records_new += 1
            else:
                self.records_updated += 1

        self.log.debug("hf_model_upserted", model_id=model_id, downloads=downloads, likes=likes)

    async def _calc_downloads_last_week(self, model_id: str, current_downloads: int) -> int | None:
        """Compare current downloads with previously stored value to estimate weekly delta."""
        async with async_session() as session:
            result = await session.execute(
                select(HFModel.downloads, HFModel.last_scraped_at).where(
                    HFModel.model_id == model_id
                )
            )
            row = result.one_or_none()
            if row is None:
                return None

            prev_downloads, last_scraped_at = row
            if prev_downloads is None:
                return None

            delta = current_downloads - prev_downloads
            return max(delta, 0)

    # ------------------------------------------------------------------
    # Spaces
    # ------------------------------------------------------------------

    async def _fetch_spaces(self, client: httpx.AsyncClient, limit: int):
        """Fetch trending HF Spaces and store as news events."""
        url = f"{HF_API_BASE}/spaces?sort=trending&direction=-1&limit={limit}"
        self.log.info("hf_fetch_spaces", limit=limit)

        try:
            response = await self.fetch_url(client, url)
        except Exception as e:
            self.log.warning("hf_spaces_fetch_failed", error=str(e))
            return

        await self.rate_limit()

        spaces = response.json()
        if not isinstance(spaces, list):
            self.log.warning("hf_spaces_unexpected_response")
            return

        self.log.info("hf_spaces_received", count=len(spaces))

        for space in spaces:
            space_id = space.get("id", "")
            if not space_id:
                continue

            title = space_id.split("/")[-1] if "/" in space_id else space_id
            owner = space_id.split("/")[0] if "/" in space_id else ""
            space_url = f"https://huggingface.co/spaces/{space_id}"

            # Parse creation/modification time
            created_at_raw = space.get("createdAt") or space.get("created_at")
            published_at = None
            if created_at_raw:
                try:
                    published_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            sdk = space.get("sdk", "")
            likes = space.get("likes", 0)
            tags = space.get("tags") or []

            await self.upsert_news_event(
                source_type="huggingface_space",
                source_name="Hugging Face Spaces",
                title=f"{title} by {owner}" if owner else title,
                body=space.get("cardData", {}).get("short_description") or space.get("description") or "",
                url=space_url,
                authors=[owner] if owner else None,
                published_at=published_at,
                categories=tags[:20] if tags else None,
                raw_metadata={
                    "space_id": space_id,
                    "sdk": sdk,
                    "likes": likes,
                    "tags": tags,
                    "trending_score": space.get("trendingScore"),
                },
            )
            self.records_fetched += 1

        self.log.info("hf_spaces_done", count=len(spaces))
