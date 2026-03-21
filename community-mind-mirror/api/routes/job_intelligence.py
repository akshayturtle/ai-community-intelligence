"""Job Intelligence routes — aggregated insights from LLM-extracted job data."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db

router = APIRouter()


@router.get("/summary")
async def job_intelligence_summary(db: AsyncSession = Depends(get_db)):
    """High-level stats: total processed, role distribution, top markets, etc."""
    total = (await db.execute(text("SELECT COUNT(*) FROM job_intelligence"))).scalar()
    total_jobs = (await db.execute(text("SELECT COUNT(*) FROM job_listings"))).scalar()

    roles = (await db.execute(text("""
        SELECT role_category, COUNT(*) as cnt
        FROM job_intelligence WHERE role_category IS NOT NULL
        GROUP BY role_category ORDER BY cnt DESC
    """))).fetchall()

    seniority = (await db.execute(text("""
        SELECT seniority_normalized, COUNT(*) as cnt
        FROM job_intelligence WHERE seniority_normalized IS NOT NULL AND seniority_normalized != 'unknown'
        GROUP BY seniority_normalized ORDER BY cnt DESC
    """))).fetchall()

    markets = (await db.execute(text("""
        SELECT market_category, COUNT(*) as cnt
        FROM job_intelligence WHERE market_category IS NOT NULL
        GROUP BY market_category ORDER BY cnt DESC LIMIT 15
    """))).fetchall()

    ai_levels = (await db.execute(text("""
        SELECT ai_investment_level, COUNT(*) as cnt
        FROM job_intelligence WHERE ai_investment_level IS NOT NULL
        GROUP BY ai_investment_level ORDER BY cnt DESC
    """))).fetchall()

    remote = (await db.execute(text("""
        SELECT remote_policy, COUNT(*) as cnt
        FROM job_intelligence WHERE remote_policy IS NOT NULL AND remote_policy != 'unknown'
        GROUP BY remote_policy ORDER BY cnt DESC
    """))).fetchall()

    return {
        "total_jobs": total_jobs,
        "total_processed": total,
        "coverage_pct": round(total / total_jobs * 100, 1) if total_jobs else 0,
        "by_role": [{"role": r[0], "count": r[1]} for r in roles],
        "by_seniority": [{"seniority": r[0], "count": r[1]} for r in seniority],
        "by_market": [{"market": r[0], "count": r[1]} for r in markets],
        "by_ai_level": [{"level": r[0], "count": r[1]} for r in ai_levels],
        "by_remote_policy": [{"policy": r[0], "count": r[1]} for r in remote],
    }


@router.get("/tech-stack")
async def tech_stack_rankings(
    role: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Most demanded technologies across all job listings."""
    role_filter = ""
    params = {"lim": limit}
    if role:
        role_filter = "WHERE role_category = :role"
        params["role"] = role

    # Extract all tech mentions from JSONB arrays and count
    # Use jsonb_typeof check to skip rows where the key is null/not an array
    rows = (await db.execute(text(f"""
        WITH techs AS (
            SELECT 'language' as category, jsonb_array_elements_text(tech_stack->'languages') as tech
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'languages') = 'array'
            UNION ALL
            SELECT 'framework', jsonb_array_elements_text(tech_stack->'frameworks')
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'frameworks') = 'array'
            UNION ALL
            SELECT 'database', jsonb_array_elements_text(tech_stack->'databases')
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'databases') = 'array'
            UNION ALL
            SELECT 'cloud', jsonb_array_elements_text(tech_stack->'cloud')
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'cloud') = 'array'
            UNION ALL
            SELECT 'ai_ml', jsonb_array_elements_text(tech_stack->'ai_ml')
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'ai_ml') = 'array'
            UNION ALL
            SELECT 'tool', jsonb_array_elements_text(tech_stack->'tools')
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(tech_stack->'tools') = 'array'
        )
        SELECT LOWER(tech) as technology, category, COUNT(*) as mentions
        FROM techs
        WHERE tech IS NOT NULL AND tech != ''
        GROUP BY LOWER(tech), category
        ORDER BY mentions DESC
        LIMIT :lim
    """), params)).fetchall()

    return {
        "filter_role": role,
        "technologies": [
            {"name": r[0], "category": r[1], "mentions": r[2]}
            for r in rows
        ],
    }


@router.get("/salary-insights")
async def salary_insights(
    country: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Salary ranges by role and seniority."""
    country_filter = ""
    params = {}
    if country:
        country_filter = "AND location_country = :country"
        params["country"] = country.upper()

    rows = (await db.execute(text(f"""
        SELECT role_category, seniority_normalized,
               COUNT(*) as sample_size,
               PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY salary_min_usd) as p25_min,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY salary_min_usd) as median_min,
               PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY salary_max_usd) as p75_max,
               PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY salary_max_usd) as median_max,
               AVG(salary_min_usd)::int as avg_min,
               AVG(salary_max_usd)::int as avg_max
        FROM job_intelligence
        WHERE salary_min_usd IS NOT NULL AND salary_max_usd IS NOT NULL
              AND salary_min_usd > 10000 AND salary_max_usd < 1000000
              AND role_category IS NOT NULL
              AND seniority_normalized IS NOT NULL AND seniority_normalized != 'unknown'
              {country_filter}
        GROUP BY role_category, seniority_normalized
        HAVING COUNT(*) >= 3
        ORDER BY median_max DESC
    """), params)).fetchall()

    return {
        "filter_country": country,
        "salary_bands": [
            {
                "role": r[0],
                "seniority": r[1],
                "sample_size": r[2],
                "p25_min": int(r[3]) if r[3] else None,
                "median_min": int(r[4]) if r[4] else None,
                "p75_max": int(r[5]) if r[5] else None,
                "median_max": int(r[6]) if r[6] else None,
                "avg_min": r[7],
                "avg_max": r[8],
            }
            for r in rows
        ],
    }


@router.get("/hiring-velocity")
async def hiring_velocity(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Companies with most open roles — hiring aggressively."""
    rows = (await db.execute(text("""
        SELECT jl.company, COUNT(*) as open_roles,
               ji.market_category,
               ji.company_stage,
               ji.ai_investment_level,
               ARRAY_AGG(DISTINCT ji.role_category) FILTER (WHERE ji.role_category IS NOT NULL) as roles,
               COUNT(*) FILTER (WHERE ji.hiring_urgency = 'urgent') as urgent_roles
        FROM job_listings jl
        JOIN job_intelligence ji ON ji.job_listing_id = jl.id
        WHERE jl.company IS NOT NULL AND jl.company != ''
        GROUP BY jl.company, ji.market_category, ji.company_stage, ji.ai_investment_level
        HAVING COUNT(*) >= 3
        ORDER BY open_roles DESC
        LIMIT :lim
    """), {"lim": limit})).fetchall()

    return {
        "companies": [
            {
                "company": r[0],
                "open_roles": r[1],
                "market": r[2],
                "stage": r[3],
                "ai_level": r[4],
                "role_types": r[5] or [],
                "urgent_roles": r[6],
            }
            for r in rows
        ],
    }


@router.get("/skills-demand")
async def skills_demand(
    role: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Most in-demand skills (must-have and nice-to-have)."""
    role_filter = ""
    params = {"lim": limit}
    if role:
        role_filter = "WHERE role_category = :role"
        params["role"] = role

    # Filter out generic soft skills to surface technical skills
    soft_skill_filter = """
        AND skill NOT ILIKE '%communication%'
        AND skill NOT ILIKE '%team player%'
        AND skill NOT ILIKE '%problem solving%'
        AND skill NOT ILIKE '%problem-solving%'
        AND skill NOT ILIKE '%analytical skills%'
        AND skill NOT ILIKE '%attention to detail%'
        AND skill NOT ILIKE '%self-motivated%'
        AND skill NOT ILIKE '%fast-paced%'
        AND skill NOT ILIKE '%work independently%'
        AND skill NOT ILIKE '%strong work ethic%'
        AND skill NOT ILIKE '%interpersonal%'
        AND skill NOT ILIKE '%organizational skills%'
        AND skill NOT ILIKE '%time management%'
        AND skill NOT ILIKE '%multitask%'
        AND skill NOT ILIKE '%leadership skills%'
        AND skill NOT ILIKE '%collaborative%'
        AND skill NOT ILIKE '%passion for%'
        AND skill NOT ILIKE '%excellent written%'
        AND skill NOT ILIKE '%strong analytical%'
        AND skill NOT ILIKE '%ability to%'
    """
    rows = (await db.execute(text(f"""
        WITH skills AS (
            SELECT 'must_have' as type, LOWER(jsonb_array_elements_text(must_have_skills)) as skill
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(must_have_skills) = 'array'
            UNION ALL
            SELECT 'nice_to_have', LOWER(jsonb_array_elements_text(nice_to_have_skills))
            FROM job_intelligence {role_filter + ' AND' if role_filter else 'WHERE'} jsonb_typeof(nice_to_have_skills) = 'array'
        )
        SELECT skill, type, COUNT(*) as mentions
        FROM skills
        WHERE skill IS NOT NULL AND LENGTH(skill) > 1
              {soft_skill_filter}
        GROUP BY skill, type
        ORDER BY mentions DESC
        LIMIT :lim
    """), params)).fetchall()

    return {
        "filter_role": role,
        "skills": [
            {"skill": r[0], "type": r[1], "mentions": r[2]}
            for r in rows
        ],
    }


@router.get("/geographic")
async def geographic_distribution(
    db: AsyncSession = Depends(get_db),
):
    """Job distribution by country and city."""
    countries = (await db.execute(text("""
        SELECT location_country, COUNT(*) as cnt,
               COUNT(*) FILTER (WHERE remote_policy = 'fully_remote') as remote_count
        FROM job_intelligence
        WHERE location_country IS NOT NULL
        GROUP BY location_country ORDER BY cnt DESC LIMIT 20
    """))).fetchall()

    cities = (await db.execute(text("""
        SELECT location_city, location_country, COUNT(*) as cnt
        FROM job_intelligence
        WHERE location_city IS NOT NULL
        GROUP BY location_city, location_country ORDER BY cnt DESC LIMIT 20
    """))).fetchall()

    return {
        "by_country": [
            {"country": r[0], "count": r[1], "remote_count": r[2]}
            for r in countries
        ],
        "by_city": [
            {"city": r[0], "country": r[1], "count": r[2]}
            for r in cities
        ],
    }


@router.get("/ai-landscape")
async def ai_landscape(db: AsyncSession = Depends(get_db)):
    """AI adoption across companies — who's building AI vs using it."""
    ai_by_market = (await db.execute(text("""
        SELECT market_category, ai_investment_level, COUNT(*) as cnt
        FROM job_intelligence
        WHERE market_category IS NOT NULL AND ai_investment_level IS NOT NULL
        GROUP BY market_category, ai_investment_level
        ORDER BY market_category, cnt DESC
    """))).fetchall()

    ai_tools = (await db.execute(text("""
        SELECT LOWER(tool) as tool, COUNT(*) as mentions
        FROM job_intelligence, jsonb_array_elements_text(tech_stack->'ai_ml') as tool
        WHERE jsonb_typeof(tech_stack->'ai_ml') = 'array'
              AND tool IS NOT NULL AND tool != ''
        GROUP BY LOWER(tool)
        ORDER BY mentions DESC LIMIT 20
    """))).fetchall()

    ai_roles = (await db.execute(text("""
        SELECT role_category, COUNT(*) as cnt,
               AVG(salary_min_usd)::int as avg_salary_min,
               AVG(salary_max_usd)::int as avg_salary_max
        FROM job_intelligence
        WHERE ai_investment_level IN ('core_product', 'significant')
              AND role_category IS NOT NULL
        GROUP BY role_category ORDER BY cnt DESC
    """))).fetchall()

    return {
        "ai_by_market": [
            {"market": r[0], "ai_level": r[1], "count": r[2]}
            for r in ai_by_market
        ],
        "top_ai_tools": [
            {"tool": r[0], "mentions": r[1]}
            for r in ai_tools
        ],
        "roles_at_ai_companies": [
            {"role": r[0], "count": r[1], "avg_salary_min": r[2], "avg_salary_max": r[3]}
            for r in ai_roles
        ],
    }


@router.get("/company-stages")
async def company_stages(db: AsyncSession = Depends(get_db)):
    """Hiring by company stage — seed vs growth vs public."""
    stages = (await db.execute(text("""
        SELECT company_stage, COUNT(*) as jobs,
               COUNT(DISTINCT jl.company) as companies,
               AVG(ji.salary_min_usd)::int as avg_salary_min,
               AVG(ji.salary_max_usd)::int as avg_salary_max
        FROM job_intelligence ji
        JOIN job_listings jl ON jl.id = ji.job_listing_id
        WHERE company_stage IS NOT NULL AND company_stage != 'unknown'
        GROUP BY company_stage ORDER BY jobs DESC
    """))).fetchall()

    return {
        "stages": [
            {
                "stage": r[0],
                "jobs": r[1],
                "companies": r[2],
                "avg_salary_min": r[3],
                "avg_salary_max": r[4],
            }
            for r in stages
        ],
    }


@router.get("/benefits-culture")
async def benefits_culture(db: AsyncSession = Depends(get_db)):
    """Most common benefits and culture signals."""
    # Normalize: replace underscores with spaces, trim, lowercase, then aggregate
    benefits = (await db.execute(text("""
        SELECT LOWER(REPLACE(b, '_', ' ')) as benefit, COUNT(*) as cnt
        FROM job_intelligence, jsonb_array_elements_text(benefits) as b
        WHERE jsonb_typeof(benefits) = 'array'
              AND b IS NOT NULL AND b != ''
        GROUP BY LOWER(REPLACE(b, '_', ' ')) ORDER BY cnt DESC LIMIT 20
    """))).fetchall()

    culture = (await db.execute(text("""
        SELECT LOWER(REPLACE(c, '_', ' ')) as signal, COUNT(*) as cnt
        FROM job_intelligence, jsonb_array_elements_text(culture_signals) as c
        WHERE jsonb_typeof(culture_signals) = 'array'
              AND c IS NOT NULL AND c != ''
        GROUP BY LOWER(REPLACE(c, '_', ' ')) ORDER BY cnt DESC LIMIT 20
    """))).fetchall()

    return {
        "top_benefits": [{"benefit": r[0], "count": r[1]} for r in benefits],
        "top_culture_signals": [{"signal": r[0], "count": r[1]} for r in culture],
    }
