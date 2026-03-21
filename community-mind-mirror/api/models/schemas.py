"""Pydantic response models for the Intelligence Dashboard API."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Generic pagination wrapper ──────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    page: int
    per_page: int
    items: list[T]


# ── Users & Personas ────────────────────────────────────────────────

class UserResponse(BaseModel):
    id: int
    platform_id: int | None = None
    platform_name: str | None = None
    platform_user_id: str | None = None
    username: str | None = None
    bio: str | None = None
    profile_url: str | None = None
    karma_score: int | None = None
    account_created_at: datetime | None = None
    is_active: bool | None = None

    model_config = {"from_attributes": True}


class PersonaResponse(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    platform_name: str | None = None
    core_beliefs: list[dict] | None = None
    communication_style: dict | None = None
    emotional_triggers: dict | None = None
    expertise_domains: list[dict] | None = None
    influence_type: str | None = None
    influence_score: float | None = None
    inferred_location: str | None = None
    inferred_role: str | None = None
    personality_summary: str | None = None
    active_topics: list[str] | None = None
    system_prompt: str | None = None
    validation_score: float | None = None
    model_used: str | None = None
    extracted_at: datetime | None = None

    model_config = {"from_attributes": True}


class PersonaDetailResponse(PersonaResponse):
    top_posts: list["PostResponse"] = []
    connections: list["GraphEdgeResponse"] = []


# ── Posts ────────────────────────────────────────────────────────────

class PostResponse(BaseModel):
    id: int
    user_id: int | None = None
    username: str | None = None
    platform_id: int | None = None
    platform_name: str | None = None
    post_type: str | None = None
    title: str | None = None
    body: str | None = None
    url: str | None = None
    subreddit: str | None = None
    score: int | None = None
    num_comments: int | None = None
    posted_at: datetime | None = None
    sentiment: dict | None = None

    model_config = {"from_attributes": True}


# ── Topics ───────────────────────────────────────────────────────────

class TopicResponse(BaseModel):
    id: int
    name: str
    slug: str | None = None
    description: str | None = None
    keywords: list[str] | None = None
    velocity: float | None = None
    total_mentions: int | None = None
    sentiment_distribution: dict | None = None
    platforms_active: dict | None = None
    opinion_camps: list[dict] | None = None
    status: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None

    model_config = {"from_attributes": True}


class TopicDetailResponse(TopicResponse):
    top_posts: list[PostResponse] = []
    related_news: list["NewsEventResponse"] = []


class TopicTimelinePoint(BaseModel):
    date: str
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    avg_sentiment: float | None = None


class TopicTimelineResponse(BaseModel):
    topic_id: int
    topic_name: str
    timeline: list[TopicTimelinePoint]


# ── News ─────────────────────────────────────────────────────────────

class NewsEventResponse(BaseModel):
    id: int
    source_type: str
    source_name: str | None = None
    title: str
    body: str | None = None
    url: str | None = None
    authors: list | None = None
    published_at: datetime | None = None
    categories: list | None = None
    entities: dict | None = None
    sentiment: float | None = None
    magnitude: str | None = None

    model_config = {"from_attributes": True}


class NewsImpactResponse(BaseModel):
    event: NewsEventResponse
    reactions: list[dict] = []
    platforms_reacted: list[str] = []
    avg_community_sentiment: float | None = None


# ── Dashboard composites ─────────────────────────────────────────────

class DashboardPulseResponse(BaseModel):
    topics: list[TopicResponse]


class DashboardDebateResponse(BaseModel):
    debates: list[dict]


class LeaderResponse(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    platform_name: str | None = None
    influence_score: float | None = None
    inferred_role: str | None = None
    inferred_location: str | None = None
    personality_summary: str | None = None
    core_beliefs: list[dict] | None = None
    active_topics: list[str] | None = None

    model_config = {"from_attributes": True}


class ResearchRadarResponse(BaseModel):
    papers: list[NewsEventResponse]


class FundingSignalResponse(BaseModel):
    events: list[NewsEventResponse]


class JobTrendResponse(BaseModel):
    weekly_counts: list[dict] = []
    recent_listings: list[dict] = []
    role_cards: list[dict] = []


class GeoDistributionResponse(BaseModel):
    locations: list[dict]


class GraphEdgeResponse(BaseModel):
    connected_user_id: int
    connected_username: str | None = None
    interaction_type: str | None = None
    interaction_count: int | None = None
    avg_sentiment: float | None = None


class OverviewResponse(BaseModel):
    total_users: int = 0
    total_personas: int = 0
    total_posts: int = 0
    total_topics: int = 0
    news_by_source: dict = {}
    trending_topics: list[TopicResponse] = []
    top_leaders: list[LeaderResponse] = []
    latest_news: list[NewsEventResponse] = []
    scraper_health: list[dict] = []


class SearchResults(BaseModel):
    posts: list[PostResponse] = []
    news: list[NewsEventResponse] = []
    topics: list[TopicResponse] = []
    users: list[UserResponse] = []


# ── Intelligence: Products ──────────────────────────────────────────

class ProductResponse(BaseModel):
    id: int
    canonical_name: str
    category: str | None = None
    aliases: list[str] | None = None
    confidence: float | None = None
    status: str | None = None
    discovered_by: str | None = None
    total_mentions: int | None = 0
    last_seen_at: datetime | None = None
    recommendation_rate: float | None = None
    avg_sentiment: float | None = None
    trend: str | None = None  # "up", "down", "stable"

    model_config = {"from_attributes": True}


class ProductMentionResponse(BaseModel):
    id: int
    product_id: int
    product_name: str | None = None
    post_id: int | None = None
    news_event_id: int | None = None
    context_type: str | None = None
    sentiment: float | None = None
    detected_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Intelligence: Migrations ────────────────────────────────────────

class MigrationResponse(BaseModel):
    id: int
    from_product: str
    to_product: str
    from_product_id: int | None = None
    to_product_id: int | None = None
    reason: str | None = None
    confidence: float | None = None
    confirmed_by: str | None = None
    count: int = 1
    detected_at: datetime | None = None

    model_config = {"from_attributes": True}


class MigrationAggregateResponse(BaseModel):
    from_product: str
    to_product: str
    count: int
    avg_confidence: float | None = None


# ── Intelligence: Pain Points ───────────────────────────────────────

class PainPointResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    intensity_score: float | None = None
    has_solution: bool | None = None
    mentioned_products: list[str] | None = None
    platforms: list[str] | None = None
    sample_quotes: list[str] | None = None
    topic_id: int | None = None
    topic_name: str | None = None
    post_count: int | None = None
    status: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Dashboard: Hype Index ───────────────────────────────────────────

class HypeIndexResponse(BaseModel):
    id: int
    topic_id: int | None = None
    sector_name: str | None = None
    topic_name: str | None = None
    builder_sentiment: float | None = None
    vc_sentiment: float | None = None
    gap: float | None = None
    status: str | None = None  # aligned, overhyped, underhyped
    builder_post_count: int | None = None
    vc_post_count: int | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Dashboard: Leader Shifts ────────────────────────────────────────

class LeaderShiftResponse(BaseModel):
    id: int
    persona_id: int | None = None
    persona_name: str | None = None
    topic_id: int | None = None
    topic_name: str | None = None
    old_stance: str | None = None
    new_stance: str | None = None
    shift_type: str | None = None
    trigger: str | None = None
    summary: str | None = None
    old_sentiment: float | None = None
    new_sentiment: float | None = None
    detected_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Dashboard: Funding Rounds ───────────────────────────────────────

class FundingRoundResponse(BaseModel):
    id: int
    company_name: str
    amount: str | None = None
    stage: str | None = None
    sector: str | None = None
    location: str | None = None
    news_event_id: int | None = None
    community_sentiment: float | None = None
    community_post_count: int | None = None
    reaction_summary: str | None = None
    announced_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Topics: Platform Tones ──────────────────────────────────────────

class PlatformToneResponse(BaseModel):
    id: int
    topic_id: int | None = None
    platform_name: str | None = None
    tone_description: str | None = None
    post_count: int | None = None
    avg_sentiment: float | None = None
    analyzed_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Signals: Cross-Source Intelligence ────────────────────────────

class ResearchPipelineResponse(BaseModel):
    id: int
    paper_title: str
    arxiv_id: str | None = None
    published_at: datetime | None = None
    current_stage: str | None = None
    pipeline_velocity: str | None = None
    github_repos: list | None = None
    github_first_impl_at: datetime | None = None
    hf_model_ids: list | None = None
    hf_total_downloads: int | None = 0
    hf_first_upload_at: datetime | None = None
    community_mention_count: int | None = 0
    community_sentiment: float | None = None
    community_first_mention_at: datetime | None = None
    ph_launches: list | None = None
    ph_first_launch_at: datetime | None = None
    so_question_count: int | None = 0
    days_paper_to_code: int | None = None
    days_code_to_adoption: int | None = None
    days_total_pipeline: int | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TractionScoreResponse(BaseModel):
    id: int
    entity_name: str
    entity_type: str | None = None
    traction_score: float | None = None
    traction_label: str | None = None
    ph_votes: int | None = 0
    gh_stars: int | None = 0
    gh_star_velocity: float | None = 0
    gh_non_founder_contributors: int | None = 0
    pypi_monthly_downloads: int | None = 0
    npm_monthly_downloads: int | None = 0
    organic_mentions: int | None = 0
    self_promo_mentions: int | None = 0
    job_listings: int | None = 0
    recommendation_rate: float | None = None
    score_breakdown: dict | None = None
    red_flags: list | None = None
    reasoning: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TechnologyLifecycleResponse(BaseModel):
    id: int
    technology_name: str
    current_stage: str | None = None
    stage_evidence: dict | None = None
    arxiv_paper_count: int | None = 0
    github_repo_count: int | None = 0
    hf_model_count: int | None = 0
    so_question_count: int | None = 0
    so_question_type: str | None = None
    job_listing_count: int | None = 0
    job_listing_type: str | None = None
    community_mention_count: int | None = 0
    community_sentiment_trajectory: dict | None = None
    pypi_download_trend: dict | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MarketGapResponse(BaseModel):
    id: int
    problem_title: str
    pain_score: float | None = None
    complaint_count: int | None = 0
    existing_products: int | None = 0
    existing_product_names: list | None = None
    total_funding_in_space: float | None = 0
    funded_startups: list | None = None
    job_postings_related: int | None = 0
    yc_batch_presence: float | None = 0
    gap_signal: str | None = None
    opportunity_score: float | None = None
    reasoning: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompetitiveThreatResponse(BaseModel):
    id: int
    target_product: str
    competitor: str
    migrations_away: int | None = 0
    competitor_gh_velocity: float | None = 0
    competitor_hiring: int | None = 0
    competitor_sentiment: float | None = 0
    competitor_sentiment_trend: float | None = None
    opinion_leaders_flipped: int | None = 0
    threat_score: float | None = None
    threat_summary: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PlatformDivergenceResponse(BaseModel):
    id: int
    topic_name: str
    reddit_sentiment: float | None = None
    hn_sentiment: float | None = None
    youtube_sentiment: float | None = None
    ph_sentiment: float | None = None
    max_divergence: float | None = None
    divergence_direction: str | None = None
    prediction: str | None = None
    status: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class NarrativeShiftResponse(BaseModel):
    id: int
    topic_name: str
    topic_id: int | None = None
    shift_type: str | None = None
    shift_velocity: str | None = None
    older_frame: str | None = None
    recent_frame: str | None = None
    media_alignment: str | None = None
    prediction: str | None = None
    confidence: str | None = None
    narrative_timeline: list | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class SmartMoneyResponse(BaseModel):
    id: int
    sector: str
    yc_companies_last_batch: int | None = None
    yc_trend: str | None = None
    yc_percentage_of_batch: float | None = None
    vc_funding_articles: int | None = None
    vc_signal: str | None = None
    builder_repos: int | None = None
    builder_stars: int | None = None
    community_posts_30d: int | None = None
    classification: str | None = None
    reasoning: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TalentFlowResponse(BaseModel):
    id: int
    skill: str
    category: str | None = None
    demand_score: int | None = None
    supply_score: int | None = None
    gap: int | None = None
    salary_pressure: str | None = None
    trend: str | None = None
    job_listings_30d: int | None = None
    so_questions_30d: int | None = None
    reasoning: str | None = None
    prediction: str | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class InsightCardResponse(BaseModel):
    category: str | None = None
    color: str | None = None
    insight: str | None = None
    signals_used: list[str] | None = None
    confidence: str | None = None
    recommended_action: str | None = None


class SignalSummaryResponse(BaseModel):
    total_signals: dict[str, int]
    top_opportunities: list[dict]
    top_threats: list[dict]
    top_skill_gaps: list[dict]
    smart_money_early: list[dict]
    narrative_shifts: list[dict]
    insights: list[InsightCardResponse]


# ── Agents: Management & Monitoring ───────────────────────────────

class AgentRunResponse(BaseModel):
    id: int
    agent_name: str
    status: str | None = None
    duration_seconds: float | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    records_produced: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AgentRunDetailResponse(AgentRunResponse):
    output: str | None = None
    output_json: dict | None = None
    error_message: str | None = None


class AgentStatusResponse(BaseModel):
    agent_name: str
    model: str | None = None
    schedule_hours: int | None = None
    last_run: AgentRunResponse | None = None
    total_runs: int = 0
    success_rate: float | None = None


class AgentCostResponse(BaseModel):
    agent_name: str
    total_runs: int = 0
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    avg_duration_seconds: float | None = None


# ── Source Data: Third-Party ──────────────────────────────────────

class GithubRepoResponse(BaseModel):
    id: int
    repo_full_name: str
    name: str | None = None
    description: str | None = None
    stars: int | None = 0
    forks: int | None = 0
    language: str | None = None
    topics: list | None = None
    star_velocity: float | None = None
    contributor_count: int | None = None
    license: str | None = None
    pushed_at: datetime | None = None
    last_scraped_at: datetime | None = None

    model_config = {"from_attributes": True}


class HFModelResponse(BaseModel):
    id: int
    model_id: str
    pipeline_tag: str | None = None
    downloads: int | None = 0
    likes: int | None = 0
    tags: list | None = None
    library_name: str | None = None
    downloads_last_week: int | None = None
    trending_score: float | None = None
    last_modified: datetime | None = None

    model_config = {"from_attributes": True}


class PackageDownloadResponse(BaseModel):
    package_name: str
    registry: str
    total_downloads_30d: int = 0
    latest_daily: int = 0
    trend: str | None = None  # "up", "down", "stable"


class YCCompanyResponse(BaseModel):
    id: int
    slug: str
    name: str | None = None
    description: str | None = None
    batch: str | None = None
    status: str | None = None
    industries: list | None = None
    regions: list | None = None
    team_size: str | None = None
    website: str | None = None

    model_config = {"from_attributes": True}


class SOQuestionResponse(BaseModel):
    id: int
    so_question_id: int
    title: str | None = None
    tags: list | None = None
    view_count: int | None = 0
    answer_count: int | None = 0
    score: int | None = 0
    is_answered: bool | None = None
    link: str | None = None
    creation_date: datetime | None = None

    model_config = {"from_attributes": True}


class PHLaunchResponse(BaseModel):
    id: int
    ph_id: str | None = None
    name: str
    tagline: str | None = None
    description: str | None = None
    votes_count: int | None = 0
    comments_count: int | None = 0
    website: str | None = None
    topics: list | None = None
    launched_at: datetime | None = None

    model_config = {"from_attributes": True}


class CrossSourceHighlight(BaseModel):
    type: str  # "insight", "alert", "trend"
    title: str
    description: str | None = None
    confidence: str | None = None
    signals_used: list[str] | None = None
    color: str | None = None


# ── Product Reviews ────────────────────────────────────────────────

class ProductReviewResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    overall_sentiment: str | None = None
    satisfaction_score: int | None = None
    pros: list[str] | None = None
    cons: list[str] | None = None
    common_use_cases: list[str] | None = None
    feature_requests: list[str] | None = None
    churn_reasons: list[str] | None = None
    competitor_comparisons: list[dict] | None = None
    post_count: int | None = 0
    source_subreddits: list[str] | None = None
    calculated_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Gig Board ──────────────────────────────────────────────────────

class GigPostResponse(BaseModel):
    id: int
    post_id: int | None = None
    project_type: str | None = None
    gig_title: str | None = None
    need_description: str | None = None
    need_category: str | None = None
    skills_required: list[str] | None = None
    budget_text: str | None = None
    budget_min_usd: float | None = None
    budget_max_usd: float | None = None
    pay_type: str | None = None
    tech_stack: list[str] | None = None
    experience_level: str | None = None
    remote_policy: str | None = None
    location: str | None = None
    start_time: str | None = None
    project_duration: str | None = None
    industry: str | None = None
    company_name: str | None = None
    contact_method: str | None = None
    equity_offered: bool | None = None
    poster_username: str | None = None
    source_url: str | None = None
    source_subreddit: str | None = None
    posted_at: datetime | None = None
    extracted_at: datetime | None = None

    model_config = {"from_attributes": True}


# ── Custom Market Research ────────────────────────────────────


class ResearchProjectCreate(BaseModel):
    name: str
    description: str | None = None
    initial_terms: list[str]


class ResearchProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    initial_terms: list[str] | None = None
    expanded_keywords: list[str] | None = None
    status: str = "draft"
    post_count: int = 0
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ResearchInsightsResponse(BaseModel):
    id: int
    project_id: int
    discussion_summary: str | None = None
    overall_sentiment: str | None = None
    sentiment_breakdown: dict | None = None
    products_mentioned: list[dict] | None = None
    feature_requests: list[dict] | None = None
    unmet_needs: list[dict] | None = None
    key_themes: list[dict] | None = None
    calculated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ResearchContactResponse(BaseModel):
    id: int
    project_id: int
    user_id: int | None = None
    username: str
    platform: str = "reddit"
    post_count: int = 0
    avg_sentiment: float | None = None
    sentiment_leaning: str | None = None
    topics_discussed: list[str] | None = None
    sample_post_ids: list[int] | None = None
    profile_url: str | None = None

    model_config = {"from_attributes": True}
