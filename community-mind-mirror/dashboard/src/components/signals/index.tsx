/**
 * Shared signal visualization components for the cross-source intelligence views.
 */

import { cn } from "../../lib/utils";

// ── Pipeline Stage Steps ──────────────────────────────────────

const PIPELINE_STAGES = ["paper", "code", "model", "community", "product"] as const;

const stageLabels: Record<string, string> = {
  paper: "Paper",
  code: "Code",
  model: "Model",
  community: "Community",
  product: "Product",
};

const stageColors: Record<string, string> = {
  paper: "bg-purple",
  code: "bg-info",
  model: "bg-warning",
  community: "bg-success",
  product: "bg-danger",
};

export function PipelineSteps({ currentStage }: { currentStage: string | null }) {
  const idx = PIPELINE_STAGES.indexOf((currentStage || "") as typeof PIPELINE_STAGES[number]);
  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STAGES.map((s, i) => (
        <div key={s} className="flex items-center gap-1">
          <div
            className={cn(
              "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium",
              i <= idx ? `${stageColors[s]} text-white` : "bg-bg-tertiary text-text-tertiary"
            )}
            title={stageLabels[s]}
          >
            {i + 1}
          </div>
          {i < PIPELINE_STAGES.length - 1 && (
            <div className={cn("w-4 h-0.5", i < idx ? "bg-info" : "bg-bg-tertiary")} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Velocity Badge ────────────────────────────────────────────

const velocityStyles: Record<string, string> = {
  fast: "bg-bg-success text-txt-success",
  medium: "bg-bg-warning text-txt-warning",
  slow: "bg-bg-tertiary text-text-secondary",
};

export function VelocityBadge({ velocity }: { velocity: string | null }) {
  const v = velocity || "slow";
  return (
    <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", velocityStyles[v] || velocityStyles.slow)}>
      {v}
    </span>
  );
}

// ── Traction Score Ring ───────────────────────────────────────

export function TractionScoreRing({ score, label }: { score: number | null; label: string | null }) {
  const pct = Math.min(100, Math.max(0, (score ?? 0) * 10));
  const radius = 20;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (pct / 100) * circ;

  const color = (score ?? 0) >= 7 ? "#1D9E75" : (score ?? 0) >= 4 ? "#BA7517" : "#E24B4A";

  return (
    <div className="flex items-center gap-2">
      <svg width="48" height="48" viewBox="0 0 48 48">
        <circle cx="24" cy="24" r={radius} fill="none" stroke="var(--mm-bg-tertiary)" strokeWidth="4" />
        <circle
          cx="24" cy="24" r={radius} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 24 24)"
        />
        <text x="24" y="26" textAnchor="middle" fill={color} fontSize="12" fontWeight="600">
          {score?.toFixed(1) ?? "—"}
        </text>
      </svg>
      {label && (
        <span className={cn(
          "text-[11px] font-medium px-2 py-0.5 rounded-md",
          label === "real_traction" ? "bg-bg-success text-txt-success" :
          label === "hype_only" ? "bg-bg-danger text-txt-danger" :
          label === "emerging" ? "bg-bg-info text-txt-info" :
          "bg-bg-tertiary text-text-secondary"
        )}>
          {label.replace(/_/g, " ")}
        </span>
      )}
    </div>
  );
}

// ── Lifecycle Bar ─────────────────────────────────────────────

const LIFECYCLE_STAGES = ["research", "experimentation", "growth", "mature", "declining"] as const;

const lifecycleColors: Record<string, string> = {
  research: "#534AB7",
  experimentation: "#378ADD",
  growth: "#1D9E75",
  mature: "#BA7517",
  declining: "#E24B4A",
};

export function LifecycleBar({ stage }: { stage: string | null }) {
  const idx = LIFECYCLE_STAGES.indexOf((stage || "") as typeof LIFECYCLE_STAGES[number]);
  return (
    <div className="flex items-center gap-0.5">
      {LIFECYCLE_STAGES.map((s, i) => (
        <div
          key={s}
          className="h-2 flex-1 rounded-sm"
          style={{
            background: i <= idx ? lifecycleColors[s] : "var(--mm-bg-tertiary)",
            opacity: i === idx ? 1 : i < idx ? 0.4 : 0.2,
          }}
          title={s}
        />
      ))}
    </div>
  );
}

// ── Divergence Bars ───────────────────────────────────────────

interface DivergenceProps {
  reddit: number | null;
  hn: number | null;
  youtube: number | null;
  ph: number | null;
}

const platformColors: Record<string, string> = {
  Reddit: "#FF4500",
  HN: "#FF6600",
  YouTube: "#FF0000",
  PH: "#DA552F",
};

export function DivergenceBars({ reddit, hn, youtube, ph }: DivergenceProps) {
  const platforms = [
    { name: "Reddit", val: reddit },
    { name: "HN", val: hn },
    { name: "YouTube", val: youtube },
    { name: "PH", val: ph },
  ];
  return (
    <div className="space-y-1">
      {platforms.map((p) => {
        const val = p.val ?? 0;
        const pct = Math.max(0, Math.min(100, (val + 1) * 50));
        return (
          <div key={p.name} className="flex items-center gap-2">
            <span className="text-[10px] text-text-secondary w-12 text-right">{p.name}</span>
            <div className="flex-1 h-2 bg-bg-tertiary rounded-sm overflow-hidden relative">
              <div className="absolute left-1/2 top-0 w-px h-full bg-border-primary" />
              <div
                className="h-full rounded-sm absolute"
                style={{
                  left: val >= 0 ? "50%" : `${pct}%`,
                  width: `${Math.abs(val) * 50}%`,
                  background: platformColors[p.name],
                  opacity: 0.7,
                }}
              />
            </div>
            <span className={cn("text-[10px] font-mono w-8", val > 0 ? "text-success" : val < 0 ? "text-danger" : "text-text-tertiary")}>
              {val > 0 ? "+" : ""}{val.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Gap Signal Badge ──────────────────────────────────────────

const gapStyles: Record<string, string> = {
  underserved: "bg-bg-danger text-txt-danger",
  crowded_but_hated: "bg-bg-warning text-txt-warning",
  emerging_need: "bg-bg-info text-txt-info",
  saturated: "bg-bg-tertiary text-text-secondary",
};

export function GapSignalBadge({ signal }: { signal: string | null }) {
  const s = signal || "unknown";
  return (
    <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", gapStyles[s] || "bg-bg-tertiary text-text-secondary")}>
      {s.replace(/_/g, " ")}
    </span>
  );
}

// ── Threat Score Bar ──────────────────────────────────────────

export function ThreatScoreBar({ score }: { score: number | null }) {
  const pct = Math.min(100, Math.max(0, (score ?? 0) * 10));
  const color = (score ?? 0) >= 7 ? "#E24B4A" : (score ?? 0) >= 4 ? "#BA7517" : "#1D9E75";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-bg-tertiary rounded-sm overflow-hidden">
        <div className="h-full rounded-sm" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono" style={{ color }}>{score?.toFixed(1) ?? "—"}</span>
    </div>
  );
}

// ── Insight Card ──────────────────────────────────────────────

interface InsightCardProps {
  category: string | null;
  insight: string | null;
  confidence: string | null;
  color: string | null;
  recommended_action: string | null;
  signals_used: string[] | null;
}

const categoryIcons: Record<string, string> = {
  opportunity: "🎯",
  threat: "⚠️",
  trend: "📈",
  anomaly: "🔍",
};

export function InsightCard({ category, insight, confidence, recommended_action, signals_used }: InsightCardProps) {
  return (
    <div className="card space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-sm">{categoryIcons[category || ""] || "💡"}</span>
        <span className="text-[11px] font-medium text-text-secondary uppercase">{category || "insight"}</span>
        {confidence && (
          <span className={cn(
            "ml-auto px-2 py-0.5 rounded-md text-[10px] font-medium",
            confidence === "high" ? "bg-bg-success text-txt-success" :
            confidence === "medium" ? "bg-bg-warning text-txt-warning" :
            "bg-bg-tertiary text-text-secondary"
          )}>
            {confidence}
          </span>
        )}
      </div>
      <p className="text-[12px] text-text-primary leading-relaxed">{insight}</p>
      {recommended_action && (
        <p className="text-[11px] text-info">{recommended_action}</p>
      )}
      {signals_used && signals_used.length > 0 && (
        <div className="flex gap-1 flex-wrap">
          {signals_used.map((s) => (
            <span key={s} className="tag">{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Agent Status Card ─────────────────────────────────────────

interface AgentStatusCardProps {
  name: string;
  model: string | null;
  lastRun: string | null;
  status: string | null;
  successRate: number | null;
  totalRuns: number;
  onTrigger?: () => void;
  triggering?: boolean;
}

export function AgentStatusCard({ name, model, lastRun, status, successRate, totalRuns, onTrigger, triggering }: AgentStatusCardProps) {
  const statusColor = status === "success" ? "text-success" : status === "error" ? "text-danger" : status === "running" ? "text-info" : "text-text-tertiary";
  const rate = successRate != null ? Math.round(successRate * 100) : null;

  return (
    <div className="card space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[12px] font-medium text-text-primary">{name.replace(/_/g, " ")}</span>
        <span className={cn("w-2 h-2 rounded-full", status === "success" ? "bg-success" : status === "error" ? "bg-danger" : status === "running" ? "bg-info" : "bg-text-tertiary")} />
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
        <span className="text-text-secondary">Model</span>
        <span className="text-text-primary">{model || "—"}</span>
        <span className="text-text-secondary">Last run</span>
        <span className={statusColor}>{status || "never"}</span>
        <span className="text-text-secondary">Success rate</span>
        <span className="text-text-primary">{rate != null ? `${rate}%` : "—"} ({totalRuns} runs)</span>
      </div>
      {lastRun && <span className="text-[10px] text-text-tertiary block">{lastRun}</span>}
      {onTrigger && (
        <button
          onClick={onTrigger}
          disabled={triggering}
          className={cn(
            "w-full mt-1 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-opacity disabled:opacity-70",
            triggering ? "bg-bg-success text-txt-success" : "bg-bg-info text-txt-info hover:opacity-80"
          )}
        >
          {triggering ? "Triggered" : "Run now"}
        </button>
      )}
    </div>
  );
}

// ── Opportunity Score ─────────────────────────────────────────

export function OpportunityScore({ score }: { score: number | null }) {
  const pct = Math.min(100, Math.max(0, (score ?? 0) * 10));
  const color = (score ?? 0) >= 7 ? "#1D9E75" : (score ?? 0) >= 4 ? "#BA7517" : "#9C9A92";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-bg-tertiary rounded-sm overflow-hidden">
        <div className="h-full rounded-sm" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] font-mono" style={{ color }}>{score?.toFixed(1) ?? "—"}</span>
    </div>
  );
}

// ── Classification Badge ──────────────────────────────────────

const classStyles: Record<string, string> = {
  smart_money_early: "bg-bg-success text-txt-success",
  hype_capital: "bg-bg-danger text-txt-danger",
  consensus_bet: "bg-bg-info text-txt-info",
  underfunded: "bg-bg-warning text-txt-warning",
  cooling_interest: "bg-bg-tertiary text-text-secondary",
};

export function ClassificationBadge({ value }: { value: string | null }) {
  const v = value || "unknown";
  return (
    <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", classStyles[v] || "bg-bg-tertiary text-text-secondary")}>
      {v.replace(/_/g, " ")}
    </span>
  );
}

// ── Salary Pressure Badge ─────────────────────────────────────

const pressureStyles: Record<string, string> = {
  high: "bg-bg-danger text-txt-danger",
  moderate: "bg-bg-warning text-txt-warning",
  low: "bg-bg-success text-txt-success",
  none: "bg-bg-tertiary text-text-secondary",
};

export function SalaryPressureBadge({ value }: { value: string | null }) {
  const v = value || "none";
  return (
    <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", pressureStyles[v] || "bg-bg-tertiary text-text-secondary")}>
      {v} pressure
    </span>
  );
}

// ── Shift Type Badge ──────────────────────────────────────────

const shiftStyles: Record<string, string> = {
  hype_to_pragmatism: "bg-bg-success text-txt-success",
  fear_to_acceptance: "bg-bg-info text-txt-info",
  dismissal_to_adoption: "bg-bg-purple text-txt-purple",
  hype_to_backlash: "bg-bg-danger text-txt-danger",
  dismissal_to_criticism: "bg-bg-warning text-txt-warning",
};

export function ShiftTypeBadge({ value }: { value: string | null }) {
  const v = value || "unknown";
  return (
    <span className={cn("px-2 py-0.5 rounded-md text-[11px] font-medium", shiftStyles[v] || "bg-bg-tertiary text-text-secondary")}>
      {v.replace(/_/g, " ")}
    </span>
  );
}

// ── Trend Arrow ───────────────────────────────────────────────

export function TrendArrow({ trend }: { trend: string | null }) {
  if (trend === "widening" || trend === "increasing") return <span className="text-danger text-[11px]">↑ {trend}</span>;
  if (trend === "narrowing" || trend === "decreasing") return <span className="text-success text-[11px]">↓ {trend}</span>;
  return <span className="text-text-tertiary text-[11px]">→ {trend || "stable"}</span>;
}

// ── Demand Supply Bar ─────────────────────────────────────────

export function DemandSupplyBar({ demand, supply }: { demand: number | null; supply: number | null }) {
  const d = demand ?? 0;
  const s = supply ?? 0;
  const max = Math.max(d, s, 1);
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-text-secondary w-14 text-right">Demand</span>
      <div className="flex-1 h-3 bg-bg-tertiary rounded-sm overflow-hidden relative">
        <div className="absolute inset-y-0 left-0 bg-danger/60 rounded-sm" style={{ width: `${(d / max) * 100}%` }} />
        <div className="absolute inset-y-0 left-0 bg-success/60 rounded-sm" style={{ width: `${(s / max) * 100}%`, opacity: 0.5 }} />
      </div>
      <span className="text-[10px] text-text-secondary w-14">Supply</span>
      <span className="text-[10px] font-mono text-text-primary w-12 text-right">{d}/{s}</span>
    </div>
  );
}

// ── VC Signal Indicator ───────────────────────────────────────

const vcStyles: Record<string, string> = {
  strong: "bg-success",
  moderate: "bg-warning",
  weak: "bg-text-tertiary",
  none: "bg-bg-tertiary",
};

export function VCSignalDots({ signal }: { signal: string | null }) {
  const v = signal || "none";
  const filled = v === "strong" ? 3 : v === "moderate" ? 2 : v === "weak" ? 1 : 0;
  return (
    <div className="flex items-center gap-0.5" title={`VC signal: ${v}`}>
      {[0, 1, 2].map((i) => (
        <div key={i} className={cn("w-2 h-2 rounded-full", i < filled ? vcStyles[v] : "bg-bg-tertiary")} />
      ))}
      <span className="text-[10px] text-text-secondary ml-1">{v}</span>
    </div>
  );
}
