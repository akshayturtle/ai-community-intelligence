"""Persona extractor — builds structured persona profiles from user posts via LLM."""

import asyncio
import json

import structlog
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.connection import async_session, User, Post, Persona
from processors.llm_client import call_llm, TokenUsage
from scrapers.base_scraper import _utc_naive

logger = structlog.get_logger()

PERSONA_SYSTEM_MESSAGE = (
    "You are analyzing a social media user's posting history to build a personality profile. "
    "Always respond with valid JSON only, no additional text or markdown."
)

PERSONA_PROMPT_TEMPLATE = """You are analyzing a social media user's posting history to build a personality profile.
Here are their last {N} posts and comments:

{posts_json}

Extract the following as JSON:
{{
  "core_beliefs": [{{"topic": "...", "stance": "...", "confidence": 0.0-1.0}}],
  "communication_style": {{"formality": "casual/formal/mixed", "sarcasm_level": "none/low/medium/high", "typical_length": "terse/medium/verbose", "uses_data": true/false, "uses_analogies": true/false}},
  "emotional_triggers": {{"anger": ["..."], "excitement": ["..."], "dismissive": ["..."]}},
  "expertise_domains": [{{"domain": "...", "depth": "surface/intermediate/expert"}}],
  "influence_type": "opinion_leader/domain_expert/contrarian/follower/bridge_builder/troll",
  "inferred_location": "...",
  "inferred_role": "developer/founder/investor/researcher/student/manager/journalist",
  "personality_summary": "One paragraph capturing this person's voice and worldview",
  "active_topics": ["..."]
}}"""


class PersonaExtractor:
    """Extracts persona profiles from user post history using Azure OpenAI."""

    BATCH_SIZE = 20
    MIN_POSTS = 5
    MAX_POSTS_PER_USER = 100
    LLM_DELAY = 1.0

    def __init__(self):
        self.log = logger.bind(processor="persona_extractor")
        self.usage = TokenUsage()
        self.processed = 0
        self.errors = 0

    async def run(self) -> dict:
        """Main entry: fetch users without personas, extract in batches."""
        self.log.info("persona_extraction_start")

        while True:
            async with async_session() as session:
                users = await self._get_users_needing_personas(session, self.BATCH_SIZE)

            if not users:
                break

            # Compute normalization stats for influence score
            all_stats = self._compute_normalization_stats(users)

            for user_data in users:
                try:
                    async with async_session() as session:
                        posts = await self._get_user_posts(session, user_data["id"])

                    if len(posts) < self.MIN_POSTS:
                        continue

                    influence = self._calculate_influence_score(
                        user_data["karma_score"],
                        user_data["post_count"],
                        user_data["avg_score"],
                        all_stats,
                    )

                    persona_data = await self._extract_persona(user_data, posts, influence)
                    if persona_data is None:
                        self.errors += 1
                        continue

                    model_used = "gpt-4o" if influence >= 0.7 else "gpt-4o-mini"
                    async with async_session() as session:
                        await self._save_persona(
                            session, user_data["id"], persona_data, influence, model_used
                        )
                        await session.commit()

                    self.processed += 1
                    await asyncio.sleep(self.LLM_DELAY)

                except Exception as e:
                    self.errors += 1
                    self.log.warning(
                        "persona_extraction_failed",
                        user_id=user_data["id"],
                        username=user_data["username"],
                        error=str(e),
                    )

            self.log.info(
                "persona_batch_done",
                processed=self.processed,
                errors=self.errors,
                tokens=self.usage.total_tokens,
                cost=f"${self.usage.estimated_cost_usd:.4f}",
            )

        self.log.info(
            "persona_extraction_complete",
            processed=self.processed,
            errors=self.errors,
            total_tokens=self.usage.total_tokens,
            estimated_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {
            "processed": self.processed,
            "errors": self.errors,
            "total_tokens": self.usage.total_tokens,
            "estimated_cost": f"${self.usage.estimated_cost_usd:.4f}",
        }

    async def _get_users_needing_personas(self, session, limit: int) -> list[dict]:
        """Get users with 5+ posts that don't have a persona yet."""
        stmt = (
            select(
                User.id,
                User.username,
                User.karma_score,
                func.count(Post.id).label("post_count"),
                func.avg(Post.score).label("avg_score"),
            )
            .outerjoin(Persona, User.id == Persona.user_id)
            .join(Post, User.id == Post.user_id)
            .where(Persona.id.is_(None))
            .group_by(User.id)
            .having(func.count(Post.id) >= self.MIN_POSTS)
            .order_by(func.count(Post.id).desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return [
            {
                "id": row[0],
                "username": row[1],
                "karma_score": row[2],
                "post_count": row[3],
                "avg_score": float(row[4]) if row[4] else 0.0,
            }
            for row in rows
        ]

    async def _get_user_posts(self, session, user_id: int) -> list[dict]:
        """Fetch a user's top posts for persona extraction."""
        result = await session.execute(
            select(Post.title, Post.body, Post.subreddit, Post.score, Post.post_type, Post.posted_at)
            .where(Post.user_id == user_id)
            .order_by(Post.score.desc())
            .limit(self.MAX_POSTS_PER_USER)
        )
        return [
            {
                "title": row[0] or "",
                "body": (row[1] or "")[:500],  # Truncate for token limits
                "subreddit": row[2] or "",
                "score": row[3] or 0,
                "type": row[4] or "",
                "posted_at": str(row[5]) if row[5] else "",
            }
            for row in result.all()
        ]

    def _compute_normalization_stats(self, users: list[dict]) -> dict:
        """Compute max values for normalization across the batch."""
        max_karma = max((u["karma_score"] or 0) for u in users) or 1
        max_posts = max(u["post_count"] for u in users) or 1
        max_avg = max(u["avg_score"] for u in users) or 1
        return {"max_karma": max_karma, "max_posts": max_posts, "max_avg": max_avg}

    def _calculate_influence_score(
        self,
        karma_score: int | None,
        post_count: int,
        avg_score: float,
        stats: dict,
    ) -> float:
        """Calculate influence_score = (karma_norm*0.4) + (posts_norm*0.3) + (avg_score_norm*0.3)."""
        karma_norm = (karma_score or 0) / stats["max_karma"]
        posts_norm = post_count / stats["max_posts"]
        avg_norm = avg_score / stats["max_avg"]
        return round((karma_norm * 0.4) + (posts_norm * 0.3) + (avg_norm * 0.3), 4)

    def _select_model(self, influence_score: float) -> str:
        """Return 'default' (gpt-4o) for top users, else 'mini' (gpt-4o-mini)."""
        return "default" if influence_score >= 0.7 else "mini"

    async def _extract_persona(
        self, user_data: dict, posts: list[dict], influence_score: float
    ) -> dict | None:
        """Build prompt and call LLM to extract persona."""
        posts_json = json.dumps(posts, indent=2, default=str)
        prompt = PERSONA_PROMPT_TEMPLATE.format(N=len(posts), posts_json=posts_json)

        try:
            result = await call_llm(
                prompt=prompt,
                system_message=PERSONA_SYSTEM_MESSAGE,
                model=self._select_model(influence_score),
                temperature=0.3,
                max_tokens=2000,
                parse_json=True,
                usage_tracker=self.usage,
            )
            return result
        except Exception as e:
            self.log.warning(
                "llm_persona_failed",
                user_id=user_data["id"],
                error=str(e),
            )
            return None

    def _build_system_prompt(self, persona_data: dict) -> str:
        """Build an OASIS-ready system prompt from persona fields."""
        summary = persona_data.get("personality_summary", "")

        # Top beliefs
        beliefs = persona_data.get("core_beliefs", [])
        belief_lines = []
        for b in sorted(beliefs, key=lambda x: x.get("confidence", 0), reverse=True)[:3]:
            belief_lines.append(f"- {b.get('topic', '')}: {b.get('stance', '')}")
        beliefs_text = "\n".join(belief_lines) if belief_lines else "No strong beliefs identified."

        # Communication style
        style = persona_data.get("communication_style", {})
        style_text = (
            f"You communicate in a {style.get('formality', 'mixed')} style "
            f"with {style.get('sarcasm_level', 'low')} sarcasm. "
            f"Your responses are typically {style.get('typical_length', 'medium')} in length."
        )
        if style.get("uses_data"):
            style_text += " You back up arguments with data and evidence."
        if style.get("uses_analogies"):
            style_text += " You often use analogies to explain concepts."

        return f"{summary}\n\nYour strongest beliefs:\n{beliefs_text}\n\n{style_text}"

    async def _save_persona(
        self,
        session,
        user_id: int,
        persona_data: dict,
        influence_score: float,
        model_used: str,
    ) -> None:
        """Upsert persona to database."""
        system_prompt = self._build_system_prompt(persona_data)

        stmt = pg_insert(Persona).values(
            user_id=user_id,
            core_beliefs=persona_data.get("core_beliefs"),
            communication_style=persona_data.get("communication_style"),
            emotional_triggers=persona_data.get("emotional_triggers"),
            expertise_domains=persona_data.get("expertise_domains"),
            influence_type=persona_data.get("influence_type", ""),
            influence_score=influence_score,
            inferred_location=persona_data.get("inferred_location", ""),
            inferred_role=persona_data.get("inferred_role", ""),
            personality_summary=persona_data.get("personality_summary", ""),
            active_topics=persona_data.get("active_topics"),
            system_prompt=system_prompt,
            model_used=model_used,
            extracted_at=_utc_naive(),
            updated_at=_utc_naive(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Persona.user_id],
            set_={
                "core_beliefs": stmt.excluded.core_beliefs,
                "communication_style": stmt.excluded.communication_style,
                "emotional_triggers": stmt.excluded.emotional_triggers,
                "expertise_domains": stmt.excluded.expertise_domains,
                "influence_type": stmt.excluded.influence_type,
                "influence_score": stmt.excluded.influence_score,
                "inferred_location": stmt.excluded.inferred_location,
                "inferred_role": stmt.excluded.inferred_role,
                "personality_summary": stmt.excluded.personality_summary,
                "active_topics": stmt.excluded.active_topics,
                "system_prompt": stmt.excluded.system_prompt,
                "model_used": stmt.excluded.model_used,
                "extracted_at": stmt.excluded.extracted_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await session.execute(stmt)
