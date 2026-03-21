"""Leader Shift Detector — detects when opinion leaders change their stance.

Layer 1: Compare recent vs older sentiment per topic for top leaders
Layer 3: LLM describes the shift
"""

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select, func, and_

from database.connection import (
    async_session,
    Post,
    Persona,
    Topic,
    LeaderShift,
    User,
    Platform,
)
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()


class LeaderShiftProcessor:
    """Detects stance changes in top opinion leaders."""

    def __init__(self):
        self.log = logger.bind(processor="leader_shift_processor")
        self.usage = TokenUsage()
        self.shifts_detected = 0
        self.errors = 0

    async def run(self) -> dict:
        self.log.info("leader_shift_start")

        # Get top personas by influence
        leaders = await self._get_top_leaders()
        self.log.info("leaders_to_check", count=len(leaders))

        # Get active topics
        topics = await self._get_active_topics()

        for leader in leaders:
            for topic in topics:
                await self._check_shift(leader, topic)

        self.log.info(
            "leader_shift_complete",
            shifts=self.shifts_detected,
            errors=self.errors,
            llm_cost=f"${self.usage.estimated_cost_usd:.4f}",
        )
        return {"shifts_detected": self.shifts_detected, "errors": self.errors}

    async def _get_top_leaders(self) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(Persona.id, Persona.user_id, User.username, Platform.name.label("platform"))
                .join(User, Persona.user_id == User.id)
                .join(Platform, User.platform_id == Platform.id)
                .where(Persona.influence_score.isnot(None))
                .order_by(Persona.influence_score.desc())
                .limit(50)
            )
            return [
                {"persona_id": r.id, "user_id": r.user_id, "username": r.username, "platform": r.platform}
                for r in result.all()
            ]

    async def _get_active_topics(self) -> list[dict]:
        async with async_session() as session:
            result = await session.execute(
                select(Topic.id, Topic.name, Topic.keywords)
                .where(Topic.status.in_(["emerging", "active", "peaking"]))
                .order_by(Topic.velocity.desc())
                .limit(10)
            )
            return [{"id": r.id, "name": r.name, "keywords": r.keywords or []} for r in result.all()]

    async def _check_shift(self, leader: dict, topic: dict):
        """Check if a leader's stance has shifted on a topic."""
        try:
            now = datetime.utcnow()
            recent_start = now - timedelta(days=14)
            older_start = now - timedelta(days=60)

            keywords = topic["keywords"]
            if not keywords:
                keywords = [topic["name"]]

            async with async_session() as session:
                # Build keyword filter
                from sqlalchemy import or_
                kw_filters = or_(*[Post.body.ilike(f"%{kw}%") for kw in keywords[:3]])

                # Recent posts (last 14 days) — include body for trigger detection
                recent_result = await session.execute(
                    select(Post.raw_metadata, Post.title, Post.body)
                    .where(Post.user_id == leader["user_id"])
                    .where(Post.posted_at >= recent_start)
                    .where(Post.raw_metadata.isnot(None))
                    .where(Post.raw_metadata.has_key("sentiment"))
                    .where(kw_filters)
                    .limit(20)
                )
                recent_posts = recent_result.all()

                # Older posts (14-60 days ago) — include body for trigger detection
                older_result = await session.execute(
                    select(Post.raw_metadata, Post.title, Post.body)
                    .where(Post.user_id == leader["user_id"])
                    .where(Post.posted_at >= older_start)
                    .where(Post.posted_at < recent_start)
                    .where(Post.raw_metadata.isnot(None))
                    .where(Post.raw_metadata.has_key("sentiment"))
                    .where(kw_filters)
                    .limit(20)
                )
                older_posts = older_result.all()

            if len(recent_posts) < 2 or len(older_posts) < 2:
                return

            recent_sentiments = [
                float(r[0]["sentiment"]["compound"])
                for r in recent_posts if r[0] and "sentiment" in r[0]
            ]
            older_sentiments = [
                float(r[0]["sentiment"]["compound"])
                for r in older_posts if r[0] and "sentiment" in r[0]
            ]

            if not recent_sentiments or not older_sentiments:
                return

            recent_avg = sum(recent_sentiments) / len(recent_sentiments)
            older_avg = sum(older_sentiments) / len(older_sentiments)

            # Detect shift
            shift_type = None
            if older_avg > 0.2 and recent_avg < -0.2:
                shift_type = "flipped_negative"
            elif older_avg < -0.2 and recent_avg > 0.2:
                shift_type = "flipped_positive"
            elif abs(older_avg - recent_avg) > 0.3:
                shift_type = "shifting"

            if not shift_type:
                return

            # Check if already detected
            async with async_session() as session:
                existing = await session.execute(
                    select(LeaderShift.id)
                    .where(LeaderShift.persona_id == leader["persona_id"])
                    .where(LeaderShift.topic_name == topic["name"])
                    .where(LeaderShift.detected_at >= now - timedelta(days=7))
                )
                if existing.scalar():
                    return

            # Collect post snippets for trigger detection
            older_snippets = []
            for r in older_posts[:3]:
                title = r[1] or ""
                body = (r[2] or "")[:150]
                snippet = f"{title}: {body}".strip(": ")
                if snippet:
                    older_snippets.append(snippet[:200])
            recent_snippets = []
            for r in recent_posts[:3]:
                title = r[1] or ""
                body = (r[2] or "")[:150]
                snippet = f"{title}: {body}".strip(": ")
                if snippet:
                    recent_snippets.append(snippet[:200])

            older_text = "\n".join(f'- "{s}"' for s in older_snippets) or "- (no excerpts available)"
            recent_text = "\n".join(f'- "{s}"' for s in recent_snippets) or "- (no excerpts available)"

            # LLM to describe the shift WITH post context
            summary = f"Sentiment shifted from {older_avg:.2f} to {recent_avg:.2f} on {topic['name']}"
            try:
                llm_result = await call_llm(
                    prompt=f"""This user ({leader['username']}, {leader['platform']}) changed their stance on "{topic['name']}".

Their older posts (2-8 weeks ago, avg sentiment {older_avg:.2f}):
{older_text}

Their recent posts (last 2 weeks, avg sentiment {recent_avg:.2f}):
{recent_text}

Based on the post content, identify what TRIGGERED this shift and describe it.

Return JSON:
{{"old_stance": "...", "new_stance": "...", "trigger": "specific event or reason for the shift", "summary": "one-sentence dashboard summary"}}""",
                    system_message="You are a community intelligence analyst.",
                    model="mini",
                    parse_json=True,
                    usage_tracker=self.usage,
                    max_tokens=300,
                )

                if isinstance(llm_result, dict):
                    summary = llm_result.get("summary", summary)
                    old_stance = llm_result.get("old_stance", "")
                    new_stance = llm_result.get("new_stance", "")
                    trigger = llm_result.get("trigger", "")
                else:
                    old_stance = f"Sentiment avg: {older_avg:.2f}"
                    new_stance = f"Sentiment avg: {recent_avg:.2f}"
                    trigger = ""
            except Exception:
                old_stance = f"Sentiment avg: {older_avg:.2f}"
                new_stance = f"Sentiment avg: {recent_avg:.2f}"
                trigger = ""

            async with async_session() as session:
                session.add(LeaderShift(
                    persona_id=leader["persona_id"],
                    topic_id=topic["id"],
                    topic_name=topic["name"],
                    old_stance=old_stance,
                    new_stance=new_stance,
                    shift_type=shift_type,
                    trigger=trigger,
                    summary=summary,
                    old_sentiment=round(older_avg, 4),
                    new_sentiment=round(recent_avg, 4),
                ))
                await session.commit()
                self.shifts_detected += 1

        except Exception as e:
            self.errors += 1
            self.log.warning(
                "shift_check_failed",
                leader=leader["username"],
                topic=topic["name"],
                error=str(e),
            )
