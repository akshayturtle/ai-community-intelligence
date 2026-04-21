"""Gig Post Processor — uses LLM to classify and extract structured gig data from posts.

Sends ALL candidate posts (from gig subreddits and gig search) directly to the LLM
for classification. Tracks EVERY evaluated post (both gig and non-gig) so the same
post is never re-evaluated. Processes in batches until all candidates are exhausted.
"""

import asyncio

import structlog
from sqlalchemy import text

from database.connection import async_session, GigPost
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

CONCURRENCY = 5
BATCH_SIZE = 200

# Priority tiers — process core gig subs first, then broader ones
TIER_1_SUBS = {
    "forhire", "remotejobs", "freelance", "freelance_forhire",
    "hireadev", "jobbit", "machinelearningjobs", "aijobs",
    "cofounderhunt", "gigwork", "gamedevclassifieds",
    "webdeveloperjobs", "pythonjobs", "aidatatrainingjobs",
    "ai_developers", "freelanceindia", "indiajobs",
    "hungryartists", "artcommissions",
}

TIER_2_SUBS = {
    "startups", "saas", "entrepreneur", "indiehackers",
    "remotework", "workonline", "sideproject", "buildinpublic",
    "webdev", "developers", "cscareerquestions", "nocode",
    "aiautomations", "ai_agents", "mlops", "aidevelopernews",
    "samplesize", "softwareengineerJobs",
    "designindia", "internshipsindia", "bangalorestartups",
    "developersindia", "jobnetworking", "appdeveloperskap",
    "graphic_design", "graphicdesignjobs", "artstore",
}

ALL_GIG_SUBS = TIER_1_SUBS | TIER_2_SUBS


async def run(batch_size: int = BATCH_SIZE, concurrency: int = CONCURRENCY) -> tuple[int, int]:
    """Process all unprocessed gig-candidate posts using LLM classification."""
    log = logger.bind(processor="gig_post_processor")
    usage = TokenUsage()
    total_gigs = 0
    total_rejected = 0
    total_failed = 0
    batch_num = 0

    log.info("gig_post_processor_start")

    # Ensure is_gig column exists
    async with async_session() as session:
        await session.execute(text(
            "ALTER TABLE gig_posts ADD COLUMN IF NOT EXISTS is_gig BOOLEAN DEFAULT true"
        ))
        await session.commit()

    # Dedicated job/freelance platforms — always gig posts, no classification needed
    DEDICATED_PLATFORMS = [
        "upwork", "fiverr", "freelancer", "peopleperhour",
        "adzuna", "web3career", "twitter",
    ]

    # Process in batches until no more candidates
    while True:
        batch_num += 1
        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT p.id, p.title, p.body, p.url, p.subreddit, p.posted_at,
                           u.username,
                           p.raw_metadata->>'source' AS source_platform
                    FROM posts p
                    LEFT JOIN users u ON u.id = p.user_id
                    LEFT JOIN gig_posts gp ON gp.post_id = p.id
                    WHERE gp.id IS NULL
                      AND p.body IS NOT NULL
                      AND LENGTH(p.body) > 20
                      AND (
                          p.raw_metadata->>'source' = 'gig_search'
                          OR LOWER(p.subreddit) = ANY(:subreddits)
                          OR p.raw_metadata->>'source' = ANY(:platforms)
                      )
                    ORDER BY
                        CASE WHEN p.raw_metadata->>'source' = ANY(:platforms) THEN 0 ELSE 1 END,
                        CASE WHEN LOWER(p.subreddit) = ANY(:tier1) THEN 0 ELSE 1 END,
                        p.posted_at DESC NULLS LAST
                    LIMIT :batch_size
                """),
                {
                    "subreddits": list(ALL_GIG_SUBS),
                    "tier1": list(TIER_1_SUBS),
                    "platforms": DEDICATED_PLATFORMS,
                    "batch_size": batch_size,
                },
            )
            candidates = result.all()

        if not candidates:
            log.info("gig_no_more_candidates", batches_processed=batch_num - 1)
            break

        log.info("gig_batch_start", batch=batch_num, candidates=len(candidates))

        sem = asyncio.Semaphore(concurrency)
        batch_gigs = 0
        batch_rejected = 0
        batch_failed = 0

        async def process_one(row):
            nonlocal batch_gigs, batch_rejected, batch_failed
            async with sem:
                try:
                    src = getattr(row, "source_platform", None) or ""
                    is_dedicated = src in DEDICATED_PLATFORMS
                    result = await _extract_gig(row, usage, is_dedicated=is_dedicated)
                    # Dedicated platforms are always gigs — only reject if extraction failed
                    if result and (result.get("is_gig") or is_dedicated):
                        await _store_gig(row, result, is_gig=True)
                        batch_gigs += 1
                    else:
                        await _store_rejected(row)
                        batch_rejected += 1
                except Exception as e:
                    batch_failed += 1
                    log.warning("gig_extraction_failed", post_id=row.id, error=str(e))

        await asyncio.gather(*(process_one(row) for row in candidates))

        total_gigs += batch_gigs
        total_rejected += batch_rejected
        total_failed += batch_failed

        log.info(
            "gig_batch_complete",
            batch=batch_num,
            gigs=batch_gigs,
            rejected=batch_rejected,
            failed=batch_failed,
            cost_so_far=f"${usage.estimated_cost_usd:.4f}",
        )

    log.info(
        "gig_post_processor_complete",
        processed=total_gigs,
        rejected=total_rejected,
        failed=total_failed,
        batches=batch_num - 1,
        llm_cost=f"${usage.estimated_cost_usd:.4f}",
    )
    return total_gigs, total_failed


async def _extract_gig(row, usage: TokenUsage, is_dedicated: bool = False) -> dict | None:
    """Use LLM to classify and extract structured gig data from a post."""
    title = row.title or "N/A"
    body = (row.body or "")[:1500]
    source = getattr(row, "source_platform", None) or ""
    text_content = f"Title: {title}\nBody: {body}"
    if row.subreddit:
        text_content += f"\nSubreddit: r/{row.subreddit}"
    if source:
        text_content += f"\nSource platform: {source}"

    if is_dedicated:
        # These are definitively job/gig posts — skip classification, just extract
        classification_instruction = (
            f"This post is from {source}, a dedicated freelance/job platform. "
            f"It is definitely a gig/job post. Set is_gig=true and extract all structured fields."
        )
    else:
        classification_instruction = (
            "Analyze this post and determine if it's a hiring, freelance, gig, job, or co-founder search post. "
            "If NOT (e.g. it's a discussion, question, news, meme), return {\"is_gig\": false}."
        )

    prompt = f"""{classification_instruction}

{text_content}

Return JSON:
{{
  "is_gig": true/false,
  "gig_title": "short descriptive title for the opportunity",
  "project_type": "freelance" | "contract" | "full_time" | "part_time" | "co_founder" | "consulting" | "internship" | "research_study",
  "need_description": "2-3 sentence description of what they need",
  "need_category": "chatbot" | "rag" | "fine_tuning" | "agent" | "automation" | "data_pipeline" | "web_app" | "mobile_app" | "ml_model" | "saas" | "design" | "devops" | "other",
  "skills_required": ["skill1", "skill2", ...],
  "tech_stack": ["technology1", "technology2", ...],
  "pay_text": "raw pay/budget text exactly as mentioned, else null",
  "pay_min_usd": number or null,
  "pay_max_usd": number or null,
  "pay_type": "hourly" | "fixed" | "monthly" | "annual" | "equity" | null,
  "experience_level": "junior" | "mid" | "senior" | "lead" | "any",
  "remote_policy": "remote" | "onsite" | "hybrid",
  "location": "location if mentioned, else null",
  "start_time": "when they need someone (e.g. 'immediately', 'next week', 'Q2 2026'), else null",
  "project_duration": "duration if mentioned (e.g. '3 months', 'ongoing'), else null",
  "industry": "industry/domain if mentioned",
  "company_name": "company or startup name if mentioned, else null",
  "apply_method": "how to apply — DM, email, link, etc. Include actual email/link if present",
  "equity_offered": true/false if equity is mentioned
}}

Rules:
- Mark as gig if someone is looking to hire, pay for work, find a co-founder, or offering paid work
- Posts where someone is offering their own services ('[For Hire]') are also gigs — set project_type to match
- Extract pay in USD when possible. Convert hourly/monthly if enough info
- For skills_required, list specific skills (e.g. 'Python', 'React', 'LLM fine-tuning', 'UI/UX design')
- For tech_stack, list specific technologies/frameworks (e.g. 'LangChain', 'FastAPI', 'PostgreSQL')
- Keep need_description informative but concise"""

    result = await call_llm(
        prompt=prompt,
        system_message="You are a job market analyst. Classify posts and extract structured hiring/gig data. Be accurate — mark genuine opportunities as gigs, skip discussions and news.",
        model="mini",
        parse_json=True,
        usage_tracker=usage,
        max_tokens=1000,
        temperature=0.1,
    )

    if not isinstance(result, dict):
        return None
    return result


async def _store_gig(row, data: dict, is_gig: bool = True):
    """Store extracted gig data."""
    async with async_session() as session:
        gig = GigPost(
            post_id=row.id,
            is_gig=is_gig,
            gig_title=data.get("gig_title"),
            project_type=data.get("project_type"),
            need_description=data.get("need_description"),
            need_category=data.get("need_category"),
            skills_required=data.get("skills_required", []),
            budget_text=data.get("pay_text"),
            budget_min_usd=data.get("pay_min_usd"),
            budget_max_usd=data.get("pay_max_usd"),
            pay_type=data.get("pay_type"),
            tech_stack=data.get("tech_stack", []),
            experience_level=data.get("experience_level"),
            remote_policy=data.get("remote_policy", "remote"),
            location=data.get("location"),
            start_time=data.get("start_time"),
            project_duration=data.get("project_duration"),
            industry=data.get("industry"),
            company_name=data.get("company_name"),
            contact_method=data.get("apply_method"),
            equity_offered=data.get("equity_offered"),
            poster_username=row.username,
            source_url=row.url,
            source_subreddit=row.subreddit,
            posted_at=row.posted_at,
            raw_llm_response=data,
        )
        session.add(gig)
        await session.commit()


async def _store_rejected(row):
    """Store a rejected post so it's not re-evaluated."""
    async with async_session() as session:
        gig = GigPost(
            post_id=row.id,
            is_gig=False,
            source_subreddit=row.subreddit,
            poster_username=row.username,
            source_url=row.url,
            posted_at=row.posted_at,
        )
        session.add(gig)
        await session.commit()
