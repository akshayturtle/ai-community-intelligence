import { useState } from "react";
import {
  Package, ArrowRightLeft, AlertTriangle, Briefcase,
  TrendingUp, TrendingDown, Minus,
  DollarSign, MapPin, Cpu, Building2, Heart, Users,
  Star, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import {
  useProducts, useMigrations, useUnmetNeeds,
  useJobIntelSummary, useJobIntelTechStack, useJobIntelSalary,
  useJobIntelHiring, useJobIntelGeo, useJobIntelAI,
  useJobIntelStages, useJobIntelBenefits, useJobIntelSkills,
  useProductReviews, useProductReviewSummary,
} from "../api/hooks";
import { formatNumber, sentimentColor, cn } from "../lib/utils";
import { CardSkeleton } from "../components/common/Skeleton";
import Pagination from "../components/common/Pagination";

const tabs = [
  { key: "products", label: "Product Landscape", icon: Package },
  { key: "reviews", label: "Product Reviews", icon: Star },
  { key: "migrations", label: "Migration Patterns", icon: ArrowRightLeft },
  { key: "unmet", label: "Unmet Needs", icon: AlertTriangle },
  { key: "jobs", label: "Job Market", icon: Briefcase },
] as const;

type TabKey = typeof tabs[number]["key"];

function TrendIcon({ trend }: { trend: string | null }) {
  if (trend === "up") return <TrendingUp className="w-4 h-4 text-success" />;
  if (trend === "down") return <TrendingDown className="w-4 h-4 text-danger" />;
  return <Minus className="w-4 h-4 text-text-tertiary" />;
}

export default function Intelligence() {
  const [tab, setTab] = useState<TabKey>("products");
  const [productPage, setProductPage] = useState(1);
  const [reviewPage, setReviewPage] = useState(1);

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-medium text-text-primary">Competitive intelligence</h1>

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-primary border border-border-primary rounded-xl p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors flex-1 justify-center",
              tab === t.key
                ? "bg-bg-info text-txt-info"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
            )}
          >
            <t.icon className="w-4 h-4" />
            <span className="hidden md:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {tab === "products" && <ProductTab page={productPage} onPageChange={setProductPage} />}
      {tab === "reviews" && <ProductReviewsTab page={reviewPage} onPageChange={setReviewPage} />}
      {tab === "migrations" && <MigrationTab />}
      {tab === "unmet" && <UnmetNeedsTab />}
      {tab === "jobs" && <JobsTab />}
    </div>
  );
}

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  const s = sentiment || "unknown";
  const cls =
    s === "positive" ? "bg-bg-success text-txt-success" :
    s === "negative" ? "bg-bg-danger text-txt-danger" :
    s === "mixed" ? "bg-bg-warning text-txt-warning" :
    "bg-bg-secondary text-text-secondary";
  return <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium", cls)}>{s}</span>;
}

function SatisfactionBar({ score }: { score: number | null }) {
  const v = score ?? 0;
  const color = v >= 70 ? "#1D9E75" : v >= 40 ? "#BA7517" : "#E24B4A";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-bg-secondary rounded-sm overflow-hidden">
        <div className="h-full rounded-sm" style={{ width: `${v}%`, background: color }} />
      </div>
      <span className="text-[12px] font-mono text-text-secondary w-8 text-right">{v}</span>
    </div>
  );
}

function ProductReviewsTab({ page, onPageChange }: { page: number; onPageChange: (p: number) => void }) {
  const { data: summary, isLoading: loadingSummary } = useProductReviewSummary();
  const { data, isLoading } = useProductReviews({ page: String(page), per_page: "20" });
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (loadingSummary && isLoading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}</div>;

  const reviews = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Total Reviews</div>
          <div className="text-[22px] font-medium text-text-primary">{formatNumber(summary?.total_reviews || 0)}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Avg Satisfaction</div>
          <div className="text-[22px] font-medium text-success">{summary?.avg_satisfaction ?? "—"}</div>
          <div className="text-[11px] text-text-tertiary">out of 100</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Sentiment</div>
          <div className="flex gap-2 mt-1">
            {summary?.sentiment_distribution && Object.entries(summary.sentiment_distribution).map(([k]) => (
              <SentimentBadge key={k} sentiment={k} />
            ))}
          </div>
          <div className="flex gap-2 mt-0.5">
            {summary?.sentiment_distribution && Object.entries(summary.sentiment_distribution).map(([k, val]) => (
              <span key={k} className="text-[11px] text-text-tertiary">{val}</span>
            ))}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Top Rated</div>
          {(summary?.top_rated || []).slice(0, 3).map((r) => (
            <div key={r.product} className="text-[12px] text-text-primary flex justify-between">
              <span className="truncate">{r.product}</span>
              <span className="text-success font-mono ml-1">{r.score}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Top Feature Requests + Churn Reasons */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Top feature requests</h2>
            <div className="space-y-1">
              {(summary.top_feature_requests || []).slice(0, 8).map((f) => (
                <div key={f.request} className="flex items-center justify-between text-[12px]">
                  <span className="text-text-primary">{f.request}</span>
                  <span className="text-text-secondary font-mono">{f.count}</span>
                </div>
              ))}
              {(summary.top_feature_requests || []).length === 0 && <p className="text-sm text-text-tertiary py-2">No data yet</p>}
            </div>
          </div>
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Top churn reasons</h2>
            <div className="space-y-1">
              {(summary.top_churn_reasons || []).slice(0, 8).map((c) => (
                <div key={c.reason} className="flex items-center justify-between text-[12px]">
                  <span className="text-text-primary">{c.reason}</span>
                  <span className="text-text-secondary font-mono">{c.count}</span>
                </div>
              ))}
              {(summary.top_churn_reasons || []).length === 0 && <p className="text-sm text-text-tertiary py-2">No data yet</p>}
            </div>
          </div>
        </div>
      )}

      {/* Review Cards */}
      <div className="space-y-3">
        {reviews.map((r) => {
          const expanded = expandedId === r.id;
          return (
            <div key={r.id} className="card">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="text-sm font-medium text-text-primary">{r.product_name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <SentimentBadge sentiment={r.overall_sentiment} />
                    <span className="text-[11px] text-text-tertiary">{r.post_count || 0} posts analyzed</span>
                    {r.source_subreddits && r.source_subreddits.length > 0 && (
                      <span className="text-[11px] text-text-tertiary">from {r.source_subreddits.slice(0, 3).join(", ")}</span>
                    )}
                  </div>
                </div>
                <div className="w-32">
                  <SatisfactionBar score={r.satisfaction_score} />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-2">
                {/* Pros */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <ThumbsUp className="w-3 h-3 text-success" />
                    <span className="text-[11px] font-medium text-text-secondary">Pros</span>
                  </div>
                  <div className="space-y-0.5">
                    {(r.pros || []).slice(0, 4).map((p, i) => (
                      <div key={i} className="text-[12px] text-text-primary">+ {p}</div>
                    ))}
                    {(!r.pros || r.pros.length === 0) && <span className="text-[11px] text-text-tertiary">None extracted</span>}
                  </div>
                </div>
                {/* Cons */}
                <div>
                  <div className="flex items-center gap-1 mb-1">
                    <ThumbsDown className="w-3 h-3 text-danger" />
                    <span className="text-[11px] font-medium text-text-secondary">Cons</span>
                  </div>
                  <div className="space-y-0.5">
                    {(r.cons || []).slice(0, 4).map((c, i) => (
                      <div key={i} className="text-[12px] text-text-primary">- {c}</div>
                    ))}
                    {(!r.cons || r.cons.length === 0) && <span className="text-[11px] text-text-tertiary">None extracted</span>}
                  </div>
                </div>
              </div>

              {/* Feature Requests (always shown if exist) */}
              {r.feature_requests && r.feature_requests.length > 0 && (
                <div className="mb-2">
                  <span className="text-[11px] font-medium text-text-secondary">Feature requests: </span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {r.feature_requests.slice(0, 5).map((f, i) => (
                      <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-info text-txt-info">{f}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Expandable: Churn Reasons + Competitor Comparisons */}
              <button
                onClick={() => setExpandedId(expanded ? null : r.id)}
                className="flex items-center gap-1 text-[11px] text-text-tertiary hover:text-text-primary transition-colors"
              >
                {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                {expanded ? "Less" : "More"} details
              </button>

              {expanded && (
                <div className="mt-2 pt-2 border-t border-border-primary space-y-2">
                  {r.common_use_cases && r.common_use_cases.length > 0 && (
                    <div>
                      <span className="text-[11px] font-medium text-text-secondary">Common use cases: </span>
                      <span className="text-[12px] text-text-primary">{r.common_use_cases.join(", ")}</span>
                    </div>
                  )}
                  {r.churn_reasons && r.churn_reasons.length > 0 && (
                    <div>
                      <span className="text-[11px] font-medium text-text-secondary">Churn reasons: </span>
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {r.churn_reasons.map((c, i) => (
                          <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-danger text-txt-danger">{c}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {r.competitor_comparisons && r.competitor_comparisons.length > 0 && (
                    <div>
                      <span className="text-[11px] font-medium text-text-secondary">Competitor comparisons:</span>
                      <div className="space-y-1 mt-0.5">
                        {r.competitor_comparisons.map((cc, i) => (
                          <div key={i} className="text-[12px]">
                            <span className="font-medium text-text-primary">{cc.competitor}:</span>{" "}
                            <span className="text-text-secondary">{cc.context}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {reviews.length === 0 && <p className="text-sm text-text-tertiary text-center py-8">No product reviews yet. Run the product review processor first.</p>}
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />}
    </div>
  );
}

function ProductTab({ page, onPageChange }: { page: number; onPageChange: (p: number) => void }) {
  const { data, isLoading } = useProducts({ page: String(page), per_page: "30" });

  if (isLoading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}</div>;

  const products = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Product landscape — from the community's mouth</h2>
        <p className="text-[12px] text-text-secondary mb-3">How the community organically recommends and compares tools (last 30 days)</p>

        {/* Table header */}
        <div className="grid grid-cols-[2fr_1fr_1fr_1fr_1fr] gap-0 text-[12px]">
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary">Product</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Mentions</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Sentiment</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Trend</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Recommended?</div>

          {products.map((p) => {
            const recRate = p.recommendation_rate != null ? Math.round(p.recommendation_rate * 100) : 0;
            const recColor = recRate >= 70 ? "#1D9E75" : recRate >= 50 ? "#BA7517" : "#E24B4A";
            return (
              <div key={p.id} className="contents">
                <div className="p-2 border-b border-border-primary">
                  <span className="font-medium text-text-primary">{p.canonical_name}</span>
                  <br />
                  <span className="text-[12px] text-text-secondary">{p.category?.replace(/_/g, " ") || "other"}</span>
                </div>
                <div className="p-2 border-b border-border-primary text-center text-text-primary">{formatNumber(p.total_mentions)}</div>
                <div className={cn("p-2 border-b border-border-primary text-center", sentimentColor(p.avg_sentiment))}>
                  {p.avg_sentiment != null ? `${p.avg_sentiment > 0 ? "+" : ""}${p.avg_sentiment.toFixed(2)}` : "—"}
                </div>
                <div className="p-2 border-b border-border-primary text-center">
                  <TrendIcon trend={p.trend} />
                </div>
                <div className="p-2 border-b border-border-primary text-center">
                  <div className="w-full bg-bg-secondary rounded-sm h-2 overflow-hidden">
                    <div className="h-full rounded-sm" style={{ width: `${recRate}%`, background: recColor }} />
                  </div>
                  <span className="text-[12px] text-text-secondary">{recRate}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {products.length === 0 && <p className="text-sm text-text-tertiary text-center py-8">No products discovered yet. Run the product processor first.</p>}
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />}
    </div>
  );
}

function MigrationTab() {
  const { data: migrations, isLoading } = useMigrations();

  if (isLoading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}</div>;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {/* Migrations */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">What users switch FROM → TO</h2>
        <p className="text-[12px] text-text-secondary mb-3">Migration patterns detected in community posts</p>
        <div className="space-y-2">
          {(migrations || []).map((m, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-[12px] line-through text-text-tertiary">{m.from_product}</span>
                <span className="text-[12px] text-text-secondary">→</span>
                <span className="text-[12px] font-medium text-text-primary">{m.to_product}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block px-2 py-0.5 rounded-md text-[11px] font-medium bg-bg-danger text-txt-danger">
                  {m.count} mentions
                </span>
              </div>
            </div>
          ))}
          {(migrations || []).length === 0 && <p className="text-sm text-text-tertiary py-4">No migration patterns detected yet.</p>}
        </div>
      </div>

      {/* (Future: could add more panels here) */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Migration trends</h2>
        <p className="text-[12px] text-text-secondary mb-3">Confidence and frequency over time</p>
        <div className="space-y-2">
          {(migrations || []).map((m, i) => (
            <div key={i} className="flex items-center justify-between text-[12px]">
              <span className="text-text-primary">{m.from_product} → {m.to_product}</span>
              <span className="text-text-secondary">
                {m.avg_confidence != null ? `${(m.avg_confidence * 100).toFixed(0)}% confidence` : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function UnmetNeedsTab() {
  const { data: needs, isLoading } = useUnmetNeeds();

  if (isLoading) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}</div>;

  return (
    <div className="space-y-3">
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-1">Unmet needs (no good solution exists)</h2>
        <p className="text-[12px] text-text-secondary mb-3">Problems people discuss with no clear product recommendation</p>
        <div className="space-y-2">
          {(needs || []).map((pp) => (
            <div key={pp.id}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[12px] font-medium text-text-primary">{pp.title}</span>
                <span className="inline-block px-2 py-0.5 rounded-md text-[11px] font-medium bg-bg-danger text-txt-danger">
                  {pp.post_count || 0} posts, {pp.has_solution ? "has recs" : "0 recommendations"}
                </span>
              </div>
              {pp.description && <p className="text-[12px] text-text-secondary">{pp.description}</p>}
            </div>
          ))}
          {(needs || []).length === 0 && <p className="text-sm text-text-tertiary py-4">No unmet needs identified yet.</p>}
        </div>
      </div>
    </div>
  );
}

const PIE_COLORS = ["#378ADD", "#1D9E75", "#BA7517", "#E24B4A", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16"];

function JobsTab() {
  const { data: summary, isLoading: loadingSummary } = useJobIntelSummary();
  const { data: techData } = useJobIntelTechStack({ limit: "20" });
  const { data: salaryData } = useJobIntelSalary();
  const { data: hiringData } = useJobIntelHiring({ limit: "15" });
  const { data: geoData } = useJobIntelGeo();
  const { data: aiData } = useJobIntelAI();
  const { data: stagesData } = useJobIntelStages();
  const { data: benefitsData } = useJobIntelBenefits();
  const { data: skillsData } = useJobIntelSkills({ limit: "20" });
  const [salaryFilter, setSalaryFilter] = useState<string>("");

  if (loadingSummary) return <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 6 }).map((_, i) => <CardSkeleton key={i} />)}</div>;

  const remotePct = summary ? Math.round(((summary.by_remote_policy.find(r => r.policy === "fully_remote")?.count || 0) / summary.total_processed) * 100) : 0;
  const aiCorePct = summary ? Math.round(((summary.by_ai_level.find(r => r.level === "core_product")?.count || 0) / summary.total_processed) * 100) : 0;

  const techChart = (techData?.technologies || []).slice(0, 15).map(t => ({
    name: t.name, mentions: t.mentions, category: t.category,
  }));

  const salaryBands = (salaryData?.salary_bands || [])
    .filter(s => !salaryFilter || s.role === salaryFilter)
    .slice(0, 15);

  const salaryChart = salaryBands.map(s => ({
    name: `${s.role} (${s.seniority})`,
    min: s.median_min || 0,
    max: s.median_max || 0,
    sample: s.sample_size,
  }));

  const uniqueRoles = [...new Set((salaryData?.salary_bands || []).map(s => s.role))];

  return (
    <div className="space-y-3">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Total Jobs Analyzed</div>
          <div className="text-[22px] font-medium text-text-primary">{formatNumber(summary?.total_processed || 0)}</div>
          <div className="text-[11px] text-text-tertiary">{summary?.coverage_pct || 0}% coverage</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Fully Remote</div>
          <div className="text-[22px] font-medium text-info">{remotePct}%</div>
          <div className="text-[11px] text-text-tertiary">{formatNumber(summary?.by_remote_policy.find(r => r.policy === "fully_remote")?.count || 0)} jobs</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">AI-Core Companies</div>
          <div className="text-[22px] font-medium text-purple">{aiCorePct}%</div>
          <div className="text-[11px] text-text-tertiary">{formatNumber(summary?.by_ai_level.find(r => r.level === "core_product")?.count || 0)} jobs</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Top Market</div>
          <div className="text-[16px] font-medium text-text-primary">{(summary?.by_market[0]?.market || "—").replace(/_/g, " ")}</div>
          <div className="text-[11px] text-text-tertiary">{formatNumber(summary?.by_market[0]?.count || 0)} jobs</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Top Seniority</div>
          <div className="text-[16px] font-medium text-text-primary">{(summary?.by_seniority[0]?.seniority || "—").replace(/_/g, " ")}</div>
          <div className="text-[11px] text-text-tertiary">{formatNumber(summary?.by_seniority[0]?.count || 0)} jobs</div>
        </div>
      </div>

      {/* Row: Tech Stack + Role Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-3">
        {/* Tech Stack */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="w-4 h-4 text-info" />
            <h2 className="text-sm font-medium text-text-primary">Most demanded technologies</h2>
          </div>
          {techChart.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={techChart} layout="vertical" margin={{ left: 80, right: 20 }}>
                <XAxis type="number" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} width={75} />
                <Tooltip
                  contentStyle={{ background: "var(--mm-bg-primary)", border: "0.5px solid var(--mm-border-primary)", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: any, _: any, props: any) => [`${v} mentions`, props.payload.category]}
                />
                <Bar dataKey="mentions" fill="#378ADD" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-sm text-text-tertiary py-4">No tech stack data yet</p>}
        </div>

        {/* Role Distribution Pie */}
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-3">Role distribution</h2>
          {(summary?.by_role || []).length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={(summary?.by_role || []).filter(r => r.role !== "other").slice(0, 8)}
                    dataKey="count"
                    nameKey="role"
                    cx="50%" cy="50%"
                    outerRadius={80}
                    label={({ role, percent }: any) => `${(role as string).replace(/_/g, " ")} ${((percent || 0) * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {(summary?.by_role || []).filter(r => r.role !== "other").slice(0, 8).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: any) => formatNumber(v)} />
                </PieChart>
              </ResponsiveContainer>
              <div className="grid grid-cols-2 gap-1 mt-2">
                {(summary?.by_role || []).slice(0, 8).map((r, i) => (
                  <div key={r.role} className="flex items-center gap-1.5 text-[11px]">
                    <div className="w-2 h-2 rounded-full shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                    <span className="text-text-secondary truncate">{r.role.replace(/_/g, " ")}</span>
                    <span className="text-text-tertiary ml-auto">{formatNumber(r.count)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : <p className="text-sm text-text-tertiary py-4">No role data yet</p>}
        </div>
      </div>

      {/* Salary Insights */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-success" />
            <h2 className="text-sm font-medium text-text-primary">Salary insights (USD, annual)</h2>
          </div>
          <select
            value={salaryFilter}
            onChange={(e) => setSalaryFilter(e.target.value)}
            className="text-[12px] bg-bg-secondary border border-border-primary rounded-md px-2 py-1 text-text-primary"
          >
            <option value="">All roles</option>
            {uniqueRoles.map(r => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        {salaryChart.length > 0 ? (
          <ResponsiveContainer width="100%" height={Math.max(200, salaryChart.length * 28)}>
            <BarChart data={salaryChart} layout="vertical" margin={{ left: 130, right: 20 }}>
              <XAxis type="number" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <YAxis type="category" dataKey="name" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} width={125} />
              <Tooltip
                contentStyle={{ background: "var(--mm-bg-primary)", border: "0.5px solid var(--mm-border-primary)", borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [`$${formatNumber(v)}`, ""]}
              />
              <Bar dataKey="min" name="Median Min" fill="#1D9E75" radius={[0, 4, 4, 0]} stackId="salary" />
              <Bar dataKey="max" name="Median Max" fill="#378ADD" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : <p className="text-sm text-text-tertiary py-4">No salary data available</p>}
      </div>

      {/* Row: Hiring Velocity + Geographic */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Hiring Velocity */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-warning" />
            <h2 className="text-sm font-medium text-text-primary">Top hiring companies</h2>
          </div>
          <div className="space-y-2">
            {(hiringData?.companies || []).slice(0, 10).map((c, i) => (
              <div key={`${c.company}-${i}`} className="flex items-center justify-between text-[12px] pb-1.5 border-b border-border-primary last:border-0">
                <div className="min-w-0">
                  <span className="font-medium text-text-primary">{c.company}</span>
                  <div className="flex items-center gap-1 mt-0.5">
                    {c.market && <span className="tag">{c.market.replace(/_/g, " ")}</span>}
                    {c.stage && c.stage !== "unknown" && <span className="tag">{c.stage.replace(/_/g, " ")}</span>}
                    {c.ai_level && c.ai_level !== "minimal" && c.ai_level !== "none" && (
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-purple text-txt-purple">{c.ai_level.replace(/_/g, " ")}</span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <span className="text-base font-medium text-text-primary">{c.open_roles}</span>
                  <div className="text-[10px] text-text-tertiary">open roles</div>
                </div>
              </div>
            ))}
            {(!hiringData?.companies || hiringData.companies.length === 0) && <p className="text-sm text-text-tertiary py-4">No hiring data yet</p>}
          </div>
        </div>

        {/* Geographic Distribution */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <MapPin className="w-4 h-4 text-danger" />
            <h2 className="text-sm font-medium text-text-primary">Geographic distribution</h2>
          </div>
          <div className="space-y-3">
            <div>
              <h3 className="text-[11px] font-medium text-text-secondary mb-1.5">By Country</h3>
              <div className="space-y-1">
                {(geoData?.by_country || []).slice(0, 8).map((c) => {
                  const maxCount = geoData?.by_country[0]?.count || 1;
                  const pct = (c.count / maxCount) * 100;
                  return (
                    <div key={c.country} className="flex items-center gap-2 text-[12px]">
                      <span className="w-6 text-text-secondary font-mono">{c.country}</span>
                      <div className="flex-1 h-3 bg-bg-secondary rounded-sm overflow-hidden">
                        <div className="h-full bg-info rounded-sm" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-text-primary font-mono w-12 text-right">{formatNumber(c.count)}</span>
                      <span className="text-text-tertiary w-14 text-right">{c.remote_count} remote</span>
                    </div>
                  );
                })}
              </div>
            </div>
            <div>
              <h3 className="text-[11px] font-medium text-text-secondary mb-1.5">Top Cities</h3>
              <div className="grid grid-cols-2 gap-1">
                {(geoData?.by_city || []).slice(0, 10).map((c) => (
                  <div key={`${c.city}-${c.country}`} className="flex items-center justify-between text-[12px]">
                    <span className="text-text-primary truncate">{c.city}</span>
                    <span className="text-text-secondary font-mono ml-1">{c.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Row: AI Landscape + Company Stages */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* AI Tools */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="w-4 h-4 text-purple" />
            <h2 className="text-sm font-medium text-text-primary">AI/ML tools in demand</h2>
          </div>
          <div className="space-y-1">
            {(aiData?.top_ai_tools || []).slice(0, 12).map((t, i) => {
              const maxMentions = aiData?.top_ai_tools[0]?.mentions || 1;
              return (
                <div key={t.tool} className="flex items-center gap-2 text-[12px]">
                  <span className="w-4 text-text-tertiary text-right">{i + 1}</span>
                  <span className="text-text-primary w-28 truncate">{t.tool}</span>
                  <div className="flex-1 h-2.5 bg-bg-secondary rounded-sm overflow-hidden">
                    <div className="h-full bg-purple rounded-sm" style={{ width: `${(t.mentions / maxMentions) * 100}%` }} />
                  </div>
                  <span className="text-text-secondary font-mono w-10 text-right">{t.mentions}</span>
                </div>
              );
            })}
            {(!aiData?.top_ai_tools || aiData.top_ai_tools.length === 0) && <p className="text-sm text-text-tertiary py-4">No AI tool data yet</p>}
          </div>
        </div>

        {/* Company Stages */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Building2 className="w-4 h-4 text-info" />
            <h2 className="text-sm font-medium text-text-primary">Hiring by company stage</h2>
          </div>
          <div className="space-y-2">
            {(stagesData?.stages || []).map((s) => (
              <div key={s.stage} className="flex items-center justify-between text-[12px] pb-1.5 border-b border-border-primary last:border-0">
                <div>
                  <span className="font-medium text-text-primary">{s.stage.replace(/_/g, " ")}</span>
                  <div className="text-[11px] text-text-tertiary">{s.companies} companies</div>
                </div>
                <div className="text-right">
                  <span className="font-medium text-text-primary">{formatNumber(s.jobs)} jobs</span>
                  {s.avg_salary_min && s.avg_salary_max && (
                    <div className="text-[11px] text-success">${formatNumber(s.avg_salary_min)} - ${formatNumber(s.avg_salary_max)}</div>
                  )}
                </div>
              </div>
            ))}
            {(!stagesData?.stages || stagesData.stages.length === 0) && <p className="text-sm text-text-tertiary py-4">No stage data yet</p>}
          </div>
        </div>
      </div>

      {/* Row: Skills + Benefits/Culture */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Skills Demand */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-4 h-4 text-success" />
            <h2 className="text-sm font-medium text-text-primary">Top skills in demand</h2>
          </div>
          <div className="space-y-1">
            {(skillsData?.skills || []).slice(0, 15).map((s) => (
              <div key={`${s.skill}-${s.type}`} className="flex items-center gap-2 text-[12px]">
                <span className={cn(
                  "inline-block px-1.5 py-0.5 rounded text-[10px] font-medium",
                  s.type === "must_have" ? "bg-bg-danger text-txt-danger" : "bg-bg-info text-txt-info"
                )}>
                  {s.type === "must_have" ? "required" : "preferred"}
                </span>
                <span className="text-text-primary flex-1 truncate">{s.skill}</span>
                <span className="text-text-secondary font-mono">{s.mentions}</span>
              </div>
            ))}
            {(!skillsData?.skills || skillsData.skills.length === 0) && <p className="text-sm text-text-tertiary py-4">No skills data yet</p>}
          </div>
        </div>

        {/* Benefits & Culture */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Heart className="w-4 h-4 text-danger" />
            <h2 className="text-sm font-medium text-text-primary">Benefits & culture signals</h2>
          </div>
          <div className="space-y-3">
            <div>
              <h3 className="text-[11px] font-medium text-text-secondary mb-1.5">Top Benefits</h3>
              <div className="flex flex-wrap gap-1">
                {(benefitsData?.top_benefits || []).slice(0, 12).map((b) => (
                  <span key={b.benefit} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-bg-success text-txt-success">
                    {b.benefit} <span className="opacity-60">({b.count})</span>
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h3 className="text-[11px] font-medium text-text-secondary mb-1.5">Culture Signals</h3>
              <div className="flex flex-wrap gap-1">
                {(benefitsData?.top_culture_signals || []).slice(0, 12).map((c) => (
                  <span key={c.signal} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] bg-bg-purple text-txt-purple">
                    {c.signal} <span className="opacity-60">({c.count})</span>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
