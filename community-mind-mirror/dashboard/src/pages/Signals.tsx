import { useState } from "react";
import {
  FlaskConical, Target, Orbit, AlertTriangle, Swords,
  Split, DollarSign, Users, MessageSquare, BarChart3,
  ChevronDown, ChevronUp, ArrowRight,
} from "lucide-react";
import {
  useResearchPipeline, useTractionScores, useTechnologyLifecycle,
  useMarketGaps, useCompetitiveThreats, usePlatformDivergence,
  useSmartMoney, useTalentFlow, useNarrativeShifts, useInsights,
  useAgentOutput, useSignalSummary,
} from "../api/hooks";
import { formatNumber, formatDate, timeAgo, cn } from "../lib/utils";
import {
  PipelineSteps, VelocityBadge, TractionScoreRing, LifecycleBar,
  DivergenceBars, GapSignalBadge, ThreatScoreBar, OpportunityScore,
  ClassificationBadge, SalaryPressureBadge, ShiftTypeBadge,
  TrendArrow, DemandSupplyBar, VCSignalDots,
} from "../components/signals";
import { CardSkeleton } from "../components/common/Skeleton";
import Pagination from "../components/common/Pagination";

const tabs = [
  { key: "overview", label: "Overview", icon: BarChart3 },
  { key: "pipeline", label: "Pipeline", icon: FlaskConical },
  { key: "traction", label: "Traction", icon: Target },
  { key: "lifecycle", label: "Lifecycle", icon: Orbit },
  { key: "gaps", label: "Gaps", icon: AlertTriangle },
  { key: "threats", label: "Threats", icon: Swords },
  { key: "divergence", label: "Divergence", icon: Split },
  { key: "money", label: "Smart Money", icon: DollarSign },
  { key: "talent", label: "Talent", icon: Users },
  { key: "narratives", label: "Narratives", icon: MessageSquare },
] as const;

type TabKey = typeof tabs[number]["key"];

export default function Signals() {
  const [tab, setTab] = useState<TabKey>("overview");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-medium text-text-primary">Cross-source signals</h1>
        <InsightsBadge />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-primary border border-border-primary rounded-xl p-1 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-[12px] transition-colors whitespace-nowrap",
              tab === t.key
                ? "bg-bg-info text-txt-info"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
            )}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span className="hidden lg:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab />}
      {tab === "pipeline" && <PipelineTab />}
      {tab === "traction" && <TractionTab />}
      {tab === "lifecycle" && <LifecycleTab />}
      {tab === "gaps" && <GapsTab />}
      {tab === "threats" && <ThreatsTab />}
      {tab === "divergence" && <DivergenceTab />}
      {tab === "money" && <SmartMoneyTab />}
      {tab === "talent" && <TalentTab />}
      {tab === "narratives" && <NarrativesTab />}
    </div>
  );
}

// ── Insights count badge ──────────────────────────────────────

function InsightsBadge() {
  const { data } = useInsights();
  if (!data || data.length === 0) return null;
  return (
    <span className="px-2 py-1 rounded-lg text-[11px] font-medium bg-bg-purple text-txt-purple">
      {data.length} insight{data.length !== 1 ? "s" : ""}
    </span>
  );
}

// ── Overview Tab ──────────────────────────────────────────────

function OverviewTab() {
  const { data, isLoading } = useSignalSummary();
  const { data: insights } = useInsights();

  if (isLoading) return <Skeletons />;
  if (!data) return <Empty msg="No signal data available yet. Run the agents to generate signals." />;

  const totalCount = Object.values(data.total_signals).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-4">
      {/* Metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card">
          <p className="text-[11px] text-text-secondary">Total Signals</p>
          <p className="text-xl font-semibold text-text-primary">{totalCount}</p>
        </div>
        <div className="card">
          <p className="text-[11px] text-text-secondary">Signal Types</p>
          <p className="text-xl font-semibold text-text-primary">{Object.keys(data.total_signals).length}</p>
        </div>
        <div className="card">
          <p className="text-[11px] text-text-secondary">Smart Money Early</p>
          <p className="text-xl font-semibold text-success">{data.smart_money_early.length}</p>
          <p className="text-[10px] text-text-tertiary">sectors</p>
        </div>
        <div className="card">
          <p className="text-[11px] text-text-secondary">Insights</p>
          <p className="text-xl font-semibold text-info">{insights?.length ?? 0}</p>
        </div>
      </div>

      {/* Signal counts by type */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-3">Signals by type</h2>
        <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
          {Object.entries(data.total_signals).map(([key, count]) => (
            <div key={key} className="flex items-center justify-between text-[11px] bg-bg-secondary rounded-md px-2 py-1.5">
              <span className="text-text-secondary">{key.replace(/_/g, " ")}</span>
              <span className="font-medium text-text-primary">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2-column grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top Opportunities */}
        {data.top_opportunities.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Biggest opportunities</h2>
            <div className="space-y-2">
              {data.top_opportunities.map((g, i) => (
                <div key={i} className="flex items-center justify-between text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="min-w-0">
                    <p className="font-medium text-text-primary truncate">{g.problem_title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      {g.gap_signal && <GapSignalBadge signal={g.gap_signal} />}
                      <span className="text-[10px] text-text-secondary">{g.complaint_count} complaints</span>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-success ml-2">{g.opportunity_score?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Threats */}
        {data.top_threats.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Top threats</h2>
            <div className="space-y-2">
              {data.top_threats.map((t, i) => (
                <div key={i} className="text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="flex items-center gap-1">
                    <span className="font-medium text-text-primary">{t.target_product}</span>
                    <span className="text-text-tertiary">←</span>
                    <span className="font-medium text-danger">{t.competitor}</span>
                    <span className="ml-auto font-semibold text-danger">{t.threat_score?.toFixed(1)}</span>
                  </div>
                  <span className="text-[10px] text-text-secondary">{t.migrations_away} migrations away</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Talent Gaps */}
        {data.top_skill_gaps.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Talent gaps widening</h2>
            <div className="space-y-2">
              {data.top_skill_gaps.map((s, i) => (
                <div key={i} className="text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-text-primary">{s.skill}</span>
                    <SalaryPressureBadge value={s.salary_pressure} />
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-text-secondary">
                    <span>Gap: <span className="font-medium text-danger">{s.gap}</span></span>
                    <span>Demand: {s.demand_score}</span>
                    <span>Supply: {s.supply_score}</span>
                    <TrendArrow trend={s.trend} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Smart Money Early */}
        {data.smart_money_early.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Smart money moving</h2>
            <div className="space-y-2">
              {data.smart_money_early.map((s, i) => (
                <div key={i} className="text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-text-primary">{s.sector}</span>
                    <ClassificationBadge value="smart_money_early" />
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-[10px] text-text-secondary">
                    <span>YC: {s.yc_companies_last_batch} companies</span>
                    <TrendArrow trend={s.yc_trend} />
                    <span>VC: {s.vc_signal}</span>
                    {(s.builder_repos ?? 0) > 0 && <span>{s.builder_repos} repos</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Narrative Shifts */}
        {data.narrative_shifts.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Narrative shifts (high confidence)</h2>
            <div className="space-y-2">
              {data.narrative_shifts.map((n, i) => (
                <div key={i} className="text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text-primary">{n.topic_name}</span>
                    {n.shift_velocity && <VelocityBadge velocity={n.shift_velocity} />}
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-[10px]">
                    <span className="text-text-tertiary line-through">{n.older_frame?.slice(0, 60)}</span>
                    <ArrowRight className="w-3 h-3 text-info shrink-0" />
                    <span className="text-text-primary">{n.recent_frame?.slice(0, 60)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Insights */}
        {insights && insights.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Cross-signal insights</h2>
            <div className="space-y-2">
              {insights.slice(0, 5).map((ins, i) => (
                <div key={i} className="text-[12px] pb-2 border-b border-border-secondary last:border-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-medium",
                      ins.category === "opportunity" ? "bg-bg-success text-txt-success" :
                      ins.category === "threat" ? "bg-bg-danger text-txt-danger" :
                      ins.category === "trend" ? "bg-bg-info text-txt-info" :
                      "bg-bg-tertiary text-text-secondary"
                    )}>{ins.category}</span>
                    {ins.confidence && (
                      <span className={cn(
                        "text-[10px]",
                        ins.confidence === "high" ? "text-success" : ins.confidence === "medium" ? "text-warning" : "text-text-tertiary"
                      )}>{ins.confidence}</span>
                    )}
                  </div>
                  <p className="text-text-primary line-clamp-2">{ins.insight}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Pipeline Tab ──────────────────────────────────────────────

function PipelineTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useResearchPipeline({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("research_pipeline");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Research → Product pipeline</h2>
          <p className="text-[12px] text-text-secondary mb-3">Tracking papers from ArXiv through code, models, community adoption, and product launches</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Research → Product pipeline</h2>
        <p className="text-[12px] text-text-secondary mb-3">Tracking papers from ArXiv through code, models, community adoption, and product launches</p>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="flex gap-4 items-start py-2 border-b border-border-secondary last:border-0">
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-text-primary truncate">{item.paper_title}</p>
                <div className="flex items-center gap-3 mt-1 text-[11px] text-text-secondary">
                  {item.arxiv_id && <span className="font-mono">{item.arxiv_id}</span>}
                  {item.published_at && <span>{formatDate(item.published_at)}</span>}
                  {item.github_repos != null && item.github_repos > 0 && <span>{item.github_repos} repos</span>}
                  {item.hf_total_downloads != null && item.hf_total_downloads > 0 && <span>{formatNumber(item.hf_total_downloads)} HF downloads</span>}
                  {item.community_mention_count != null && item.community_mention_count > 0 && <span>{item.community_mention_count} mentions</span>}
                </div>
                <div className="flex items-center gap-3 mt-0.5 text-[10px] text-text-tertiary">
                  {item.days_paper_to_code != null && <span>Paper→Code: {item.days_paper_to_code}d</span>}
                  {item.days_code_to_adoption != null && <span>Code→Adoption: {item.days_code_to_adoption}d</span>}
                  {item.days_total_pipeline != null && <span className="font-medium text-text-secondary">Total: {item.days_total_pipeline}d</span>}
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <VelocityBadge velocity={item.pipeline_velocity} />
                <PipelineSteps currentStage={item.current_stage} />
              </div>
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Traction Tab ──────────────────────────────────────────────

function TractionTab() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);
  const { data, isLoading } = useTractionScores({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("traction_scorer");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Anti-hype traction scores</h2>
          <p className="text-[12px] text-text-secondary mb-3">Real traction based on unfakeable signals: stars, downloads, organic mentions, job listings</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Anti-hype traction scores</h2>
        <p className="text-[12px] text-text-secondary mb-3">Real traction based on unfakeable signals: stars, downloads, organic mentions, job listings</p>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="py-2 border-b border-border-secondary last:border-0">
              <div className="flex gap-4 items-center">
                <TractionScoreRing score={item.traction_score} label={item.traction_label} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-[12px] font-medium text-text-primary">{item.entity_name}</p>
                    <span className="text-[11px] text-text-secondary">{item.entity_type?.replace(/_/g, " ")}</span>
                    {item.recommendation_rate != null && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-success text-txt-success">
                        {item.recommendation_rate.toFixed(0)}% recommended
                      </span>
                    )}
                  </div>
                  <div className="flex gap-3 mt-1 flex-wrap">
                    {item.gh_stars != null && <Stat label="Stars" value={formatNumber(item.gh_stars)} />}
                    {item.gh_star_velocity != null && item.gh_star_velocity > 0 && <Stat label="Star vel" value={formatNumber(item.gh_star_velocity)} />}
                    {item.pypi_monthly_downloads != null && <Stat label="PyPI/mo" value={formatNumber(item.pypi_monthly_downloads)} />}
                    {item.npm_monthly_downloads != null && <Stat label="npm/mo" value={formatNumber(item.npm_monthly_downloads)} />}
                    {item.organic_mentions != null && <Stat label="Organic" value={String(item.organic_mentions)} />}
                    {item.job_listings != null && <Stat label="Jobs" value={String(item.job_listings)} />}
                  </div>
                  {item.red_flags && item.red_flags.length > 0 && (
                    <div className="flex gap-1 mt-1">
                      {item.red_flags.map((f) => (
                        <span key={f} className="px-1.5 py-0.5 text-[10px] rounded bg-bg-danger text-txt-danger">{f}</span>
                      ))}
                    </div>
                  )}
                </div>
                <button onClick={() => setExpanded(expanded === item.id ? null : item.id)} className="text-text-tertiary hover:text-text-primary p-1">
                  {expanded === item.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
              {expanded === item.id && (
                <div className="mt-2 ml-16 space-y-2">
                  {item.score_breakdown && Object.keys(item.score_breakdown).length > 0 && (
                    <div>
                      <p className="text-[10px] font-medium text-text-secondary mb-1">Score breakdown</p>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-1">
                        {Object.entries(item.score_breakdown).map(([k, v]) => (
                          <div key={k} className="flex justify-between text-[10px] bg-bg-secondary rounded px-2 py-1">
                            <span className="text-text-secondary">{k.replace(/_/g, " ")}</span>
                            <span className="text-text-primary font-medium">{typeof v === "number" ? v.toFixed(1) : String(v)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {item.reasoning && (
                    <div>
                      <p className="text-[10px] font-medium text-text-secondary mb-1">Reasoning</p>
                      <p className="text-[11px] text-text-primary">{item.reasoning}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Lifecycle Tab ─────────────────────────────────────────────

function LifecycleTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useTechnologyLifecycle({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("lifecycle_mapper");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Technology lifecycle mapping</h2>
          <p className="text-[12px] text-text-secondary mb-3">Where each technology sits: research → experimentation → growth → mature → declining</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Technology lifecycle mapping</h2>
        <p className="text-[12px] text-text-secondary mb-3">Where each technology sits: research → experimentation → growth → mature → declining</p>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="py-2 border-b border-border-secondary last:border-0 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-text-primary">{item.technology_name}</span>
                <span className="text-[11px] text-text-secondary capitalize">{item.current_stage?.replace(/_/g, " ")}</span>
              </div>
              <LifecycleBar stage={item.current_stage} />
              <div className="flex gap-3 flex-wrap">
                {item.arxiv_paper_count != null && <Stat label="Papers" value={String(item.arxiv_paper_count)} />}
                {item.github_repo_count != null && <Stat label="Repos" value={String(item.github_repo_count)} />}
                {item.hf_model_count != null && <Stat label="Models" value={String(item.hf_model_count)} />}
                {item.so_question_count != null && <Stat label="SO Q's" value={String(item.so_question_count)} />}
                {item.job_listing_count != null && <Stat label="Jobs" value={String(item.job_listing_count)} />}
                {item.community_mention_count != null && <Stat label="Mentions" value={String(item.community_mention_count)} />}
              </div>
              {item.pypi_download_trend && typeof item.pypi_download_trend === "object" && (
                <div className="flex items-center gap-2 text-[10px] text-text-tertiary">
                  <span>PyPI trend:</span>
                  {Object.entries(item.pypi_download_trend).slice(0, 4).map(([k, v]) => (
                    <span key={k} className="bg-bg-secondary px-1.5 py-0.5 rounded">{k}: {typeof v === "number" ? formatNumber(v) : String(v)}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Gaps Tab ──────────────────────────────────────────────────

function GapsTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useMarketGaps({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("market_gap_detector");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Market gaps & startup opportunities</h2>
          <p className="text-[12px] text-text-secondary mb-3">Where demand outstrips supply — cross-referenced from complaints, funding, jobs, and YC batches</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Market gaps & startup opportunities</h2>
        <p className="text-[12px] text-text-secondary mb-3">Where demand outstrips supply — cross-referenced from complaints, funding, jobs, and YC batches</p>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-text-primary">{item.problem_title}</span>
                <GapSignalBadge signal={item.gap_signal} />
              </div>
              <OpportunityScore score={item.opportunity_score} />
              <div className="flex gap-3 flex-wrap text-[11px]">
                {item.complaint_count != null && <Stat label="Complaints" value={String(item.complaint_count)} />}
                {item.existing_products != null && <Stat label="Existing" value={String(item.existing_products)} />}
                {item.funded_startups != null && <Stat label="Funded" value={String(item.funded_startups)} />}
                {item.job_postings_related != null && <Stat label="Jobs" value={String(item.job_postings_related)} />}
                {item.yc_batch_presence != null && <Stat label="YC batches" value={String(item.yc_batch_presence)} />}
              </div>
              {item.reasoning && <p className="text-[11px] text-text-secondary">{item.reasoning}</p>}
              {item.existing_product_names && item.existing_product_names.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {item.existing_product_names.map((n) => <span key={n} className="tag">{n}</span>)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Threats Tab ───────────────────────────────────────────────

function ThreatsTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useCompetitiveThreats({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("competitive_threat");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Competitive threats</h2>
          <p className="text-[12px] text-text-secondary mb-3">Products at risk based on migrations, competitor velocity, hiring, and leader opinion shifts</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Competitive threats</h2>
        <p className="text-[12px] text-text-secondary mb-3">Products at risk based on migrations, competitor velocity, hiring, and leader opinion shifts</p>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[12px] font-medium text-text-primary">{item.target_product}</span>
                  <span className="text-[11px] text-text-tertiary mx-2">threatened by</span>
                  <span className="text-[12px] font-medium text-danger">{item.competitor}</span>
                </div>
              </div>
              <ThreatScoreBar score={item.threat_score} />
              <div className="flex gap-3 flex-wrap">
                {item.migrations_away != null && <Stat label="Migrations" value={String(item.migrations_away)} />}
                {item.competitor_gh_velocity != null && <Stat label="GH velocity" value={formatNumber(item.competitor_gh_velocity)} />}
                {item.competitor_hiring != null && <Stat label="Hiring" value={String(item.competitor_hiring)} />}
                {item.competitor_sentiment != null && (
                  <span className="text-[11px]">
                    <span className="text-text-secondary">Sentiment: </span>
                    <span className={cn("font-medium", item.competitor_sentiment > 0 ? "text-success" : item.competitor_sentiment < 0 ? "text-danger" : "text-text-tertiary")}>
                      {item.competitor_sentiment > 0 ? "+" : ""}{item.competitor_sentiment.toFixed(2)}
                    </span>
                    {item.competitor_sentiment_trend != null && (
                      <span className={cn("ml-1", Number(item.competitor_sentiment_trend) > 0 ? "text-success" : "text-danger")}>
                        {Number(item.competitor_sentiment_trend) > 0 ? "↑" : "↓"}
                      </span>
                    )}
                  </span>
                )}
                {item.opinion_leaders_flipped != null && <Stat label="Leaders flipped" value={String(item.opinion_leaders_flipped)} />}
              </div>
              {item.threat_summary && <p className="text-[11px] text-text-secondary italic">{item.threat_summary}</p>}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Divergence Tab ────────────────────────────────────────────

function DivergenceTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = usePlatformDivergence({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("divergence_detector");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Platform sentiment divergence</h2>
          <p className="text-[12px] text-text-secondary mb-3">When Reddit, HN, YouTube, and Product Hunt disagree — early signal for sentiment shifts</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Platform sentiment divergence</h2>
        <p className="text-[12px] text-text-secondary mb-3">When Reddit, HN, YouTube, and Product Hunt disagree — early signal for sentiment shifts</p>

        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-text-primary">{item.topic_name}</span>
                <div className="flex items-center gap-2">
                  {item.status && (
                    <span className={cn(
                      "px-2 py-0.5 rounded-md text-[10px] font-medium",
                      item.status === "confirmed" ? "bg-bg-success text-txt-success" :
                      item.status === "pending" ? "bg-bg-warning text-txt-warning" :
                      "bg-bg-tertiary text-text-secondary"
                    )}>
                      {item.status}
                    </span>
                  )}
                  <span className="text-[11px] font-mono text-text-secondary">
                    Δ {item.max_divergence?.toFixed(2) ?? "—"}
                  </span>
                </div>
              </div>
              <DivergenceBars
                reddit={item.reddit_sentiment}
                hn={item.hn_sentiment}
                youtube={item.youtube_sentiment}
                ph={item.ph_sentiment}
              />
              {item.divergence_direction && (
                <p className="text-[11px] text-text-secondary">{item.divergence_direction}</p>
              )}
              {item.prediction && (
                <p className="text-[11px] text-info">{item.prediction}</p>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Smart Money Tab ───────────────────────────────────────────

function SmartMoneyTab() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);
  const { data, isLoading } = useSmartMoney({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("smart_money_tracker");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Smart money tracker</h2>
          <p className="text-[12px] text-text-secondary mb-3">YC vs VC capital flow analysis — where is money actually going vs. what's hyped?</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  // Summary counts
  const classCount = items.reduce((acc, it) => {
    const c = it.classification || "unknown";
    acc[c] = (acc[c] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Smart money tracker</h2>
        <p className="text-[12px] text-text-secondary mb-3">YC vs VC capital flow analysis — where is money actually going vs. what's hyped?</p>

        {/* Summary badges */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <span className="text-[11px] bg-bg-secondary px-2 py-1 rounded-lg">{items.length} sectors</span>
          {Object.entries(classCount).map(([k, v]) => (
            <span key={k} className="text-[11px]"><ClassificationBadge value={k} /> ×{v}</span>
          ))}
        </div>

        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[12px] font-medium text-text-primary">{item.sector}</span>
                  <ClassificationBadge value={item.classification} />
                </div>
                <button onClick={() => setExpanded(expanded === item.id ? null : item.id)} className="text-text-tertiary hover:text-text-primary p-1">
                  {expanded === item.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>
              <div className="flex gap-4 mt-2 flex-wrap">
                {/* YC */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-text-secondary font-medium">YC</span>
                  <span className="text-[12px] font-semibold text-text-primary">{item.yc_companies_last_batch ?? 0}</span>
                  <span className="text-[10px] text-text-tertiary">companies</span>
                  <TrendArrow trend={item.yc_trend} />
                  {item.yc_percentage_of_batch != null && (
                    <span className="text-[10px] text-text-tertiary">({item.yc_percentage_of_batch.toFixed(1)}% of batch)</span>
                  )}
                </div>
                {/* VC */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-text-secondary font-medium">VC</span>
                  <VCSignalDots signal={item.vc_signal} />
                  {item.vc_funding_articles != null && item.vc_funding_articles > 0 && (
                    <span className="text-[10px] text-text-tertiary">{item.vc_funding_articles} articles</span>
                  )}
                </div>
                {/* Builder */}
                {((item.builder_repos ?? 0) > 0 || (item.builder_stars ?? 0) > 0) && (
                  <div className="flex items-center gap-1 text-[10px] text-text-secondary">
                    <span className="font-medium">Builders:</span>
                    {item.builder_repos != null && <span>{item.builder_repos} repos</span>}
                    {item.builder_stars != null && <span>/ {formatNumber(item.builder_stars)} ★</span>}
                  </div>
                )}
                {/* Community */}
                {(item.community_posts_30d ?? 0) > 0 && (
                  <span className="text-[10px] text-text-secondary">{formatNumber(item.community_posts_30d ?? 0)} posts (30d)</span>
                )}
              </div>
              {expanded === item.id && item.reasoning && (
                <div className="mt-2 bg-bg-secondary rounded-lg p-2">
                  <p className="text-[10px] font-medium text-text-secondary mb-1">Reasoning</p>
                  <p className="text-[11px] text-text-primary">{item.reasoning}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Talent Tab ────────────────────────────────────────────────

function TalentTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useTalentFlow({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("talent_flow");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Talent flow analysis</h2>
          <p className="text-[12px] text-text-secondary mb-3">Supply vs demand skill gap predictions — where hiring outpaces talent</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  // Summary counts
  const catCount = items.reduce((acc, it) => {
    const c = it.category || "unknown";
    acc[c] = (acc[c] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const catStyles: Record<string, string> = {
    skill_gap: "bg-bg-danger text-txt-danger",
    emerging: "bg-bg-info text-txt-info",
    oversupply: "bg-bg-warning text-txt-warning",
  };

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Talent flow analysis</h2>
        <p className="text-[12px] text-text-secondary mb-3">Supply vs demand skill gap predictions — where hiring outpaces talent</p>

        {/* Summary badges */}
        <div className="flex gap-2 mb-4 flex-wrap">
          <span className="text-[11px] bg-bg-secondary px-2 py-1 rounded-lg">{items.length} skills tracked</span>
          {Object.entries(catCount).map(([k, v]) => (
            <span key={k} className={cn("text-[11px] px-2 py-1 rounded-lg", catStyles[k] || "bg-bg-tertiary text-text-secondary")}>
              {k.replace(/_/g, " ")}: {v}
            </span>
          ))}
        </div>

        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[12px] font-medium text-text-primary">{item.skill}</span>
                  <span className={cn("px-2 py-0.5 rounded-md text-[10px] font-medium", catStyles[item.category || ""] || "bg-bg-tertiary text-text-secondary")}>
                    {item.category?.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <SalaryPressureBadge value={item.salary_pressure} />
                  <TrendArrow trend={item.trend} />
                </div>
              </div>
              <DemandSupplyBar demand={item.demand_score} supply={item.supply_score} />
              <div className="flex gap-3 flex-wrap text-[11px]">
                <Stat label="Gap" value={String(item.gap ?? 0)} />
                {item.job_listings_30d != null && <Stat label="Jobs (30d)" value={String(item.job_listings_30d)} />}
                {item.so_questions_30d != null && <Stat label="SO Q's (30d)" value={String(item.so_questions_30d)} />}
              </div>
              {item.prediction && <p className="text-[11px] text-info">{item.prediction}</p>}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Narratives Tab ────────────────────────────────────────────

function NarrativesTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useNarrativeShifts({ page: String(page), per_page: "20" });
  const fallback = useAgentOutput("narrative_shift");

  if (isLoading) return <Skeletons />;

  const items = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (items.length === 0) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Narrative shift detector</h2>
          <p className="text-[12px] text-text-secondary mb-3">How community framing of technologies evolves over time</p>
          {fallback.data?.last_run && <span className="text-[10px] text-text-tertiary">Last run: {timeAgo(fallback.data.last_run)}</span>}
        </div>
        <AgentOutputDisplay data={fallback.data?.data} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Narrative shift detector</h2>
        <p className="text-[12px] text-text-secondary mb-3">How community framing of technologies evolves over time</p>

        <div className="space-y-4">
          {items.map((item) => (
            <div key={item.id} className="py-3 border-b border-border-secondary last:border-0 space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[12px] font-medium text-text-primary">{item.topic_name}</span>
                <ShiftTypeBadge value={item.shift_type} />
                {item.shift_velocity && <VelocityBadge velocity={item.shift_velocity} />}
                {item.confidence && (
                  <span className={cn(
                    "px-2 py-0.5 rounded-md text-[10px] font-medium",
                    item.confidence === "high" ? "bg-bg-success text-txt-success" :
                    item.confidence === "medium" ? "bg-bg-warning text-txt-warning" :
                    "bg-bg-tertiary text-text-secondary"
                  )}>
                    {item.confidence}
                  </span>
                )}
              </div>

              {/* Frame comparison */}
              <div className="flex items-stretch gap-2">
                <div className="flex-1 bg-bg-secondary rounded-lg p-2.5">
                  <p className="text-[10px] text-text-tertiary mb-1">Older frame</p>
                  <p className="text-[11px] text-text-secondary">{item.older_frame}</p>
                </div>
                <div className="flex items-center">
                  <ArrowRight className="w-4 h-4 text-info" />
                </div>
                <div className="flex-1 bg-bg-info/10 border border-info/20 rounded-lg p-2.5">
                  <p className="text-[10px] text-info mb-1">Recent frame</p>
                  <p className="text-[11px] text-text-primary">{item.recent_frame}</p>
                </div>
              </div>

              {item.media_alignment && (
                <p className="text-[10px] text-text-secondary">
                  <span className="font-medium">Media alignment:</span> {item.media_alignment}
                </p>
              )}
              {item.prediction && (
                <p className="text-[11px] text-info">{item.prediction}</p>
              )}
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}

// ── Shared helpers ────────────────────────────────────────────

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-[11px]">
      <span className="text-text-secondary">{label}: </span>
      <span className="text-text-primary font-medium">{value}</span>
    </span>
  );
}

function Skeletons() {
  return (
    <div className="grid grid-cols-1 gap-3">
      {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
    </div>
  );
}

function Empty({ msg }: { msg: string }) {
  return <p className="text-sm text-text-tertiary text-center py-8">{msg}</p>;
}

function renderValue(v: unknown): string {
  if (v == null) return "—";
  if (typeof v === "number") return formatNumber(v);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) {
    if (v.length === 0) return "—";
    if (typeof v[0] !== "object") return v.join(", ");
    return `${v.length} items`;
  }
  if (typeof v === "object") return JSON.stringify(v).slice(0, 120);
  return String(v);
}

function AgentOutputDisplay({ data }: { data: unknown }) {
  if (!data) return <Empty msg="No data yet. Run the agent to generate results." />;

  if (Array.isArray(data)) {
    const items = data.length === 1 && typeof data[0] === "object" && data[0] !== null
      ? (() => {
          const inner = data[0] as Record<string, unknown>;
          const arrayKeys = Object.entries(inner).filter(([, v]) => Array.isArray(v));
          if (arrayKeys.length > 0) {
            const cards: Record<string, unknown>[] = [];
            for (const [section, arr] of arrayKeys) {
              for (const item of arr as unknown[]) {
                if (typeof item === "object" && item !== null) {
                  cards.push({ _section: section.replace(/_/g, " "), ...item as Record<string, unknown> });
                }
              }
            }
            return cards.length > 0 ? cards : data;
          }
          return data;
        })()
      : data;

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((item, i) => (
          <div key={i} className="card space-y-1">
            {typeof item === "object" && item !== null ? (
              <>
                {(item as Record<string, unknown>)._section && (
                  <div className="text-[10px] font-medium text-txt-info uppercase tracking-wider mb-1">
                    {String((item as Record<string, unknown>)._section)}
                  </div>
                )}
                {Object.entries(item as Record<string, unknown>)
                  .filter(([k]) => k !== "_section")
                  .slice(0, 10)
                  .map(([k, v]) => {
                    const isLongText = typeof v === "string" && v.length > 80;
                    return isLongText ? (
                      <div key={k} className="text-[11px]">
                        <span className="text-text-secondary">{k.replace(/_/g, " ")}</span>
                        <p className="text-text-primary mt-0.5 line-clamp-3">{String(v)}</p>
                      </div>
                    ) : (
                      <div key={k} className="flex justify-between text-[11px]">
                        <span className="text-text-secondary">{k.replace(/_/g, " ")}</span>
                        <span className="text-text-primary font-medium truncate ml-2 max-w-[60%] text-right">
                          {renderValue(v)}
                        </span>
                      </div>
                    );
                  })}
              </>
            ) : (
              <span className="text-[12px] text-text-primary">{String(item)}</span>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (typeof data === "object" && data !== null) {
    return (
      <div className="card space-y-1">
        {Object.entries(data as Record<string, unknown>).slice(0, 20).map(([k, v]) => {
          const isLongText = typeof v === "string" && v.length > 80;
          return isLongText ? (
            <div key={k} className="text-[11px]">
              <span className="text-text-secondary">{k.replace(/_/g, " ")}</span>
              <p className="text-text-primary mt-0.5 line-clamp-3">{String(v)}</p>
            </div>
          ) : (
            <div key={k} className="flex justify-between text-[11px]">
              <span className="text-text-secondary">{k.replace(/_/g, " ")}</span>
              <span className="text-text-primary font-medium truncate ml-2 max-w-[70%] text-right">
                {renderValue(v)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  return <div className="card"><p className="text-[12px] text-text-primary whitespace-pre-wrap">{String(data)}</p></div>;
}
