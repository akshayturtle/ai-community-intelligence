const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// Types — matched to actual Pydantic schemas in api/models/schemas.py

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  per_page: number;
  items: T[];
}

export interface Topic {
  id: number;
  name: string;
  slug: string | null;
  description: string | null;
  keywords: string[] | null;
  velocity: number | null;
  total_mentions: number | null;
  sentiment_distribution: Record<string, number> | null;
  platforms_active: Record<string, number> | null;
  opinion_camps: Record<string, unknown>[] | null;
  status: string | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface TopicDetail extends Topic {
  top_posts: PostItem[];
  related_news: NewsEvent[];
}

export interface TimelinePoint {
  date: string;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  avg_sentiment: number | null;
}

export interface TopicTimeline {
  topic_id: number;
  topic_name: string;
  timeline: TimelinePoint[];
}

export interface PostItem {
  id: number;
  user_id: number | null;
  username: string | null;
  platform_id: number | null;
  platform_name: string | null;
  post_type: string | null;
  title: string | null;
  body: string | null;
  url: string | null;
  subreddit: string | null;
  score: number | null;
  num_comments: number | null;
  posted_at: string | null;
  sentiment: Record<string, unknown> | null;
}

export interface Persona {
  id: number;
  user_id: number;
  username: string | null;
  platform_name: string | null;
  personality_summary: string | null;
  inferred_role: string | null;
  expertise_domains: Record<string, unknown>[] | null;
  core_beliefs: Record<string, unknown>[] | null;
  communication_style: Record<string, unknown> | null;
  emotional_triggers: Record<string, unknown>[] | null;
  influence_score: number | null;
  inferred_location: string | null;
  active_topics: string[] | null;
  system_prompt: string | null;
  karma: number | null;
  post_count: number | null;
  first_seen: string | null;
}

export interface PersonaDetail extends Persona {
  top_posts: PostItem[];
  connections: GraphEdge[];
}

export interface NewsEvent {
  id: number;
  source_type: string;
  source_name: string | null;
  title: string;
  body: string | null;
  url: string | null;
  authors: unknown[] | null;
  published_at: string | null;
  categories: unknown[] | null;
  entities: Record<string, unknown> | null;
  sentiment: number | null;
  magnitude: string | null;
}

export interface NewsImpact {
  event: NewsEvent;
  reactions: Record<string, unknown>[];
  platforms_reacted: string[];
  avg_community_sentiment: number | null;
}

export interface Leader {
  id: number;
  user_id: number;
  username: string | null;
  platform_name: string | null;
  influence_score: number | null;
  inferred_role: string | null;
  inferred_location: string | null;
  personality_summary: string | null;
  core_beliefs: Record<string, unknown>[] | null;
  active_topics: string[] | null;
}

// Wrapper types matching actual API responses
interface PulseResponse { topics: Topic[] }
interface DebateResponse { debates: DebateItem[] }
interface ResearchResponse { papers: NewsEvent[] }
interface FundingResponse { events: NewsEvent[] }
interface GeoResponse { locations: GeoItem[] }

export interface DebateItem {
  id: number;
  name: string;
  slug: string;
  opinion_camps: unknown;
  sentiment_distribution: Record<string, number>;
  total_mentions: number;
  polarization_score: number;
}

export interface JobTrend {
  weekly_counts: { week: string; count: number }[];
  recent_listings: Record<string, unknown>[];
  role_cards?: { role: string; count: number; growth: number }[];
}

export interface GeoItem {
  location: string;
  user_count: number;
  avg_influence: number;
  top_topics: string[];
}

export interface GraphEdge {
  connected_user_id: number;
  connected_username: string | null;
  interaction_type: string | null;
  interaction_count: number | null;
  avg_sentiment: number | null;
}

export interface Overview {
  total_users: number;
  total_posts: number;
  total_personas: number;
  total_topics: number;
  news_by_source: Record<string, number>;
  trending_topics: Topic[];
  top_leaders: Leader[];
  latest_news: NewsEvent[];
  scraper_health: Record<string, unknown>[];
}

export interface SearchResults {
  posts: PostItem[];
  news: NewsEvent[];
  topics: Topic[];
  users: { id: number; username: string | null; platform_name: string | null }[];
}

// ── Intelligence Types ─────────────────────────────────────────

export interface Product {
  id: number;
  canonical_name: string;
  category: string | null;
  aliases: string[] | null;
  confidence: number | null;
  status: string | null;
  discovered_by: string | null;
  total_mentions: number;
  last_seen_at: string | null;
  recommendation_rate: number | null;
  avg_sentiment: number | null;
  trend: string | null;
}

export interface MigrationAggregate {
  from_product: string;
  to_product: string;
  count: number;
  avg_confidence: number | null;
}

export interface Migration {
  id: number;
  from_product: string;
  to_product: string;
  from_product_id: number | null;
  to_product_id: number | null;
  reason: string | null;
  confidence: number | null;
  confirmed_by: string | null;
  count: number;
  detected_at: string | null;
}

export interface PainPoint {
  id: number;
  title: string;
  description: string | null;
  intensity_score: number | null;
  has_solution: boolean | null;
  mentioned_products: string[] | null;
  platforms: string[] | null;
  sample_quotes: string[] | null;
  topic_id: number | null;
  topic_name: string | null;
  post_count: number | null;
  status: string | null;
  created_at: string | null;
}

export interface HypeIndexItem {
  id: number;
  topic_id: number | null;
  sector_name: string | null;
  topic_name: string | null;
  builder_sentiment: number | null;
  vc_sentiment: number | null;
  gap: number | null;
  status: string | null;
  builder_post_count: number | null;
  vc_post_count: number | null;
  calculated_at: string | null;
}

export interface LeaderShift {
  id: number;
  persona_id: number | null;
  persona_name: string | null;
  topic_id: number | null;
  topic_name: string | null;
  old_stance: string | null;
  new_stance: string | null;
  shift_type: string | null;
  trigger: string | null;
  summary: string | null;
  old_sentiment: number | null;
  new_sentiment: number | null;
  detected_at: string | null;
}

export interface FundingRound {
  id: number;
  company_name: string;
  amount: string | null;
  stage: string | null;
  sector: string | null;
  location: string | null;
  news_event_id: number | null;
  community_sentiment: number | null;
  community_post_count: number | null;
  reaction_summary: string | null;
  announced_at: string | null;
}

export interface PlatformTone {
  id: number;
  topic_id: number | null;
  platform_name: string | null;
  tone_description: string | null;
  post_count: number | null;
  avg_sentiment: number | null;
  analyzed_at: string | null;
}

export interface JobAnalysis {
  total_listings_90d: number;
  role_trends: { role: string; total_90d: number; total_30d: number }[];
  geo_breakdown: { location: string; count: number }[];
}

// ── Job Intelligence Types (LLM-extracted) ────────────────────

export interface JobIntelSummary {
  total_jobs: number;
  total_processed: number;
  coverage_pct: number;
  by_role: { role: string; count: number }[];
  by_seniority: { seniority: string; count: number }[];
  by_market: { market: string; count: number }[];
  by_ai_level: { level: string; count: number }[];
  by_remote_policy: { policy: string; count: number }[];
}

export interface TechStackItem {
  name: string;
  category: string;
  mentions: number;
}

export interface SalaryBand {
  role: string;
  seniority: string;
  sample_size: number;
  p25_min: number | null;
  median_min: number | null;
  p75_max: number | null;
  median_max: number | null;
  avg_min: number | null;
  avg_max: number | null;
}

export interface HiringVelocityCompany {
  company: string;
  open_roles: number;
  market: string | null;
  stage: string | null;
  ai_level: string | null;
  role_types: string[];
  urgent_roles: number;
}

export interface JobGeoData {
  by_country: { country: string; count: number; remote_count: number }[];
  by_city: { city: string; country: string; count: number }[];
}

export interface AILandscape {
  ai_by_market: { market: string; ai_level: string; count: number }[];
  top_ai_tools: { tool: string; mentions: number }[];
  roles_at_ai_companies: { role: string; count: number; avg_salary_min: number | null; avg_salary_max: number | null }[];
}

export interface CompanyStage {
  stage: string;
  jobs: number;
  companies: number;
  avg_salary_min: number | null;
  avg_salary_max: number | null;
}

export interface BenefitsCulture {
  top_benefits: { benefit: string; count: number }[];
  top_culture_signals: { signal: string; count: number }[];
}

export interface SkillDemand {
  skill: string;
  type: string;
  mentions: number;
}

// ── Cross-Source Signal Types ─────────────────────────────────

export interface ResearchPipelineItem {
  id: number;
  paper_title: string;
  arxiv_id: string | null;
  published_at: string | null;
  current_stage: string | null;
  pipeline_velocity: string | null;
  github_repos: number | null;
  github_first_impl_at: string | null;
  hf_model_ids: string[] | null;
  hf_total_downloads: number | null;
  hf_first_upload_at: string | null;
  community_mention_count: number | null;
  community_sentiment: number | null;
  community_first_mention_at: string | null;
  ph_launches: number | null;
  ph_first_launch_at: string | null;
  so_question_count: number | null;
  days_paper_to_code: number | null;
  days_code_to_adoption: number | null;
  days_total_pipeline: number | null;
  updated_at: string | null;
}

export interface TractionScoreItem {
  id: number;
  entity_name: string;
  entity_type: string | null;
  traction_score: number | null;
  traction_label: string | null;
  ph_votes: number | null;
  gh_stars: number | null;
  gh_star_velocity: number | null;
  gh_non_founder_contributors: number | null;
  pypi_monthly_downloads: number | null;
  npm_monthly_downloads: number | null;
  organic_mentions: number | null;
  self_promo_mentions: number | null;
  job_listings: number | null;
  recommendation_rate: number | null;
  score_breakdown: Record<string, unknown> | null;
  red_flags: string[] | null;
  reasoning: string | null;
  calculated_at: string | null;
}

export interface TechnologyLifecycleItem {
  id: number;
  technology_name: string;
  current_stage: string | null;
  stage_evidence: Record<string, unknown> | null;
  arxiv_paper_count: number | null;
  github_repo_count: number | null;
  hf_model_count: number | null;
  so_question_count: number | null;
  so_question_type: string | null;
  job_listing_count: number | null;
  job_listing_type: string | null;
  community_mention_count: number | null;
  community_sentiment_trajectory: Record<string, unknown> | null;
  pypi_download_trend: Record<string, unknown> | null;
  calculated_at: string | null;
}

export interface MarketGapItem {
  id: number;
  problem_title: string;
  pain_score: number | null;
  complaint_count: number | null;
  existing_products: number | null;
  existing_product_names: string[] | null;
  total_funding_in_space: number | null;
  funded_startups: number | null;
  job_postings_related: number | null;
  yc_batch_presence: number | null;
  gap_signal: string | null;
  opportunity_score: number | null;
  reasoning: string | null;
  calculated_at: string | null;
}

export interface CompetitiveThreatItem {
  id: number;
  target_product: string;
  competitor: string;
  migrations_away: number | null;
  competitor_gh_velocity: number | null;
  competitor_hiring: number | null;
  competitor_sentiment: number | null;
  competitor_sentiment_trend: string | null;
  opinion_leaders_flipped: number | null;
  threat_score: number | null;
  threat_summary: string | null;
  calculated_at: string | null;
}

export interface PlatformDivergenceItem {
  id: number;
  topic_name: string;
  reddit_sentiment: number | null;
  hn_sentiment: number | null;
  youtube_sentiment: number | null;
  ph_sentiment: number | null;
  max_divergence: number | null;
  divergence_direction: string | null;
  prediction: string | null;
  status: string | null;
  calculated_at: string | null;
}

export interface SmartMoneyItem {
  id: number;
  sector: string;
  yc_companies_last_batch: number | null;
  yc_trend: string | null;
  yc_percentage_of_batch: number | null;
  vc_funding_articles: number | null;
  vc_signal: string | null;
  builder_repos: number | null;
  builder_stars: number | null;
  community_posts_30d: number | null;
  classification: string | null;
  reasoning: string | null;
  calculated_at: string | null;
}

export interface TalentFlowItem {
  id: number;
  skill: string;
  category: string | null;
  demand_score: number | null;
  supply_score: number | null;
  gap: number | null;
  salary_pressure: string | null;
  trend: string | null;
  job_listings_30d: number | null;
  so_questions_30d: number | null;
  reasoning: string | null;
  prediction: string | null;
  calculated_at: string | null;
}

export interface NarrativeShiftItem {
  id: number;
  topic_name: string;
  topic_id: number | null;
  shift_type: string | null;
  shift_velocity: string | null;
  older_frame: string | null;
  recent_frame: string | null;
  media_alignment: string | null;
  prediction: string | null;
  confidence: string | null;
  narrative_timeline: unknown[] | null;
  calculated_at: string | null;
}

export interface SignalSummary {
  total_signals: Record<string, number>;
  top_opportunities: { problem_title: string; opportunity_score: number | null; gap_signal: string | null; complaint_count: number | null }[];
  top_threats: { target_product: string; competitor: string; threat_score: number | null; migrations_away: number | null }[];
  top_skill_gaps: { skill: string; gap: number | null; salary_pressure: string | null; trend: string | null; demand_score: number | null; supply_score: number | null }[];
  smart_money_early: { sector: string; yc_companies_last_batch: number | null; yc_trend: string | null; vc_signal: string | null; builder_repos: number | null }[];
  narrative_shifts: { topic_name: string; shift_type: string | null; shift_velocity: string | null; older_frame: string | null; recent_frame: string | null }[];
  insights: InsightCard[];
}

export interface InsightCard {
  category: string | null;
  color: string | null;
  insight: string | null;
  signals_used: string[] | null;
  confidence: string | null;
  recommended_action: string | null;
}

export interface AgentOutput {
  agent: string;
  data: unknown;
  last_run: string | null;
  duration_seconds: number | null;
  tokens_used: number | null;
}

export interface CrossSourceHighlight {
  type: string;
  title: string;
  description: string | null;
  confidence: string | null;
  signals_used: string[] | null;
  color: string | null;
}

// ── Agent Management Types ────────────────────────────────────

export interface AgentRun {
  id: number;
  agent_name: string;
  status: string;
  duration_seconds: number | null;
  tokens_used: number | null;
  cost_usd: number | null;
  records_produced: number | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface AgentRunDetail extends AgentRun {
  output: string | null;
  output_json: unknown;
  error_message: string | null;
}

export interface AgentStatus {
  agent_name: string;
  model: string | null;
  schedule_hours: number | null;
  last_run: AgentRun | null;
  total_runs: number;
  success_rate: number | null;
}

export interface AgentCost {
  agent_name: string;
  total_runs: number;
  total_tokens: number | null;
  total_cost_usd: number | null;
  avg_duration_seconds: number | null;
}

// ── Source Data Types ─────────────────────────────────────────

export interface GithubRepo {
  id: number;
  full_name: string;
  description: string | null;
  language: string | null;
  stars: number | null;
  forks: number | null;
  star_velocity_7d: number | null;
  topics: string[] | null;
  pushed_at: string | null;
  scraped_at: string | null;
}

export interface HFModel {
  id: number;
  model_id: string;
  author: string | null;
  pipeline_tag: string | null;
  library_name: string | null;
  downloads: number | null;
  likes: number | null;
  trending_score: number | null;
  tags: string[] | null;
  scraped_at: string | null;
}

export interface PackageDownloadTrend {
  package_name: string;
  registry: string | null;
  total_downloads_30d: number;
  latest_daily: number | null;
  trend: string | null;
}

export interface YCCompany {
  id: number;
  name: string;
  slug: string | null;
  batch: string | null;
  status: string | null;
  one_liner: string | null;
  industry: string[] | null;
  website: string | null;
  team_size: number | null;
  scraped_at: string | null;
}

export interface SOQuestion {
  id: number;
  question_id: number;
  title: string;
  tags: string[] | null;
  view_count: number | null;
  answer_count: number | null;
  score: number | null;
  is_answered: boolean | null;
  creation_date: string | null;
  scraped_at: string | null;
}

export interface PHLaunch {
  id: number;
  name: string;
  tagline: string | null;
  description: string | null;
  url: string | null;
  votes_count: number | null;
  comments_count: number | null;
  topics: string[] | null;
  thumbnail_url: string | null;
  featured_at: string | null;
  scraped_at: string | null;
}

// ── Product Review Types ─────────────────────────────────────

export interface ProductReviewItem {
  id: number;
  product_id: number;
  product_name: string;
  overall_sentiment: string | null;
  satisfaction_score: number | null;
  pros: string[] | null;
  cons: string[] | null;
  common_use_cases: string[] | null;
  feature_requests: string[] | null;
  churn_reasons: string[] | null;
  competitor_comparisons: { competitor: string; context: string }[] | null;
  post_count: number | null;
  source_subreddits: string[] | null;
  calculated_at: string | null;
  updated_at: string | null;
}

export interface ProductReviewSummary {
  total_reviews: number;
  sentiment_distribution: Record<string, number>;
  avg_satisfaction: number | null;
  top_rated: { product: string; score: number }[];
  top_feature_requests: { request: string; count: number }[];
  top_churn_reasons: { reason: string; count: number }[];
}

// ── Gig Board Types ─────────────────────────────────────────

export interface GigPostItem {
  id: number;
  post_id: number | null;
  project_type: string | null;
  need_description: string | null;
  need_category: string | null;
  budget_text: string | null;
  budget_min_usd: number | null;
  budget_max_usd: number | null;
  tech_stack: string[] | null;
  experience_level: string | null;
  remote_policy: string | null;
  project_duration: string | null;
  industry: string | null;
  contact_method: string | null;
  poster_username: string | null;
  source_url: string | null;
  source_subreddit: string | null;
  posted_at: string | null;
  extracted_at: string | null;
}

export interface GigSummary {
  total_gigs: number;
  by_project_type: Record<string, number>;
  by_need_category: Record<string, number>;
  budget: { avg_min: number | null; avg_max: number | null; min: number | null; max: number | null };
  top_tech_stacks: { tech: string; count: number }[];
  by_remote_policy: Record<string, number>;
}

export interface GigTrends {
  weekly_trend: { week: string; count: number }[];
}

// ── Custom Market Research Types ─────────────────────────────

export interface ResearchProject {
  id: number;
  name: string;
  description: string | null;
  initial_terms: string[] | null;
  expanded_keywords: string[] | null;
  status: string;
  post_count: number;
  error_message: string | null;
  created_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
}

export interface ResearchProjectCreate {
  name: string;
  description?: string;
  initial_terms: string[];
}

export interface ResearchInsights {
  id: number;
  project_id: number;
  discussion_summary: string | null;
  overall_sentiment: string | null;
  sentiment_breakdown: Record<string, number> | null;
  products_mentioned: { name: string; pros: string[]; cons: string[]; mention_count: number }[] | null;
  feature_requests: { description: string; frequency: string; source_count: number }[] | null;
  unmet_needs: { description: string; intensity: string; evidence: string }[] | null;
  key_themes: { theme: string; post_count: number; sentiment: string }[] | null;
  calculated_at: string | null;
}

export interface ResearchContact {
  id: number;
  project_id: number;
  user_id: number | null;
  username: string;
  platform: string;
  post_count: number;
  avg_sentiment: number | null;
  sentiment_leaning: string | null;
  topics_discussed: string[] | null;
  sample_post_ids: number[] | null;
  profile_url: string | null;
}

// API functions — unwrap wrappers to keep hooks simple
export const api = {
  // Dashboard
  overview: () => fetchJSON<Overview>("/dashboard/overview"),
  pulse: (params?: Record<string, string>) =>
    fetchJSON<PulseResponse>(`/dashboard/pulse?${new URLSearchParams(params)}`).then(r => r.topics),
  debates: () =>
    fetchJSON<DebateResponse>("/dashboard/debates").then(r => r.debates),
  leaders: (params?: Record<string, string>) =>
    fetchJSON<Leader[]>(`/dashboard/leaders?${new URLSearchParams(params)}`),
  research: () =>
    fetchJSON<ResearchResponse>("/dashboard/research").then(r => r.papers),
  funding: () =>
    fetchJSON<FundingResponse>("/dashboard/funding").then(r => r.events),
  jobs: () => fetchJSON<JobTrend>("/dashboard/jobs"),
  newsImpact: () => fetchJSON<NewsImpact[]>("/dashboard/news-impact"),
  geo: () =>
    fetchJSON<GeoResponse>("/dashboard/geo").then(r => r.locations),

  // Topics
  topics: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<Topic>>(`/topics?${new URLSearchParams(params)}`),
  topic: (id: number) => fetchJSON<TopicDetail>(`/topics/${id}`),
  topicTimeline: (id: number) => fetchJSON<TopicTimeline>(`/topics/${id}/timeline`),
  topicPosts: (id: number, params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<PostItem>>(`/topics/${id}/posts?${new URLSearchParams(params)}`),

  // Personas
  personas: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<Persona>>(`/personas?${new URLSearchParams(params)}`),
  persona: (id: number) => fetchJSON<PersonaDetail>(`/personas/${id}`),
  personaPosts: (id: number, params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<PostItem>>(`/personas/${id}/posts?${new URLSearchParams(params)}`),
  personaGraph: (id: number) => fetchJSON<GraphEdge[]>(`/personas/${id}/graph`),

  // News
  news: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<NewsEvent>>(`/news?${new URLSearchParams(params)}`),
  newsItem: (id: number) => fetchJSON<NewsEvent & { related_posts: PostItem[] }>(`/news/${id}`),

  // Search
  search: (q: string) => fetchJSON<SearchResults>(`/search?q=${encodeURIComponent(q)}`),

  // Intelligence
  products: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<Product>>(`/intelligence/products?${new URLSearchParams(params)}`),
  migrations: () =>
    fetchJSON<MigrationAggregate[]>("/intelligence/migrations"),
  unmetNeeds: () =>
    fetchJSON<PainPoint[]>("/intelligence/unmet-needs"),
  jobAnalysis: () =>
    fetchJSON<JobAnalysis>("/intelligence/job-analysis"),

  // Job Intelligence (LLM-extracted)
  jobIntelSummary: () =>
    fetchJSON<JobIntelSummary>("/job-intelligence/summary"),
  jobIntelTechStack: (params?: Record<string, string>) =>
    fetchJSON<{ filter_role: string | null; technologies: TechStackItem[] }>(`/job-intelligence/tech-stack?${new URLSearchParams(params)}`),
  jobIntelSalary: (params?: Record<string, string>) =>
    fetchJSON<{ filter_country: string | null; salary_bands: SalaryBand[] }>(`/job-intelligence/salary-insights?${new URLSearchParams(params)}`),
  jobIntelHiring: (params?: Record<string, string>) =>
    fetchJSON<{ companies: HiringVelocityCompany[] }>(`/job-intelligence/hiring-velocity?${new URLSearchParams(params)}`),
  jobIntelGeo: () =>
    fetchJSON<JobGeoData>("/job-intelligence/geographic"),
  jobIntelAI: () =>
    fetchJSON<AILandscape>("/job-intelligence/ai-landscape"),
  jobIntelStages: () =>
    fetchJSON<{ stages: CompanyStage[] }>("/job-intelligence/company-stages"),
  jobIntelBenefits: () =>
    fetchJSON<BenefitsCulture>("/job-intelligence/benefits-culture"),
  jobIntelSkills: (params?: Record<string, string>) =>
    fetchJSON<{ filter_role: string | null; skills: SkillDemand[] }>(`/job-intelligence/skills-demand?${new URLSearchParams(params)}`),

  // Dashboard Intelligence
  hypeIndex: (params?: Record<string, string>) =>
    fetchJSON<HypeIndexItem[]>(`/dashboard/hype-index?${new URLSearchParams(params)}`),
  painPoints: (params?: Record<string, string>) =>
    fetchJSON<PainPoint[]>(`/dashboard/pain-points?${new URLSearchParams(params)}`),
  leaderShifts: () =>
    fetchJSON<LeaderShift[]>("/dashboard/leader-shifts"),
  fundingRounds: (params?: Record<string, string>) =>
    fetchJSON<FundingRound[]>(`/dashboard/funding-rounds?${new URLSearchParams(params)}`),

  // Topic platform tones
  topicPlatformTones: (id: number) =>
    fetchJSON<PlatformTone[]>(`/topics/${id}/platform-tones`),

  // Health
  health: () => fetchJSON<{ status: string }>("/health"),
  stats: () => fetchJSON<Record<string, number>>("/stats"),

  // ── Cross-Source Signals ────────────────────────────────────────
  researchPipeline: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<ResearchPipelineItem>>(`/signals/research-pipeline?${new URLSearchParams(params)}`),
  tractionScores: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<TractionScoreItem>>(`/signals/traction-scores?${new URLSearchParams(params)}`),
  technologyLifecycle: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<TechnologyLifecycleItem>>(`/signals/technology-lifecycle?${new URLSearchParams(params)}`),
  marketGaps: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<MarketGapItem>>(`/signals/market-gaps?${new URLSearchParams(params)}`),
  competitiveThreats: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<CompetitiveThreatItem>>(`/signals/competitive-threats?${new URLSearchParams(params)}`),
  platformDivergence: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<PlatformDivergenceItem>>(`/signals/platform-divergence?${new URLSearchParams(params)}`),
  smartMoney: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<SmartMoneyItem>>(`/signals/smart-money?${new URLSearchParams(params)}`),
  talentFlow: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<TalentFlowItem>>(`/signals/talent-flow?${new URLSearchParams(params)}`),
  narrativeShifts: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<NarrativeShiftItem>>(`/signals/narrative-shifts?${new URLSearchParams(params)}`),
  signalSummary: () => fetchJSON<SignalSummary>("/signals/summary"),
  productDiscoveries: () => fetchJSON<AgentOutput>("/signals/product-discoveries"),
  insights: (params?: Record<string, string>) =>
    fetchJSON<InsightCard[]>(`/signals/insights?${new URLSearchParams(params)}`),
  crossSourceHighlights: () =>
    fetchJSON<CrossSourceHighlight[]>("/dashboard/cross-source-highlights"),
  agentOutput: (name: string) =>
    fetchJSON<AgentOutput>(`/signals/agent-output/${name}`),

  // ── Agent Management ────────────────────────────────────────────
  agentStatus: () => fetchJSON<AgentStatus[]>("/agents/status"),
  agentRuns: (params?: Record<string, string>) =>
    fetchJSON<AgentRun[]>(`/agents/runs?${new URLSearchParams(params)}`),
  agentRunDetail: (id: number) => fetchJSON<AgentRunDetail>(`/agents/runs/${id}`),
  triggerAgent: (name: string) =>
    fetchJSON<{ status: string; agent: string }>(`/agents/trigger/${name}`, { method: "POST" }),
  triggerAllAgents: () =>
    fetchJSON<{ status: string; agents: string }>("/agents/trigger-all", { method: "POST" }),
  agentCosts: (params?: Record<string, string>) =>
    fetchJSON<AgentCost[]>(`/agents/costs?${new URLSearchParams(params)}`),

  // ── Source Data ─────────────────────────────────────────────────
  githubTrending: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<GithubRepo>>(`/sources/github-trending?${new URLSearchParams(params)}`),
  hfTrending: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<HFModel>>(`/sources/hf-trending?${new URLSearchParams(params)}`),
  packageTrends: (params?: Record<string, string>) =>
    fetchJSON<PackageDownloadTrend[]>(`/sources/package-trends?${new URLSearchParams(params)}`),
  ycBatches: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<YCCompany>>(`/sources/yc-batches?${new URLSearchParams(params)}`),
  soTrends: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<SOQuestion>>(`/sources/so-trends?${new URLSearchParams(params)}`),
  phRecent: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<PHLaunch>>(`/sources/ph-recent?${new URLSearchParams(params)}`),

  // ── Product Reviews ───────────────────────────────────────────
  productReviews: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<ProductReviewItem>>(`/product-reviews/?${new URLSearchParams(params)}`),
  productReviewSummary: () =>
    fetchJSON<ProductReviewSummary>("/product-reviews/summary"),
  productReview: (productId: number) =>
    fetchJSON<ProductReviewItem>(`/product-reviews/${productId}`),

  // ── Gig Board ────────────────────────────────────────────────
  gigBoard: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<GigPostItem>>(`/gig-board/?${new URLSearchParams(params)}`),
  gigSummary: () =>
    fetchJSON<GigSummary>("/gig-board/summary"),
  gigTrends: () =>
    fetchJSON<GigTrends>("/gig-board/trends"),

  // ── Custom Market Research ────────────────────────────────────
  researchProjects: (params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<ResearchProject>>(`/research/?${new URLSearchParams(params)}`),
  researchProject: (id: number) =>
    fetchJSON<ResearchProject>(`/research/${id}`),
  createResearchProject: (data: ResearchProjectCreate) =>
    fetchJSON<ResearchProject>("/research/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  runResearch: (id: number) =>
    fetchJSON<{ status: string; project_id: number }>(`/research/${id}/run`, { method: "POST" }),
  researchInsights: (id: number) =>
    fetchJSON<ResearchInsights>(`/research/${id}/insights`),
  researchContacts: (id: number, params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<ResearchContact>>(`/research/${id}/contacts?${new URLSearchParams(params)}`),
  researchPosts: (id: number, params?: Record<string, string>) =>
    fetchJSON<PaginatedResponse<PostItem>>(`/research/${id}/posts?${new URLSearchParams(params)}`),
  deleteResearch: (id: number) =>
    fetchJSON<{ status: string }>(`/research/${id}`, { method: "DELETE" }),
};
