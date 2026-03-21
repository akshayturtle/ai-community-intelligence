"""Job Intelligence Extractor — LLM-per-post structured extraction.

Processes each job listing through gpt-4o-mini to extract:
- Tech stack, role category, seniority, experience years
- Salary (normalized USD), location (normalized), remote policy
- Market category, business model, company stage, AI investment level
- Hiring urgency, team structure, responsibilities, skills
- Benefits, culture signals, compliance, work methodology
"""

import asyncio
import json
import time
import structlog
from sqlalchemy import text

from database.connection import async_session
from processors.llm_client import call_llm, TokenUsage

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a job market intelligence analyst. Extract structured data from job postings.
Return ONLY valid JSON — no markdown, no explanation. Follow the exact schema provided."""

EXTRACTION_PROMPT = """Analyze this job posting and extract structured intelligence.

**Job Title:** {title}
**Company:** {company}
**Location:** {location}
**Source:** {source}
**Existing Tags:** {tags}
**Listed Salary:** {salary}
**Remote Flag:** {remote}
**Seniority (if any):** {seniority}

**Job Description:**
{description}

---

Return a JSON object with these exact keys:

{{
  "role_category": "<one of: backend, frontend, fullstack, devops, data_engineer, data_scientist, ml_ai, mobile, security, qa, product, design, management, devrel, sales_engineer, other>",
  "seniority_normalized": "<one of: intern, junior, mid, senior, staff, principal, lead, manager, director, vp, c_level, unknown>",
  "experience_years_min": <integer or null>,
  "experience_years_max": <integer or null>,
  "salary_min_usd": <annual USD integer or null — convert hourly*2080, monthly*12, EUR*1.08, GBP*1.27>,
  "salary_max_usd": <annual USD integer or null>,
  "remote_policy": "<one of: fully_remote, hybrid, onsite, remote_friendly, unknown>",
  "location_city": "<city name or null>",
  "location_state": "<state/province or null>",
  "location_country": "<2-letter ISO code like US, GB, DE, IN or null>",
  "tech_stack": {{
    "languages": ["Python", "Go", ...],
    "frameworks": ["React", "FastAPI", ...],
    "databases": ["PostgreSQL", "Redis", ...],
    "cloud": ["AWS", "GCP", ...],
    "ai_ml": ["PyTorch", "LangChain", "RAG", ...],
    "tools": ["Docker", "Kubernetes", "Terraform", ...]
  }},
  "market_category": "<one of: fintech, healthtech, devtools, cybersecurity, edtech, ecommerce, saas, ai_ml, data_infra, cloud_infra, gaming, media, social, hr_tech, legal_tech, proptech, climate_tech, biotech, logistics, govtech, other>",
  "business_model": "<one of: b2b_saas, b2c, marketplace, enterprise, open_source, consulting, platform, api_service, other, unknown>",
  "company_stage": "<one of: seed, series_a, series_b, series_c_plus, growth, public, bootstrapped, unknown>",
  "ai_investment_level": "<one of: core_product, significant, internal_tooling, minimal, none>",
  "funding_mentions": "<exact funding text like '$50M Series B' or null>",
  "domain_industry": "<primary industry: healthcare, finance, education, logistics, etc or null>",
  "hiring_urgency": "<one of: urgent, normal, passive> — urgent if: ASAP, immediately, multiple similar roles, start date soon",
  "team_structure_clues": "<string: 'founding engineer', 'team of 15', 'report to VP Eng' or null>",
  "key_responsibilities": ["top 3-5 responsibilities as short phrases"],
  "must_have_skills": ["required skills/qualifications"],
  "nice_to_have_skills": ["preferred/bonus skills"],
  "benefits": ["equity", "unlimited_pto", "visa_sponsorship", "401k_match", "health_insurance", "remote_stipend", ...],
  "culture_signals": ["startup_mentality", "flat_hierarchy", "mission_driven", "move_fast", "work_life_balance", ...],
  "work_methodology": "<one of: agile, scrum, kanban, waterfall, unknown>",
  "compliance_requirements": ["soc2", "hipaa", "pci", "fedramp", "clearance", ...]
}}

Be precise. Use null for unknown/not mentioned. For tech_stack, only include explicitly mentioned technologies."""


async def run(batch_size: int = 100, concurrency: int = 5, max_jobs: int = 0):
    """Process all unprocessed job listings through LLM extraction.

    Args:
        batch_size: Number of jobs to fetch per DB batch.
        concurrency: Max parallel LLM calls.
        max_jobs: If >0, stop after this many jobs (for testing).
    """
    usage = TokenUsage()
    sem = asyncio.Semaphore(concurrency)
    processed = 0
    failed = 0
    start_time = time.time()

    logger.info("job_intelligence_start", batch_size=batch_size, concurrency=concurrency, max_jobs=max_jobs)

    while True:
        # Fetch next batch of unprocessed jobs
        async with async_session() as session:
            rows = (await session.execute(text("""
                SELECT jl.id, jl.title, jl.company, jl.location, jl.source,
                       jl.tags::text, jl.salary_min, jl.salary_max, jl.salary_currency,
                       jl.remote, jl.seniority, jl.department,
                       LEFT(jl.description, 4000) as description
                FROM job_listings jl
                LEFT JOIN job_intelligence ji ON ji.job_listing_id = jl.id
                WHERE ji.id IS NULL
                ORDER BY jl.id
                LIMIT :limit
            """), {"limit": batch_size})).fetchall()

        if not rows:
            logger.info("job_intelligence_no_more_jobs")
            break

        logger.info("job_intelligence_batch", count=len(rows), total_processed=processed)

        # Process batch with concurrency limit
        tasks = []
        for row in rows:
            if max_jobs > 0 and processed + len(tasks) >= max_jobs:
                break
            tasks.append(_process_one(row, sem, usage))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for r in results:
            if isinstance(r, Exception):
                failed += 1
                logger.warning("job_intelligence_task_error", error=str(r))
            elif r:
                processed += 1
            else:
                failed += 1

        elapsed = time.time() - start_time
        rate = processed / elapsed if elapsed > 0 else 0
        logger.info(
            "job_intelligence_progress",
            processed=processed,
            failed=failed,
            elapsed_s=round(elapsed, 1),
            rate=f"{rate:.1f}/s",
            cost=f"${usage.estimated_cost_usd:.4f}",
        )

        if max_jobs > 0 and processed >= max_jobs:
            logger.info("job_intelligence_max_reached", max_jobs=max_jobs)
            break

    elapsed = time.time() - start_time
    logger.info(
        "job_intelligence_complete",
        processed=processed,
        failed=failed,
        elapsed_s=round(elapsed, 1),
        total_tokens=usage.total_tokens,
        llm_calls=usage.calls,
        cost=f"${usage.estimated_cost_usd:.4f}",
    )
    return processed, failed


async def _process_one(row, sem: asyncio.Semaphore, usage: TokenUsage) -> bool:
    """Extract intelligence from a single job listing."""
    async with sem:
        job_id = row[0]
        title = row[1] or ""
        company = row[2] or ""
        location = row[3] or ""
        source = row[4] or ""
        tags = row[5] or "[]"
        salary_min = row[6]
        salary_max = row[7]
        salary_currency = row[8] or ""
        remote = row[9] or False
        seniority = row[10] or ""
        description = row[12] or ""

        if not description and not title:
            return False

        salary_str = "Not listed"
        if salary_min or salary_max:
            parts = []
            if salary_min:
                parts.append(f"{salary_currency}{salary_min:,.0f}")
            if salary_max:
                parts.append(f"{salary_currency}{salary_max:,.0f}")
            salary_str = " - ".join(parts)

        prompt = EXTRACTION_PROMPT.format(
            title=title,
            company=company,
            location=location,
            source=source,
            tags=tags,
            salary=salary_str,
            remote=remote,
            seniority=seniority,
            description=description[:4000],
        )

        try:
            result = await call_llm(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                model="mini",
                temperature=0.1,
                max_tokens=1200,
                parse_json=True,
                usage_tracker=usage,
            )
        except Exception as e:
            logger.warning("job_intelligence_llm_error", job_id=job_id, error=str(e))
            return False

        if not isinstance(result, dict):
            logger.warning("job_intelligence_bad_response", job_id=job_id)
            return False

        # Store in DB
        try:
            await _store_intelligence(job_id, result)
            return True
        except Exception as e:
            logger.warning("job_intelligence_store_error", job_id=job_id, error=str(e))
            return False


async def _store_intelligence(job_id: int, data: dict):
    """Insert extracted intelligence into job_intelligence table."""
    ts = data.get("tech_stack", {})
    if not isinstance(ts, dict):
        ts = {}

    async with async_session() as session:
        await session.execute(text("""
            INSERT INTO job_intelligence (
                job_listing_id, role_category, seniority_normalized,
                experience_years_min, experience_years_max,
                salary_min_usd, salary_max_usd,
                remote_policy, location_city, location_state, location_country,
                tech_stack, market_category, business_model, company_stage,
                ai_investment_level, funding_mentions, domain_industry,
                hiring_urgency, team_structure_clues,
                key_responsibilities, must_have_skills, nice_to_have_skills,
                benefits, culture_signals, work_methodology, compliance_requirements,
                raw_llm_response
            ) VALUES (
                :job_listing_id, :role_category, :seniority_normalized,
                :experience_years_min, :experience_years_max,
                :salary_min_usd, :salary_max_usd,
                :remote_policy, :location_city, :location_state, :location_country,
                :tech_stack, :market_category, :business_model, :company_stage,
                :ai_investment_level, :funding_mentions, :domain_industry,
                :hiring_urgency, :team_structure_clues,
                :key_responsibilities, :must_have_skills, :nice_to_have_skills,
                :benefits, :culture_signals, :work_methodology, :compliance_requirements,
                :raw_llm_response
            )
            ON CONFLICT (job_listing_id) DO UPDATE SET
                role_category = EXCLUDED.role_category,
                seniority_normalized = EXCLUDED.seniority_normalized,
                tech_stack = EXCLUDED.tech_stack,
                raw_llm_response = EXCLUDED.raw_llm_response,
                extracted_at = NOW()
        """), {
            "job_listing_id": job_id,
            "role_category": _str(data, "role_category", 50),
            "seniority_normalized": _str(data, "seniority_normalized", 30),
            "experience_years_min": _int(data, "experience_years_min"),
            "experience_years_max": _int(data, "experience_years_max"),
            "salary_min_usd": _int(data, "salary_min_usd"),
            "salary_max_usd": _int(data, "salary_max_usd"),
            "remote_policy": _str(data, "remote_policy", 30),
            "location_city": _str(data, "location_city", 100),
            "location_state": _str(data, "location_state", 100),
            "location_country": _str(data, "location_country", 100),
            "tech_stack": json.dumps(ts),
            "market_category": _str(data, "market_category", 50),
            "business_model": _str(data, "business_model", 30),
            "company_stage": _str(data, "company_stage", 30),
            "ai_investment_level": _str(data, "ai_investment_level", 20),
            "funding_mentions": _str(data, "funding_mentions", 500),
            "domain_industry": _str(data, "domain_industry", 50),
            "hiring_urgency": _str(data, "hiring_urgency", 20),
            "team_structure_clues": _str(data, "team_structure_clues", 500),
            "key_responsibilities": json.dumps(data.get("key_responsibilities") or []),
            "must_have_skills": json.dumps(data.get("must_have_skills") or []),
            "nice_to_have_skills": json.dumps(data.get("nice_to_have_skills") or []),
            "benefits": json.dumps(data.get("benefits") or []),
            "culture_signals": json.dumps(data.get("culture_signals") or []),
            "work_methodology": _str(data, "work_methodology", 30),
            "compliance_requirements": json.dumps(data.get("compliance_requirements") or []),
            "raw_llm_response": json.dumps(data),
        })
        await session.commit()


def _str(data: dict, key: str, max_len: int) -> str | None:
    """Extract a string value, truncate, return None if empty."""
    val = data.get(key)
    if val is None or val == "null" or val == "":
        return None
    val = str(val).strip()[:max_len]
    return val if val else None


def _int(data: dict, key: str) -> int | None:
    """Extract an integer value, return None if not a valid number."""
    val = data.get(key)
    if val is None or val == "null":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# CLI entry point
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract intelligence from job listings via LLM")
    parser.add_argument("--batch-size", type=int, default=100, help="DB fetch batch size")
    parser.add_argument("--concurrency", type=int, default=5, help="Parallel LLM calls")
    parser.add_argument("--max-jobs", type=int, default=0, help="Max jobs to process (0=all)")
    args = parser.parse_args()

    asyncio.run(run(
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        max_jobs=args.max_jobs,
    ))
