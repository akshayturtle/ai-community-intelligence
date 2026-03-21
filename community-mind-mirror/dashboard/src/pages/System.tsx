import { useState } from "react";
import { Play, RefreshCw, Clock, DollarSign, CheckCircle, XCircle, Loader2 } from "lucide-react";
import {
  useAgentStatus, useAgentRuns, useAgentCosts,
  useTriggerAgent, useTriggerAllAgents, useHealth,
} from "../api/hooks";
import { formatNumber, timeAgo, cn } from "../lib/utils";
import { AgentStatusCard } from "../components/signals";
import { CardSkeleton } from "../components/common/Skeleton";

export default function System() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-medium text-text-primary">System monitor</h1>
      <AgentStatusGrid />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CostTracker />
        <RecentRuns />
      </div>
      <ScraperHealth />
    </div>
  );
}

// ── Agent Status Grid ─────────────────────────────────────────

function AgentStatusGrid() {
  const { data: agents, isLoading } = useAgentStatus();
  const triggerOne = useTriggerAgent();
  const triggerAll = useTriggerAllAgents();
  const [triggered, setTriggered] = useState<Record<string, boolean>>({});
  const [allTriggered, setAllTriggered] = useState(false);

  const handleTriggerOne = (name: string) => {
    if (triggered[name]) return;
    triggerOne.mutate(name, {
      onSuccess: () => {
        setTriggered((prev) => ({ ...prev, [name]: true }));
        setTimeout(() => setTriggered((prev) => ({ ...prev, [name]: false })), 5000);
      },
    });
  };

  const handleTriggerAll = () => {
    if (allTriggered) return;
    triggerAll.mutate(undefined, {
      onSuccess: () => {
        setAllTriggered(true);
        const all: Record<string, boolean> = {};
        (agents || []).forEach((a) => { all[a.agent_name] = true; });
        setTriggered(all);
        setTimeout(() => { setAllTriggered(false); setTriggered({}); }, 5000);
      },
    });
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-text-primary">Agent status</h2>
        <button
          onClick={handleTriggerAll}
          disabled={triggerAll.isPending || allTriggered}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium bg-bg-info text-txt-info hover:opacity-80 transition-opacity disabled:opacity-50"
        >
          {triggerAll.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : allTriggered ? <CheckCircle className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          {allTriggered ? "All triggered" : "Run all agents"}
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {(agents || []).map((a) => (
          <AgentStatusCard
            key={a.agent_name}
            name={a.agent_name}
            model={a.model}
            lastRun={a.last_run ? timeAgo(a.last_run.started_at) : null}
            status={a.last_run?.status || null}
            successRate={a.success_rate}
            totalRuns={a.total_runs}
            onTrigger={() => handleTriggerOne(a.agent_name)}
            triggering={!!triggered[a.agent_name]}
          />
        ))}
      </div>
    </div>
  );
}

// ── Cost Tracker ──────────────────────────────────────────────

function CostTracker() {
  const [days, setDays] = useState(30);
  const { data: costs, isLoading } = useAgentCosts({ days: String(days) });

  const totalCost = (costs || []).reduce((sum, c) => sum + (c.total_cost_usd || 0), 0);
  const totalTokens = (costs || []).reduce((sum, c) => sum + (c.total_tokens || 0), 0);

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-warning" />
          <h2 className="text-sm font-medium text-text-primary">Cost tracker</h2>
        </div>
        <div className="flex gap-1">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={cn(
                "px-2 py-0.5 rounded text-[11px]",
                days === d ? "bg-bg-info text-txt-info" : "text-text-secondary hover:bg-bg-secondary"
              )}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <span className="text-[11px] text-text-secondary block">Total cost</span>
          <span className="text-lg font-semibold text-text-primary">${totalCost.toFixed(2)}</span>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <span className="text-[11px] text-text-secondary block">Total tokens</span>
          <span className="text-lg font-semibold text-text-primary">{formatNumber(totalTokens)}</span>
        </div>
      </div>

      {isLoading ? (
        <CardSkeleton />
      ) : (
        <div className="space-y-1">
          {(costs || []).map((c) => (
            <div key={c.agent_name} className="flex items-center justify-between text-[11px] py-1">
              <span className="text-text-primary">{c.agent_name.replace(/_/g, " ")}</span>
              <div className="flex items-center gap-4">
                <span className="text-text-secondary">{c.total_runs} runs</span>
                <span className="text-text-secondary">{formatNumber(c.total_tokens || 0)} tok</span>
                <span className="font-mono text-text-primary w-14 text-right">
                  ${(c.total_cost_usd || 0).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
          {(costs || []).length === 0 && <p className="text-[12px] text-text-tertiary text-center py-4">No agent runs in this period.</p>}
        </div>
      )}
    </div>
  );
}

// ── Recent Runs ───────────────────────────────────────────────

function RecentRuns() {
  const { data: runs, isLoading } = useAgentRuns({ limit: "20" });

  return (
    <div className="card space-y-3">
      <div className="flex items-center gap-2">
        <Clock className="w-4 h-4 text-info" />
        <h2 className="text-sm font-medium text-text-primary">Recent runs</h2>
      </div>

      {isLoading ? (
        <CardSkeleton />
      ) : (
        <div className="space-y-1 max-h-[400px] overflow-y-auto">
          {(runs || []).map((r) => (
            <div key={r.id} className="flex items-center justify-between text-[11px] py-1.5 border-b border-border-secondary last:border-0">
              <div className="flex items-center gap-2">
                {r.status === "success" ? (
                  <CheckCircle className="w-3.5 h-3.5 text-success" />
                ) : r.status === "error" ? (
                  <XCircle className="w-3.5 h-3.5 text-danger" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-info animate-spin" />
                )}
                <span className="text-text-primary">{r.agent_name.replace(/_/g, " ")}</span>
              </div>
              <div className="flex items-center gap-3">
                {r.records_produced != null && (
                  <span className="text-text-secondary">{r.records_produced} records</span>
                )}
                {r.duration_seconds != null && (
                  <span className="text-text-secondary">{r.duration_seconds.toFixed(1)}s</span>
                )}
                <span className="text-text-tertiary">{timeAgo(r.started_at)}</span>
              </div>
            </div>
          ))}
          {(runs || []).length === 0 && <p className="text-[12px] text-text-tertiary text-center py-4">No agent runs yet.</p>}
        </div>
      )}
    </div>
  );
}

// ── Scraper Health ────────────────────────────────────────────

function ScraperHealth() {
  const { data: health } = useHealth();

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-3">
        <RefreshCw className="w-4 h-4 text-success" />
        <h2 className="text-sm font-medium text-text-primary">System health</h2>
        <span className={cn(
          "ml-auto px-2 py-0.5 rounded-md text-[11px] font-medium",
          health?.status === "ok" ? "bg-bg-success text-txt-success" : "bg-bg-danger text-txt-danger"
        )}>
          {health?.status || "checking..."}
        </span>
      </div>
      <p className="text-[12px] text-text-secondary">
        API health check endpoint is {health?.status === "ok" ? "responding normally" : "not responding"}.
        Agent and scraper details are shown above.
      </p>
    </div>
  );
}
