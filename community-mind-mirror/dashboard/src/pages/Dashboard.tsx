import { Link } from "react-router-dom";
import { ExternalLink, Radar, Briefcase } from "lucide-react";
import {
  useOverview, usePulse,
  useHypeIndex, usePainPoints, useLeaderShifts, useFundingRounds,
  useResearch, useJobs, useCrossSourceHighlights,
  useJobIntelSummary, useJobIntelHiring, useJobIntelTechStack,
} from "../api/hooks";
import { formatNumber, timeAgo, cn, initials } from "../lib/utils";
import Badge from "../components/common/Badge";
import { CardSkeleton } from "../components/common/Skeleton";

export default function Dashboard() {
  const { data: overview, isLoading: loadingOverview } = useOverview();
  const { data: pulse } = usePulse();
  const { data: hypeIndex } = useHypeIndex();
  const { data: painPoints } = usePainPoints();
  const { data: leaderShifts } = useLeaderShifts();
  const { data: fundingRounds } = useFundingRounds();
  const { data: research } = useResearch();
  const { data: jobs } = useJobs();
  const { data: highlights } = useCrossSourceHighlights();
  const { data: jobIntelSummary } = useJobIntelSummary();
  const { data: jobIntelHiring } = useJobIntelHiring({ limit: "5" });
  const { data: jobIntelTech } = useJobIntelTechStack({ limit: "10" });

  if (loadingOverview) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Row 1: 4-col Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard label="Tracked users" value={formatNumber(overview?.total_users || 0)} badge="+312 this week" badgeType="success" />
        <MetricCard label="Active topics" value={String(overview?.total_topics || 0)} badge={`${(pulse || []).filter((t: any) => t.status === "emerging").length} emerging`} badgeType="warning" />
        <MetricCard label="Posts today" value={formatNumber(overview?.total_posts || 0)} badge={`${Object.keys(overview?.news_by_source || {}).length} platforms`} badgeType="info" />
        <MetricCard label="Hype vs reality gap" value={(hypeIndex || []).length > 0 ? ((hypeIndex || [])[0]?.gap ?? 0).toFixed(2) : "—"} subtext="moderate divergence" valueColor="text-warning" />
      </div>

      {/* Cross-source highlights */}
      {highlights && highlights.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Radar className="w-4 h-4 text-purple" />
            <h2 className="text-sm font-medium text-text-primary">Cross-source highlights</h2>
            <Link to="/signals" className="ml-auto text-[11px] text-info hover:underline">View all signals</Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {highlights.slice(0, 6).map((h, i) => {
              const bgMap: Record<string, string> = {
                opportunity: "bg-bg-success", threat: "bg-bg-danger", divergence: "bg-bg-warning",
                hype: "bg-bg-purple", insight: "bg-bg-info",
              };
              const txtMap: Record<string, string> = {
                opportunity: "text-txt-success", threat: "text-txt-danger", divergence: "text-txt-warning",
                hype: "text-txt-purple", insight: "text-txt-info",
              };
              return (
                <div key={i} className="bg-bg-secondary rounded-lg p-3 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-medium", bgMap[h.type] || "bg-bg-tertiary", txtMap[h.type] || "text-text-secondary")}>
                      {h.type}
                    </span>
                    {h.confidence && (
                      <span className="text-[10px] text-text-tertiary ml-auto">{h.confidence}</span>
                    )}
                  </div>
                  <p className="text-[12px] font-medium text-text-primary">{h.title}</p>
                  {h.description && <p className="text-[11px] text-text-secondary line-clamp-2">{h.description}</p>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Row 2: 1.6fr / 1fr — Trending + (Hype + Leaders) */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-3">
        {/* Trending Topics */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-text-primary">Trending topics</h2>
            <div className="flex gap-1">
              <span className="tag">All</span>
              <span className="tag-active">Emerging</span>
              <span className="tag">Peaking</span>
            </div>
          </div>
          <div className="divide-y divide-border-primary">
            {(pulse || []).slice(0, 5).map((t: any) => (
              <Link key={t.id} to={`/topics/${t.id}`} className="block py-2.5 hover:bg-bg-secondary/50 transition-colors">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium text-text-primary">{t.name}</span>
                  <div className="flex items-center gap-1">
                    {t.status && <Badge label={t.status} />}
                    <span className={cn("text-[11px]", (t.velocity || 0) > 0 ? "text-success" : "text-danger")}>
                      {(t.velocity || 0) > 0 ? "+" : ""}{((t.velocity || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                {/* Sentiment bar */}
                <SentimentBar
                  positive={t.sentiment_distribution?.positive || 0}
                  negative={t.sentiment_distribution?.negative || 0}
                  neutral={t.sentiment_distribution?.neutral || 0}
                />
                <div className="flex items-center gap-1 mt-1">
                  {(t.keywords || []).slice(0, 3).map((kw: string) => (
                    <span key={kw} className="tag">{kw}</span>
                  ))}
                  <span className="text-[12px] text-text-secondary ml-auto">{formatNumber(t.total_mentions || 0)} mentions</span>
                </div>
              </Link>
            ))}
            {(pulse || []).length === 0 && <p className="text-sm text-text-tertiary py-4">No trending topics yet</p>}
          </div>
        </div>

        {/* Right column: Hype + Leaders stacked */}
        <div className="flex flex-col gap-3">
          {/* Hype vs Reality Index */}
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-1">Hype vs reality index</h2>
            <p className="text-[12px] text-text-secondary mb-3">VC/press sentiment vs builder sentiment gap</p>
            <div className="space-y-3">
              {(hypeIndex || []).slice(0, 4).map((h: any) => {
                const builderPct = Math.round(((h.builder_sentiment ?? 0) + 1) * 50);
                const vcPct = Math.round(((h.vc_sentiment ?? 0) + 1) * 50);
                const statusLabel = h.status === "overhyped" ? "Overhyped" : h.status === "underhyped" ? "Underhyped" : h.status === "aligned" ? "Aligned" : (h.status || "—");
                const statusColor = h.status === "overhyped" ? "text-danger" : h.status === "aligned" ? "text-success" : "text-warning";
                return (
                  <div key={h.id}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] text-text-primary">{h.topic_name || h.sector_name}</span>
                      <span className={cn("text-[11px]", statusColor)}>{statusLabel}</span>
                    </div>
                    <div className="relative h-4 bg-bg-secondary rounded-lg overflow-hidden">
                      <div className="absolute left-0 top-0 h-full rounded-lg opacity-30" style={{ width: `${vcPct}%`, background: vcPct > builderPct ? "#E24B4A" : "#1D9E75" }} />
                      <div className="absolute left-0 top-0 h-full rounded-lg opacity-60" style={{ width: `${builderPct}%`, background: "#1D9E75" }} />
                    </div>
                    <div className="flex justify-between mt-0.5">
                      <span className="text-[10px] text-text-tertiary">Builders: {builderPct}%</span>
                      <span className="text-[10px] text-text-tertiary">VCs: {vcPct}%</span>
                    </div>
                  </div>
                );
              })}
              {(hypeIndex || []).length === 0 && <p className="text-sm text-text-tertiary">No hype data yet</p>}
            </div>
          </div>

          {/* Opinion Leaders Shifting */}
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Opinion leaders shifting</h2>
            <div className="space-y-2.5">
              {(leaderShifts || []).slice(0, 3).map((ls: any) => (
                <div key={ls.id} className="pb-2.5 border-b border-border-primary last:border-0 last:pb-0">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-7 h-7 rounded-full bg-bg-info flex items-center justify-center text-[11px] font-medium text-txt-info shrink-0">
                      {initials(ls.persona_name || "?")}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[12px] font-medium text-text-primary truncate">{ls.persona_name || "Unknown"}</div>
                      <div className="text-[11px] text-text-secondary">{ls.topic_name}</div>
                    </div>
                    {ls.shift_type && <Badge label={ls.shift_type.replace(/_/g, " ")} className="ml-auto shrink-0" />}
                  </div>
                  {ls.summary && <p className="text-[12px] text-text-secondary line-clamp-2">{ls.summary}</p>}
                </div>
              ))}
              {(leaderShifts || []).length === 0 && <p className="text-sm text-text-tertiary">No leader shifts detected yet</p>}
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Pain Points + Funding */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Pain Point Radar */}
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Pain point radar</h2>
          <p className="text-[12px] text-text-secondary mb-3">Most discussed unresolved problems this week</p>
          <div className="space-y-2">
            {(painPoints || []).slice(0, 4).map((pp: any) => {
              const intensity = pp.intensity_score != null ? Math.round(pp.intensity_score * 100) : 0;
              const bgColor = intensity > 80 ? "bg-bg-danger" : intensity > 60 ? "bg-bg-warning" : "bg-bg-info";
              const txtColor = intensity > 80 ? "text-txt-danger" : intensity > 60 ? "text-txt-warning" : "text-txt-info";
              return (
                <div key={pp.id} className="flex items-start gap-3">
                  <div className={cn("w-9 h-9 rounded-md flex items-center justify-center shrink-0", bgColor)}>
                    <span className={cn("text-[13px] font-medium", txtColor)}>{intensity}</span>
                  </div>
                  <div className="min-w-0">
                    <div className="text-[12px] font-medium text-text-primary truncate">{pp.title}</div>
                    <div className="text-[12px] text-text-secondary line-clamp-1">{pp.description || "No description"}</div>
                  </div>
                </div>
              );
            })}
            {(painPoints || []).length === 0 && <p className="text-sm text-text-tertiary">No pain points identified yet</p>}
          </div>
        </div>

        {/* Funding Signal Tracker */}
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-1">Funding signal tracker</h2>
          <p className="text-[12px] text-text-secondary mb-3">Recent raises + community reaction</p>
          <div className="space-y-2">
            {(fundingRounds || []).slice(0, 3).map((fr: any) => {
              const sentPct = fr.community_sentiment != null ? Math.round(((fr.community_sentiment + 1) / 2) * 100) : null;
              return (
                <div key={fr.id} className="pb-2 border-b border-border-primary last:border-0 last:pb-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-[12px] font-medium text-text-primary">{fr.company_name}</span>
                    <span className="text-[12px] font-medium text-success">{fr.amount} {fr.stage}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] text-text-secondary">{fr.sector}{fr.location ? `, ${fr.location}` : ""}</span>
                    {sentPct != null && (
                      <Badge label={`${sentPct}% ${sentPct >= 50 ? "positive" : "negative"}`} variant={sentPct >= 50 ? "positive" : "negative"} />
                    )}
                  </div>
                  {fr.reaction_summary && <p className="text-[12px] text-text-secondary mt-0.5">{fr.reaction_summary}</p>}
                </div>
              );
            })}
            {(fundingRounds || []).length === 0 && <p className="text-sm text-text-tertiary">No funding data yet</p>}
          </div>
        </div>
      </div>

      {/* Row 4: Job Market Intelligence */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-info" />
            <h2 className="text-sm font-medium text-text-primary">Job market intelligence</h2>
          </div>
          <Link to="/intelligence" className="text-[11px] text-info hover:underline">Full analysis →</Link>
        </div>

        {/* Summary metrics row */}
        {jobIntelSummary && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3">
            <div className="bg-bg-secondary rounded-md p-2.5">
              <div className="text-[11px] text-text-secondary">Jobs Analyzed</div>
              <div className="text-[18px] font-medium text-text-primary">{formatNumber(jobIntelSummary.total_processed)}</div>
            </div>
            <div className="bg-bg-secondary rounded-md p-2.5">
              <div className="text-[11px] text-text-secondary">Remote</div>
              <div className="text-[18px] font-medium text-info">
                {Math.round(((jobIntelSummary.by_remote_policy.find(r => r.policy === "fully_remote")?.count || 0) / jobIntelSummary.total_processed) * 100)}%
              </div>
            </div>
            <div className="bg-bg-secondary rounded-md p-2.5">
              <div className="text-[11px] text-text-secondary">AI-Core</div>
              <div className="text-[18px] font-medium text-purple">
                {Math.round(((jobIntelSummary.by_ai_level.find(r => r.level === "core_product")?.count || 0) / jobIntelSummary.total_processed) * 100)}%
              </div>
            </div>
            <div className="bg-bg-secondary rounded-md p-2.5">
              <div className="text-[11px] text-text-secondary">Top Market</div>
              <div className="text-[14px] font-medium text-text-primary">{(jobIntelSummary.by_market[0]?.market || "—").replace(/_/g, " ")}</div>
            </div>
            <div className="bg-bg-secondary rounded-md p-2.5">
              <div className="text-[11px] text-text-secondary">Top Role</div>
              <div className="text-[14px] font-medium text-text-primary">{(jobIntelSummary.by_role.filter(r => r.role !== "other")[0]?.role || "—").replace(/_/g, " ")}</div>
            </div>
          </div>
        )}

        {/* Top hiring companies + Tech stack side by side */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Top hiring */}
          <div>
            <h3 className="text-[11px] font-medium text-text-secondary mb-2">Top hiring companies</h3>
            <div className="space-y-1.5">
              {(jobIntelHiring?.companies || []).slice(0, 5).map((c, i) => (
                <div key={`${c.company}-${i}`} className="flex items-center justify-between text-[12px]">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-text-primary font-medium truncate">{c.company}</span>
                    {c.ai_level && c.ai_level !== "minimal" && c.ai_level !== "none" && (
                      <span className="inline-block px-1 py-0.5 rounded text-[9px] bg-bg-purple text-txt-purple shrink-0">AI</span>
                    )}
                  </div>
                  <span className="text-text-secondary font-mono shrink-0 ml-2">{c.open_roles} roles</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top tech */}
          <div>
            <h3 className="text-[11px] font-medium text-text-secondary mb-2">Most demanded tech</h3>
            <div className="space-y-1">
              {(jobIntelTech?.technologies || []).slice(0, 8).map((t) => {
                const maxM = jobIntelTech?.technologies[0]?.mentions || 1;
                return (
                  <div key={t.name} className="flex items-center gap-2 text-[12px]">
                    <span className="text-text-primary w-20 truncate">{t.name}</span>
                    <div className="flex-1 h-2 bg-bg-secondary rounded-sm overflow-hidden">
                      <div className="h-full bg-info rounded-sm" style={{ width: `${(t.mentions / maxM) * 100}%` }} />
                    </div>
                    <span className="text-text-tertiary font-mono w-8 text-right">{t.mentions}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Role growth cards (keep original) */}
        {(jobs?.role_cards || []).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3 pt-3 border-t border-border-primary">
            {(jobs?.role_cards || []).slice(0, 5).map((j: any, i: number) => (
              <div key={j.role || i} className="bg-bg-secondary rounded-md p-2">
                <div className="text-[11px] text-text-secondary mb-0.5">{j.role}</div>
                <div className={cn("text-sm font-medium", j.growth > 0 ? "text-success" : j.growth < 0 ? "text-danger" : "text-text-secondary")}>
                  {j.growth > 0 ? "+" : ""}{j.growth}%
                </div>
                <div className="text-[11px] text-text-secondary">{formatNumber(j.count)} listings</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Row 5: Research Radar */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-sm font-medium text-text-primary">Research radar — ArXiv hot papers</h2>
            <p className="text-[12px] text-text-secondary">Papers gaining unusual community traction</p>
          </div>
        </div>
        <div className="divide-y divide-border-primary">
          {(research || []).slice(0, 5).map((r: any) => (
            <div key={r.id} className="flex items-start gap-3 py-2">
              <div className="flex-1 min-w-0">
                <div className="text-[12px] font-medium text-text-primary truncate">{r.title}</div>
                <div className="text-[12px] text-text-secondary">{r.source_name} — {timeAgo(r.published_at)}</div>
              </div>
              <div className="text-right shrink-0">
                {r.score != null && <div className="text-[12px] font-medium text-success">{r.score} HN pts</div>}
                {r.url && (
                  <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info">
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          ))}
          {(research || []).length === 0 && <p className="text-sm text-text-tertiary py-4">No research data yet</p>}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, badge, badgeType, subtext, valueColor }: {
  label: string;
  value: string;
  badge?: string;
  badgeType?: "success" | "warning" | "info" | "danger";
  subtext?: string;
  valueColor?: string;
}) {
  const badgeColors = {
    success: "bg-bg-success text-txt-success",
    warning: "bg-bg-warning text-txt-warning",
    info: "bg-bg-info text-txt-info",
    danger: "bg-bg-danger text-txt-danger",
  };
  return (
    <div className="bg-bg-secondary rounded-lg p-3">
      <div className="text-[12px] text-text-secondary mb-1">{label}</div>
      <div className="flex items-center gap-2">
        <span className={cn("text-[22px] font-medium", valueColor || "text-text-primary")}>{value}</span>
        {badge && badgeType && (
          <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium", badgeColors[badgeType])}>{badge}</span>
        )}
        {subtext && <span className="text-[12px] text-text-secondary">{subtext}</span>}
      </div>
    </div>
  );
}

function SentimentBar({ positive, negative, neutral }: { positive: number; negative: number; neutral: number }) {
  const total = positive + negative + neutral || 1;
  const pPct = (positive / total) * 100;
  const nPct = (negative / total) * 100;
  const neuPct = (neutral / total) * 100;
  return (
    <div className="h-1.5 rounded-full flex overflow-hidden">
      <div style={{ width: `${pPct}%` }} className="bg-success" />
      <div style={{ width: `${nPct}%` }} className="bg-danger" />
      <div style={{ width: `${neuPct}%` }} className="bg-border-secondary" />
    </div>
  );
}
