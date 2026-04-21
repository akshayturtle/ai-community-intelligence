"""CrossSourceOrchestrator — Runs all signal agents and then the synthesizer."""

import asyncio
import json
import re
import time
from datetime import datetime

import asyncpg
import structlog

from agents.signal_agents.research_pipeline import create_research_pipeline_agent, run_research_pipeline
from agents.signal_agents.traction_scorer import create_traction_scorer_agent, run_traction_scorer
from agents.signal_agents.market_gap_detector import create_market_gap_agent, run_market_gap_detector
from agents.signal_agents.competitive_threat import create_competitive_threat_agent, run_competitive_threat
from agents.signal_agents.divergence_detector import create_divergence_agent, run_divergence_detector
from agents.signal_agents.lifecycle_mapper import create_lifecycle_agent, run_lifecycle_mapper
from agents.signal_agents.smart_money_tracker import create_smart_money_agent, run_smart_money_tracker
from agents.signal_agents.talent_flow import create_talent_flow_agent, run_talent_flow
from agents.signal_agents.product_discoverer import create_product_discoverer_agent
from agents.signal_agents.narrative_shift import create_narrative_shift_agent, run_narrative_shift
from agents.signal_agents.freelance_market import run as run_freelance_market
from agents.synthesizer.insight_synthesizer import create_insight_synthesizer_agent
from agents.config import DATABASE_URL

# Pre-fetch agents — these use Python to gather data, then pass to LLM in one shot
# (much faster and more reliable than making the LLM call SQL tools 100+ times)
PREFETCH_AGENTS = {
    "research_pipeline": run_research_pipeline,
    "traction_scorer": run_traction_scorer,
    "market_gap_detector": run_market_gap_detector,
    "competitive_threat": run_competitive_threat,
    "divergence_detector": run_divergence_detector,
    "lifecycle_mapper": run_lifecycle_mapper,
    "smart_money_tracker": run_smart_money_tracker,
    "talent_flow": run_talent_flow,
    "narrative_shift": run_narrative_shift,
    "freelance_market": run_freelance_market,
}

logger = structlog.get_logger()


def _extract_json(text: str):
    """Extract JSON array or object from agent text output.

    Agents often wrap their JSON in markdown fences or include narrative before/after.
    This tries multiple strategies to find valid JSON.
    """
    if not text:
        return None

    # Normalize whitespace — some models output tabs that break JSON
    text = text.replace("\t", "  ")

    # Strategy 1: Try parsing the whole thing directly
    try:
        data = json.loads(text)
        return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: Find JSON in markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 3: Find the largest JSON array [...] or object {...}
    # Look for array first (most agents output arrays)
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Find the matching closing bracket by counting nesting
        depth = 0
        best_end = -1
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    best_end = i
                    break
        if best_end > start_idx:
            candidate = text[start_idx : best_end + 1]
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                pass

    return None

# Map agent names to their result tables for structured storage
TABLE_MAP = {
    "research_pipeline": "research_pipeline",
    "traction_scorer": "traction_scores",
    "market_gap_detector": "market_gaps",
    "competitive_threat": "competitive_threats",
    "divergence_detector": "platform_divergence",
    "lifecycle_mapper": "technology_lifecycle",
    "narrative_shift": "narrative_shifts",
    "smart_money_tracker": "smart_money",
    "talent_flow": "talent_flow",
}

# All agent creators
AGENT_CREATORS = {
    "research_pipeline": create_research_pipeline_agent,
    "traction_scorer": create_traction_scorer_agent,
    "market_gap_detector": create_market_gap_agent,
    "competitive_threat": create_competitive_threat_agent,
    "divergence_detector": create_divergence_agent,
    "lifecycle_mapper": create_lifecycle_agent,
    "smart_money_tracker": create_smart_money_agent,
    "talent_flow": create_talent_flow_agent,
    "product_discoverer": create_product_discoverer_agent,
    "narrative_shift": create_narrative_shift_agent,
    "insight_synthesizer": create_insight_synthesizer_agent,
}


class CrossSourceOrchestrator:
    """Runs all signal agents and then the synthesizer."""

    def __init__(self, db_url: str | None = None):
        self.db_url = db_url or DATABASE_URL

    async def run_all_signals(self) -> dict:
        """Run all signal agents in groups, then the synthesizer."""
        today = datetime.now().strftime("%Y-%m-%d")
        trigger = f"Analyze the current data and produce your signal report. Today is {today}."

        results = {}

        # Group 1: Independent agents (parallel)
        # Some use pre-fetch (Python gathers data), others use tool-based approach
        group1_names = [
            "research_pipeline", "traction_scorer", "market_gap_detector",
            "divergence_detector", "lifecycle_mapper", "talent_flow",
            "product_discoverer", "narrative_shift",
        ]

        logger.info("orchestrator_group1_start", agents=len(group1_names))

        async def _run_one(name):
            if name in PREFETCH_AGENTS:
                return await self._run_prefetch_agent(name)
            agent = AGENT_CREATORS[name]()
            return await self._run_agent(name, agent, trigger)

        tasks = [_run_one(name) for name in group1_names]
        group1_results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(group1_names, group1_results):
            if isinstance(result, Exception):
                logger.error("agent_failed", agent=name, error=str(result))
                results[name] = None
            else:
                results[name] = result

        # Group 2: Depends on group 1
        group2 = [
            ("competitive_threat", create_competitive_threat_agent()),
            ("smart_money_tracker", create_smart_money_agent()),
        ]

        logger.info("orchestrator_group2_start", agents=len(group2))
        for name, agent in group2:
            try:
                result = await self._run_agent(name, agent, trigger)
                results[name] = result
            except Exception as e:
                logger.error("agent_failed", agent=name, error=str(e))
                results[name] = None

        # Group 3: Synthesizer runs LAST
        logger.info("orchestrator_synthesizer_start")
        try:
            synthesizer = create_insight_synthesizer_agent()
            insights = await self._run_agent(
                "insight_synthesizer",
                synthesizer,
                "Read all cross-source signal tables and produce actionable insight cards.",
            )
            results["insight_synthesizer"] = insights
        except Exception as e:
            logger.error("synthesizer_failed", error=str(e))

        logger.info("orchestrator_complete", agents_run=len(results))
        return results

    async def run_single(self, agent_name: str) -> str:
        """Run a single agent by name."""
        # Pre-fetch agents (pure-Python data gathering + one LLM call)
        if agent_name in PREFETCH_AGENTS:
            return await self._run_prefetch_agent(agent_name)

        if agent_name not in AGENT_CREATORS:
            raise ValueError(
                f"Unknown agent: {agent_name}. Available: "
                f"{sorted(set(list(AGENT_CREATORS.keys()) + list(PREFETCH_AGENTS.keys())))}"
            )

        agent = AGENT_CREATORS[agent_name]()
        today = datetime.now().strftime("%Y-%m-%d")
        result = await self._run_agent(
            agent_name, agent, f"Run your analysis. Today is {today}."
        )
        return result

    async def _run_prefetch_agent(self, name: str) -> str:
        """Run a pre-fetch agent: Python gathers data, LLM analyzes in one shot."""
        start = time.time()
        logger.info("agent_start", agent=name, mode="prefetch")
        try:
            content = await PREFETCH_AGENTS[name]()
            duration = time.time() - start

            await self._store_agent_run(name, content, duration, None, None, "success")

            if name in TABLE_MAP:
                await self._store_structured(name, content)
            else:
                await self._store_output_json(name, content)

            logger.info("agent_complete", agent=name, duration=f"{duration:.1f}s")
            return content
        except Exception as e:
            duration = time.time() - start
            await self._store_agent_run(name, str(e), duration, None, None, "failed")
            raise

    async def _run_agent(self, name: str, agent, message: str) -> str:
        """Run an agent, store results, and log to agent_runs."""
        start = time.time()
        logger.info("agent_start", agent=name)

        try:
            response = await agent.arun(message)
            content = response.content
            duration = time.time() - start

            # Extract token usage if available
            tokens_used = None
            cost_usd = None
            if hasattr(response, "metrics") and response.metrics:
                metrics = response.metrics
                tokens_used = getattr(metrics, "total_tokens", None)
                cost_usd = getattr(metrics, "total_cost", None)

            # Store raw result in agent_runs
            await self._store_agent_run(
                name, content, duration, tokens_used, cost_usd, "success"
            )

            # Store structured results — signal tables for TABLE_MAP agents,
            # output_json for ALL agents that produce JSON
            if name in TABLE_MAP:
                await self._store_structured(name, content)
            else:
                # Still try to extract and store JSON for non-signal agents
                await self._store_output_json(name, content)

            logger.info(
                "agent_complete",
                agent=name,
                duration=f"{duration:.1f}s",
                tokens=tokens_used,
            )
            return content

        except Exception as e:
            duration = time.time() - start
            await self._store_agent_run(name, str(e), duration, None, None, "failed")
            raise

    async def _store_agent_run(
        self,
        agent_name: str,
        output: str,
        duration: float,
        tokens: int | None,
        cost: float | None,
        status: str,
    ):
        """Log agent run to agent_runs table."""
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                """
                INSERT INTO agent_runs (agent_name, status, output, duration_seconds,
                                        tokens_used, cost_usd, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                agent_name,
                status,
                output[:50000] if output else None,  # Truncate very long outputs
                duration,
                tokens,
                cost,
            )
        except Exception as e:
            logger.error("agent_run_store_failed", agent=agent_name, error=str(e))
        finally:
            await conn.close()

    async def _store_output_json(self, agent_name: str, raw_output: str):
        """Extract JSON and store in agent_runs.output_json (no signal table)."""
        data = _extract_json(raw_output)
        if data is None:
            return
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute(
                """
                UPDATE agent_runs SET output_json = $1::jsonb, records_produced = $2
                WHERE id = (SELECT id FROM agent_runs WHERE agent_name = $3
                            ORDER BY started_at DESC LIMIT 1)
                """,
                json.dumps(data, default=str),
                len(data) if isinstance(data, list) else 1,
                agent_name,
            )
        except Exception as e:
            logger.error("output_json_store_failed", agent=agent_name, error=str(e))
        finally:
            await conn.close()

    async def _store_structured(self, agent_name: str, raw_output: str):
        """Parse agent JSON output, store in output_json, and INSERT into signal tables."""
        data = _extract_json(raw_output)
        if data is None:
            logger.warning("json_extract_failed", agent=agent_name)
            return

        conn = await asyncpg.connect(self.db_url)
        try:
            # 1) Update agent_runs.output_json
            await conn.execute(
                """
                UPDATE agent_runs SET output_json = $1::jsonb, records_produced = $2
                WHERE id = (SELECT id FROM agent_runs WHERE agent_name = $3
                            ORDER BY started_at DESC LIMIT 1)
                """,
                json.dumps(data, default=str),
                len(data) if isinstance(data, list) else 1,
                agent_name,
            )

            # 2) INSERT into the corresponding signal table
            table = TABLE_MAP.get(agent_name)
            if not table:
                return

            rows = data if isinstance(data, list) else [data]
            if not rows:
                return

            # Clear stale data for this signal (replace with fresh analysis)
            await conn.execute(f"DELETE FROM {table}")

            inserted = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    await self._insert_signal_row(conn, table, agent_name, row)
                    inserted += 1
                except Exception as e:
                    logger.warning("signal_row_insert_failed", table=table, error=str(e))

            # Update records_produced with actual inserted count
            if inserted > 0:
                await conn.execute(
                    """
                    UPDATE agent_runs SET records_produced = $1
                    WHERE id = (SELECT id FROM agent_runs WHERE agent_name = $2
                                ORDER BY started_at DESC LIMIT 1)
                    """,
                    inserted,
                    agent_name,
                )

            logger.info("signal_table_updated", agent=agent_name, table=table, rows=inserted)

        except Exception as e:
            logger.error("store_structured_failed", agent=agent_name, error=str(e))
        finally:
            await conn.close()

    async def _insert_signal_row(
        self, conn, table: str, agent_name: str, row: dict
    ):
        """Insert a single row into a signal table, mapping agent output fields to columns."""
        # Column mappings per table — map agent output keys to DB columns
        COLUMN_MAPS = {
            "research_pipeline": {
                "paper_title": "paper_title",
                "arxiv_id": "arxiv_id",
                "published_at": "published_at",
                "github_repos": "github_repos",  # JSONB
                "hf_total_downloads": "hf_total_downloads",
                "community_mention_count": "community_mention_count",
                "community_sentiment": "community_sentiment",
                "ph_launches": "ph_launches",  # JSONB
                "so_question_count": "so_question_count",
                "current_stage": "current_stage",
                "pipeline_velocity": "pipeline_velocity",
                "days_paper_to_code": "days_paper_to_code",
                "days_total_pipeline": "days_total_pipeline",
            },
            "traction_scores": {
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "ph_votes": "ph_votes",
                "gh_stars": "gh_stars",
                "gh_star_velocity": "gh_star_velocity",
                "gh_non_founder_contributors": "gh_non_founder_contributors",
                "pypi_monthly_downloads": "pypi_monthly_downloads",
                "npm_monthly_downloads": "npm_monthly_downloads",
                "organic_mentions": "organic_mentions",
                "self_promo_mentions": "self_promo_mentions",
                "job_listings": "job_listings",
                "recommendation_rate": "recommendation_rate",
                "traction_score": "traction_score",
                "traction_label": "traction_label",
                "score_breakdown": "score_breakdown",  # JSONB
                "red_flags": "red_flags",  # JSONB
                "reasoning": "reasoning",
            },
            "technology_lifecycle": {
                "technology": "technology_name",
                "technology_name": "technology_name",
                "current_stage": "current_stage",
                "evidence": "stage_evidence",  # JSONB
                "stage_evidence": "stage_evidence",
                "arxiv_paper_count": "arxiv_paper_count",
                "github_repo_count": "github_repo_count",
                "hf_model_count": "hf_model_count",
                "so_question_count": "so_question_count",
                "job_listing_count": "job_listing_count",
                "community_mention_count": "community_mention_count",
            },
            "market_gaps": {
                "problem_title": "problem_title",
                "pain_score": "pain_score",
                "complaint_count": "complaint_count",
                "existing_products": "existing_products",
                "existing_product_names": "existing_product_names",  # JSONB
                "total_funding_in_space": "total_funding_in_space",
                "funded_startups": "funded_startups",  # JSONB
                "job_postings_related": "job_postings_related",
                "yc_batch_presence": "yc_batch_presence",
                "gap_signal": "gap_signal",
                "opportunity_score": "opportunity_score",
                "reasoning": "reasoning",
            },
            "competitive_threats": {
                "target_product": "target_product",
                "competitor": "competitor",
                "name": "competitor",  # alias
                "migrations_away": "migrations_away",
                "migrations_from_target": "migrations_away",  # alias
                "competitor_gh_velocity": "competitor_gh_velocity",
                "gh_star_velocity": "competitor_gh_velocity",  # alias
                "competitor_hiring": "competitor_hiring",
                "hiring_count": "competitor_hiring",  # alias
                "competitor_sentiment": "competitor_sentiment",
                "avg_sentiment": "competitor_sentiment",  # alias
                "opinion_leaders_flipped": "opinion_leaders_flipped",
                "threat_score": "threat_score",
                "threat_summary": "threat_summary",
                "summary": "threat_summary",  # alias
            },
            "platform_divergence": {
                "topic_name": "topic_name",
                "reddit_sentiment": "reddit_sentiment",
                "hn_sentiment": "hn_sentiment",
                "youtube_sentiment": "youtube_sentiment",
                "ph_sentiment": "ph_sentiment",
                "max_divergence": "max_divergence",
                "divergence_score": "max_divergence",  # alias
                "divergence_direction": "divergence_direction",
                "prediction": "prediction",
                "status": "status",
                "signal_type": "status",  # alias
            },
            "narrative_shifts": {
                "topic_name": "topic_name",
                "topic_id": "topic_id",
                "shift_type": "shift_type",
                "shift_velocity": "shift_velocity",
                "older_frame": "older_frame",
                "recent_frame": "recent_frame",
                "media_alignment": "media_alignment",
                "prediction": "prediction",
                "confidence": "confidence",
                "narrative_timeline": "narrative_timeline",  # JSONB
            },
            "smart_money": {
                "sector": "sector",
                "yc_companies_last_batch": "yc_companies_last_batch",
                "yc_trend": "yc_trend",
                "yc_percentage_of_batch": "yc_percentage_of_batch",
                "vc_funding_articles": "vc_funding_articles",
                "vc_signal": "vc_signal",
                "builder_repos": "builder_repos",
                "builder_stars": "builder_stars",
                "community_posts_30d": "community_posts_30d",
                "classification": "classification",
                "reasoning": "reasoning",
            },
            "talent_flow": {
                "skill": "skill",
                "category": "category",
                "demand_score": "demand_score",
                "supply_score": "supply_score",
                "gap": "gap",
                "salary_pressure": "salary_pressure",
                "trend": "trend",
                "job_listings_30d": "job_listings_30d",
                "so_questions_30d": "so_questions_30d",
                "reasoning": "reasoning",
                "prediction": "prediction",
            },
        }

        JSONB_COLS = {
            "github_repos", "ph_launches", "score_breakdown", "red_flags",
            "stage_evidence", "existing_product_names", "funded_startups",
            "community_sentiment_trajectory", "pypi_download_trend",
            "hf_model_ids", "narrative_timeline",
        }

        col_map = COLUMN_MAPS.get(table, {})

        # competitive_threats has nested structure: expand competitors array
        if table == "competitive_threats" and "competitors" in row:
            target = row.get("target_product", "")
            category = row.get("category", "")
            for comp in row["competitors"]:
                if isinstance(comp, dict):
                    comp["target_product"] = target
                    comp["category"] = category
                    await self._insert_signal_row(conn, table, agent_name, comp)
            return

        # Map agent output keys to DB column names
        mapped = {}
        for src_key, val in row.items():
            db_col = col_map.get(src_key)
            if db_col and val is not None:
                mapped[db_col] = val

        # Handle divergence platforms dict → flat columns
        if table == "platform_divergence" and "platforms" in row:
            platforms = row["platforms"]
            if isinstance(platforms, dict):
                for plat, pdata in platforms.items():
                    sent = pdata.get("avg_sentiment", 0) if isinstance(pdata, dict) else 0
                    plat_lower = plat.lower()
                    if "reddit" in plat_lower:
                        mapped["reddit_sentiment"] = sent
                    elif "hacker" in plat_lower or "hn" in plat_lower:
                        mapped["hn_sentiment"] = sent
                    elif "youtube" in plat_lower:
                        mapped["youtube_sentiment"] = sent
                    elif "product" in plat_lower or "ph" in plat_lower:
                        mapped["ph_sentiment"] = sent

        # Handle narrative_shifts: extract older/recent frames from timeline
        if table == "narrative_shifts" and "narrative_timeline" in row:
            timeline = row["narrative_timeline"]
            if isinstance(timeline, list):
                for entry in timeline:
                    if isinstance(entry, dict):
                        period = entry.get("period", "").lower()
                        frame = entry.get("dominant_frame", "")
                        if "older" in period or "past" in period:
                            mapped.setdefault("older_frame", frame)
                        elif "recent" in period or "current" in period:
                            mapped.setdefault("recent_frame", frame)

        # Handle lifecycle evidence dict → flat columns
        if table == "technology_lifecycle" and ("evidence" in row or "stage_evidence" in row):
            ev = row.get("evidence") or row.get("stage_evidence")
            if isinstance(ev, dict):
                mapped.setdefault("arxiv_paper_count", ev.get("arxiv_papers", 0))
                mapped.setdefault("github_repo_count", ev.get("github_repos", 0))
                mapped.setdefault("hf_model_count", ev.get("hf_models", 0))
                mapped.setdefault("so_question_count", ev.get("so_questions", 0))
                mapped.setdefault("job_listing_count", ev.get("job_listings", 0))
                mapped.setdefault("community_mention_count", ev.get("community_posts_30d", 0))
                mapped.setdefault("stage_evidence", ev)

        if not mapped:
            return

        # Parse date strings to datetime objects for timestamp columns
        DATE_COLS = {"published_at", "calculated_at", "detected_at", "created_at"}
        for col in list(mapped.keys()):
            val = mapped[col]
            if col in DATE_COLS and isinstance(val, str):
                try:
                    mapped[col] = datetime.fromisoformat(val.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    # Try date-only format
                    try:
                        from datetime import date as dt_date
                        mapped[col] = datetime.combine(
                            dt_date.fromisoformat(val), datetime.min.time()
                        )
                    except (ValueError, TypeError):
                        del mapped[col]  # Drop unparseable dates

        # Build INSERT
        cols = list(mapped.keys())
        placeholders = []
        values = []
        for i, col in enumerate(cols, 1):
            val = mapped[col]
            if col in JSONB_COLS:
                placeholders.append(f"${i}::jsonb")
                values.append(json.dumps(val, default=str) if not isinstance(val, str) else val)
            else:
                placeholders.append(f"${i}")
                values.append(val)

        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
        await conn.execute(sql, *values)
