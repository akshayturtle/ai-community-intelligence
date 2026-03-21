import { useState } from "react";
import {
  DollarSign, MapPin, Clock, Code,
  TrendingUp, ExternalLink,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { useGigBoard, useGigSummary, useGigTrends } from "../api/hooks";
import { formatNumber, cn } from "../lib/utils";
import { CardSkeleton } from "../components/common/Skeleton";
import Pagination from "../components/common/Pagination";

const TYPE_COLORS: Record<string, string> = {
  freelance: "bg-bg-info text-txt-info",
  contract: "bg-bg-purple text-txt-purple",
  full_time: "bg-bg-success text-txt-success",
  co_founder: "bg-bg-warning text-txt-warning",
  consulting: "bg-bg-danger text-txt-danger",
};

const CATEGORY_LABELS: Record<string, string> = {
  chatbot: "Chatbot",
  rag: "RAG",
  fine_tuning: "Fine-tuning",
  agent: "AI Agent",
  automation: "Automation",
  data_pipeline: "Data Pipeline",
  web_app: "Web App",
  mobile_app: "Mobile App",
  ml_model: "ML Model",
  saas: "SaaS",
  design: "Design",
  devops: "DevOps",
  other: "Other",
};

export default function GigBoard() {
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  const params: Record<string, string> = { page: String(page), per_page: "20" };
  if (typeFilter) params.project_type = typeFilter;
  if (categoryFilter) params.need_category = categoryFilter;

  const { data: summary, isLoading: loadingSummary } = useGigSummary();
  const { data, isLoading } = useGigBoard(params);
  const { data: trends } = useGigTrends();

  if (loadingSummary && isLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-medium text-text-primary">AI Gig Board</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      </div>
    );
  }

  const gigs = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  const trendChart = (trends?.weekly_trend || []).map(w => ({
    week: w.week.slice(5), // MM-DD
    count: w.count,
  }));

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-medium text-text-primary">AI Gig Board</h1>
      <p className="text-[12px] text-text-secondary -mt-3">Freelance, contract, and hiring posts extracted from Reddit communities</p>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Total Gigs</div>
          <div className="text-[22px] font-medium text-text-primary">{formatNumber(summary?.total_gigs || 0)}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Avg Budget</div>
          <div className="text-[18px] font-medium text-success">
            {summary?.budget?.avg_min && summary?.budget?.avg_max
              ? `$${formatNumber(summary.budget.avg_min)} - $${formatNumber(summary.budget.avg_max)}`
              : "—"}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Top Type</div>
          <div className="text-[16px] font-medium text-text-primary">
            {summary?.by_project_type
              ? Object.entries(summary.by_project_type).sort((a, b) => b[1] - a[1])[0]?.[0]?.replace(/_/g, " ") || "—"
              : "—"}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Top Category</div>
          <div className="text-[16px] font-medium text-text-primary">
            {summary?.by_need_category
              ? CATEGORY_LABELS[Object.entries(summary.by_need_category).sort((a: [string, unknown], b: [string, unknown]) => (b[1] as number) - (a[1] as number))[0]?.[0] || ""] || Object.entries(summary.by_need_category).sort((a: [string, unknown], b: [string, unknown]) => (b[1] as number) - (a[1] as number))[0]?.[0]?.replace(/_/g, " ") || "—"
              : "—"}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Remote</div>
          <div className="text-[16px] font-medium text-info">
            {summary?.by_remote_policy?.remote || summary?.by_remote_policy?.fully_remote || 0}
          </div>
          <div className="text-[11px] text-text-tertiary">remote gigs</div>
        </div>
      </div>

      {/* Row: Trend + Tech Stacks + Type Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-3">
        {/* Weekly trend */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-info" />
            <h2 className="text-sm font-medium text-text-primary">Weekly gig volume</h2>
          </div>
          {trendChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={trendChart}>
                <XAxis dataKey="week" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} />
                <YAxis tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: "var(--mm-bg-primary)", border: "0.5px solid var(--mm-border-primary)", borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="count" fill="#378ADD" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-text-tertiary py-4">No trend data yet</p>}
        </div>

        {/* Top Tech Stacks */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Code className="w-4 h-4 text-purple" />
            <h2 className="text-sm font-medium text-text-primary">Top tech stacks</h2>
          </div>
          <div className="space-y-1">
            {(summary?.top_tech_stacks || []).slice(0, 12).map((t: any, i: number) => {
              const maxCount = summary?.top_tech_stacks[0]?.count || 1;
              return (
                <div key={t.tech} className="flex items-center gap-2 text-[12px]">
                  <span className="w-4 text-text-tertiary text-right">{i + 1}</span>
                  <span className="text-text-primary w-24 truncate">{t.tech}</span>
                  <div className="flex-1 h-2.5 bg-bg-secondary rounded-sm overflow-hidden">
                    <div className="h-full bg-purple rounded-sm" style={{ width: `${(t.count / maxCount) * 100}%` }} />
                  </div>
                  <span className="text-text-secondary font-mono w-8 text-right">{t.count}</span>
                </div>
              );
            })}
            {(!summary?.top_tech_stacks || summary.top_tech_stacks.length === 0) && <p className="text-sm text-text-tertiary py-4">No data yet</p>}
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 items-center">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="text-[12px] bg-bg-secondary border border-border-primary rounded-md px-2 py-1.5 text-text-primary"
        >
          <option value="">All types</option>
          <option value="freelance">Freelance</option>
          <option value="contract">Contract</option>
          <option value="full_time">Full Time</option>
          <option value="part_time">Part Time</option>
          <option value="co_founder">Co-Founder</option>
          <option value="consulting">Consulting</option>
          <option value="internship">Internship</option>
          <option value="research_study">Research Study</option>
        </select>
        <select
          value={categoryFilter}
          onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
          className="text-[12px] bg-bg-secondary border border-border-primary rounded-md px-2 py-1.5 text-text-primary"
        >
          <option value="">All categories</option>
          {Object.entries(CATEGORY_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <span className="text-[11px] text-text-tertiary ml-auto">{data?.total || 0} gigs</span>
      </div>

      {/* Gig Listing */}
      <div className="space-y-2">
        {gigs.map((g: any) => (
          <div key={g.id} className="card">
            <div className="flex items-start justify-between mb-1.5">
              <div className="flex items-center gap-2">
                {g.project_type && (
                  <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium", TYPE_COLORS[g.project_type] || "bg-bg-secondary text-text-secondary")}>
                    {g.project_type.replace(/_/g, " ")}
                  </span>
                )}
                {g.need_category && (
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-secondary text-text-secondary">
                    {CATEGORY_LABELS[g.need_category] || g.need_category}
                  </span>
                )}
                {g.experience_level && g.experience_level !== "any" && (
                  <span className="text-[10px] text-text-tertiary">{g.experience_level}</span>
                )}
              </div>
              <div className="flex items-center gap-3 text-[11px] text-text-tertiary shrink-0">
                {g.remote_policy && (
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3 h-3" />
                    {g.remote_policy.replace(/_/g, " ")}
                  </span>
                )}
                {g.project_duration && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {g.project_duration}
                  </span>
                )}
                {g.posted_at && (
                  <span>{new Date(g.posted_at).toLocaleDateString()}</span>
                )}
              </div>
            </div>

            {g.need_description && (
              <p className="text-[12px] text-text-primary mb-2">{g.need_description}</p>
            )}

            <div className="flex items-center flex-wrap gap-2">
              {/* Budget */}
              {(g.budget_min_usd || g.budget_max_usd || g.budget_text) && (
                <span className="flex items-center gap-1 text-[12px] text-success font-medium">
                  <DollarSign className="w-3 h-3" />
                  {g.budget_min_usd || g.budget_max_usd
                    ? `$${formatNumber(g.budget_min_usd || 0)} - $${formatNumber(g.budget_max_usd || 0)}`
                    : g.budget_text}
                </span>
              )}

              {/* Tech Stack Tags */}
              {g.tech_stack && g.tech_stack.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {g.tech_stack.slice(0, 6).map((t: string, i: number) => (
                    <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-purple text-txt-purple">{t}</span>
                  ))}
                  {g.tech_stack.length > 6 && (
                    <span className="text-[10px] text-text-tertiary">+{g.tech_stack.length - 6}</span>
                  )}
                </div>
              )}

              {/* Source + View Post */}
              <div className="flex items-center gap-2 ml-auto">
                {g.source_subreddit && (
                  <span className="text-[10px] text-text-tertiary">r/{g.source_subreddit}</span>
                )}
                {g.poster_username && (
                  <span className="text-[10px] text-text-tertiary">u/{g.poster_username}</span>
                )}
                {g.source_url && (
                  <a
                    href={g.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[10px] text-info hover:text-info/80 font-medium"
                  >
                    <ExternalLink className="w-3 h-3" />
                    View Post
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {gigs.length === 0 && <p className="text-sm text-text-tertiary text-center py-8">No gig posts yet. Run the gig post processor first.</p>}
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
    </div>
  );
}
