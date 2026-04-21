import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play, RefreshCw, CheckCircle2, XCircle, Clock, Loader2,
  Circle, ChevronDown, ChevronUp, Terminal, Zap,
} from "lucide-react";
import { cn } from "../lib/utils";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
const WS_URL = (() => {
  const base = import.meta.env.VITE_WS_URL || "ws://localhost:8000/api/ws/dashboard";
  return base;
})();

// ── Types ────────────────────────────────────────────────────────────────────
type StepStatus = "pending" | "running" | "ok" | "error" | "timeout";

interface StepInfo {
  type: "scraper" | "processor" | "agent";
  status: StepStatus;
  fetched?: number;
  new?: number;
  records?: number;
  result?: string;
  duration_s?: number | null;
  error?: string | null;
}

interface PipelineState {
  running: boolean;
  phase: "idle" | "scrapers" | "processors" | "agents" | "done";
  current_steps: string[];   // parallel scrapers → multiple active at once
  started_at: string | null;
  finished_at: string | null;
  steps: Record<string, StepInfo>;
  log: string[];
  scrapers: string[];
  processors: string[];
  agents: string[];
}

// ── API helpers ──────────────────────────────────────────────────────────────
async function fetchState(): Promise<PipelineState> {
  const r = await fetch(`${BASE}/pipeline/state`);
  if (!r.ok) throw new Error("Failed to fetch pipeline state");
  return r.json();
}

async function triggerPipeline(): Promise<{ status: string }> {
  const r = await fetch(`${BASE}/pipeline/trigger`, { method: "POST" });
  if (!r.ok) throw new Error("Failed to trigger pipeline");
  return r.json();
}

// ── Status badge ─────────────────────────────────────────────────────────────
function StepBadge({ name, info }: { name: string; info: StepInfo }) {
  const [expanded, setExpanded] = useState(false);
  const active = info.status === "running";

  const icon = () => {
    if (active)
      return <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-400 shrink-0" />;
    if (info.status === "ok")
      return <CheckCircle2 className="w-3.5 h-3.5 text-green-400 shrink-0" />;
    if (info.status === "error")
      return <XCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />;
    if (info.status === "timeout")
      return <Clock className="w-3.5 h-3.5 text-amber-400 shrink-0" />;
    return <Circle className="w-3.5 h-3.5 text-zinc-600 shrink-0" />;
  };

  const rowBg = active
    ? "bg-blue-500/10 border-blue-500/30"
    : info.status === "ok"
    ? "bg-green-500/5 border-green-500/10"
    : info.status === "error"
    ? "bg-red-500/8 border-red-500/15"
    : info.status === "timeout"
    ? "bg-amber-500/8 border-amber-500/15"
    : "border-transparent";

  const meta = () => {
    if (info.status === "pending") return null;
    if (info.type === "scraper" && info.status === "ok")
      return (
        <span className="text-xs text-zinc-500">
          {info.fetched ?? 0} fetched · <span className="text-green-400">+{info.new ?? 0}</span>
        </span>
      );
    if ((info.type === "processor" || info.type === "agent") && info.status === "ok")
      return (
        <span className="text-xs text-zinc-500 truncate max-w-[120px]">
          {info.result ?? (info.records != null ? `${info.records} records` : "")}
        </span>
      );
    if (info.status === "timeout")
      return <span className="text-xs text-amber-500/80">{info.duration_s}s</span>;
    return null;
  };

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-sm cursor-default",
        rowBg
      )}
      onClick={() => info.error && setExpanded((v) => !v)}
    >
      {icon()}
      <span className={cn(
        "flex-1 font-mono text-xs truncate",
        active ? "text-blue-300" : info.status === "ok" ? "text-zinc-200" : "text-zinc-400"
      )}>
        {name}
      </span>
      {meta()}
      {info.error && (
        <button className="text-zinc-500 hover:text-zinc-300 ml-1">
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      )}
    </div>
  );
}

// ── Phase column ─────────────────────────────────────────────────────────────
function PhaseColumn({
  title, steps, stepsInfo, phaseActive,
}: {
  title: string;
  steps: string[];
  stepsInfo: Record<string, StepInfo>;
  phaseActive: boolean;
}) {
  const running = steps.filter((s) => stepsInfo[s]?.status === "running").length;
  const done    = steps.filter((s) => stepsInfo[s]?.status === "ok").length;
  const errors  = steps.filter((s) => ["error", "timeout"].includes(stepsInfo[s]?.status ?? "")).length;
  const total   = steps.length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between mb-1">
        <h3 className={cn(
          "text-xs font-semibold uppercase tracking-wider",
          phaseActive ? "text-blue-400" : "text-zinc-500"
        )}>
          {title}
        </h3>
        <div className="flex items-center gap-2 text-xs text-zinc-600">
          {running > 0 && (
            <span className="text-blue-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
              {running} running
            </span>
          )}
          <span>{done}/{total}</span>
          {errors > 0 && <span className="text-red-400">{errors} err</span>}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden mb-2">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500",
            errors > 0 ? "bg-amber-500" : "bg-blue-500"
          )}
          style={{ width: `${total > 0 ? (done / total) * 100 : 0}%` }}
        />
      </div>

      <div className="space-y-1 max-h-[520px] overflow-y-auto pr-1 scrollbar-thin">
        {steps.map((name) => (
          <StepBadge
            key={name}
            name={name}
            info={stepsInfo[name] ?? { type: "scraper", status: "pending" }}
          />
        ))}
      </div>
    </div>
  );
}

// ── Log terminal ─────────────────────────────────────────────────────────────
function LogTerminal({ lines, running }: { lines: string[]; running: boolean }) {
  const [open, setOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines, open]);

  const colorLine = (line: string) => {
    if (/OK\s+[—\-]|: OK/.test(line)) return "text-green-400";
    if (/ERROR|Traceback/.test(line)) return "text-red-400";
    if (/TIMEOUT/.test(line)) return "text-amber-400";
    if (/Scraper:|Processor:|Agent:/.test(line)) return "text-blue-300 font-semibold";
    if (/Phase\s+[123]|===/.test(line)) return "text-zinc-300 font-bold";
    if (/Budget|OVER/.test(line)) return "text-orange-400";
    return "text-zinc-400";
  };

  return (
    <div className="rounded-xl border border-border-primary overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 bg-bg-secondary hover:bg-zinc-800/60 transition-colors"
      >
        <Terminal className="w-4 h-4 text-zinc-500" />
        <span className="text-sm font-medium text-zinc-300 flex-1 text-left">Live Log</span>
        {running && (
          <span className="flex items-center gap-1 text-xs text-blue-400">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            streaming
          </span>
        )}
        <span className="text-xs text-zinc-600">{lines.length} lines</span>
        {open ? <ChevronUp className="w-4 h-4 text-zinc-600" /> : <ChevronDown className="w-4 h-4 text-zinc-600" />}
      </button>

      {open && (
        <div className="bg-zinc-950 px-4 py-3 h-64 overflow-y-auto font-mono text-xs leading-5">
          {lines.length === 0 ? (
            <span className="text-zinc-600 italic">No log output yet. Trigger a run to see live output.</span>
          ) : (
            lines.map((line, i) => (
              <div key={i} className={cn("whitespace-pre-wrap break-all", colorLine(line))}>
                {line || "\u00A0"}
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Scrapers() {
  const qc = useQueryClient();
  const [liveLog, setLiveLog] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const { data: pipelineState, isLoading } = useQuery<PipelineState>({
    queryKey: ["pipeline-state"],
    queryFn: fetchState,
    refetchInterval: (query) => {
      const data = query.state.data as PipelineState | undefined;
      return data?.running ? 1500 : 10000;
    },
  });

  const trigger = useMutation({
    mutationFn: triggerPipeline,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipeline-state"] });
    },
  });

  // WebSocket: subscribe to pipeline events for instant log streaming
  useEffect(() => {
    let ws: WebSocket;
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect() {
      try {
        ws = new WebSocket(WS_URL);

        ws.onmessage = (evt) => {
          try {
            const msg = JSON.parse(evt.data);
            if (msg.type === "log_line") {
              setLiveLog((prev) => {
                const next = [...prev, msg.data.line];
                return next.slice(-300); // keep last 300 lines
              });
            } else if (
              msg.type === "pipeline_started" ||
              msg.type === "pipeline_finished" ||
              msg.type === "step_update"
            ) {
              qc.invalidateQueries({ queryKey: ["pipeline-state"] });
            }
          } catch { /* ignore */ }
        };

        ws.onclose = () => {
          retryTimer = setTimeout(connect, 5000);
        };
        ws.onerror = () => ws.close();
        wsRef.current = ws;
      } catch {
        retryTimer = setTimeout(connect, 5000);
      }
    }

    connect();
    return () => {
      clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [qc]);

  // Sync server log to liveLog when not running (historical)
  const serverLog = pipelineState?.log ?? [];
  const displayLog = liveLog.length > 0 ? liveLog : serverLog;

  const running = pipelineState?.running ?? false;
  const phase = pipelineState?.phase ?? "idle";
  const steps = pipelineState?.steps ?? {};
  const currentSteps = pipelineState?.current_steps ?? [];

  const scrapers = pipelineState?.scrapers ?? [];
  const processors = pipelineState?.processors ?? [];
  const agents = pipelineState?.agents ?? [];

  const allSteps = [...scrapers, ...processors, ...agents];
  const doneCount = allSteps.filter((s) => steps[s]?.status === "ok").length;
  const errorCount = allSteps.filter(
    (s) => steps[s]?.status === "error" || steps[s]?.status === "timeout"
  ).length;
  const totalSteps = allSteps.length;
  const progressPct = totalSteps > 0 ? (doneCount / totalSteps) * 100 : 0;

  const phaseLabelMap: Record<string, string> = {
    idle: "Idle",
    scrapers: "Running scrapers…",
    processors: "Running processors…",
    agents: "Running signal agents…",
    done: "Completed",
  };

  const startedAt = pipelineState?.started_at
    ? new Date(pipelineState.started_at).toLocaleString()
    : null;
  const finishedAt = pipelineState?.finished_at
    ? new Date(pipelineState.finished_at).toLocaleString()
    : null;

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text-primary flex items-center gap-2">
            <Zap className="w-5 h-5 text-blue-400" />
            Scraper Pipeline
          </h1>
          <p className="text-sm text-text-secondary mt-0.5">
            25 scrapers · 14 processors · 11 signal agents · runs every 24 h
          </p>
        </div>

        <button
          onClick={() => trigger.mutate()}
          disabled={running || trigger.isPending}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            running || trigger.isPending
              ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700 text-white"
          )}
        >
          {running ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Running…
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Run Now
            </>
          )}
        </button>
      </div>

      {/* Status bar */}
      <div className="rounded-xl border border-border-primary bg-bg-secondary p-4 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className={cn(
                "w-2.5 h-2.5 rounded-full shrink-0",
                running ? "bg-blue-400 animate-pulse" : phase === "done" ? "bg-green-400" : "bg-zinc-600"
              )}
            />
            <span className="text-sm font-medium text-text-primary">
              {phaseLabelMap[phase] ?? phase}
            </span>
            {currentSteps.map((s) => (
              <span key={s} className="text-xs bg-blue-500/15 text-blue-300 px-2 py-0.5 rounded-full">
                {s}
              </span>
            ))}
          </div>
          <div className="text-xs text-zinc-500 space-x-3">
            {startedAt && <span>Started {startedAt}</span>}
            {finishedAt && !running && <span>· Finished {finishedAt}</span>}
          </div>
        </div>

        {/* Overall progress */}
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-zinc-500">
            <span>{doneCount} / {totalSteps} steps complete</span>
            {errorCount > 0 && <span className="text-red-400">{errorCount} errors</span>}
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={cn(
                "h-full rounded-full transition-all duration-700",
                errorCount > 0 ? "bg-amber-500" : "bg-blue-500"
              )}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* 3-column step grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-40 text-zinc-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading…
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <PhaseColumn
            title="Scrapers"
            steps={scrapers}
            stepsInfo={steps}
            phaseActive={phase === "scrapers"}
          />
          <PhaseColumn
            title="Processors"
            steps={processors}
            stepsInfo={steps}
            phaseActive={phase === "processors"}
          />
          <PhaseColumn
            title="Signal Agents"
            steps={agents}
            stepsInfo={steps}
            phaseActive={phase === "agents"}
          />
        </div>
      )}

      {/* Log terminal */}
      <LogTerminal lines={displayLog} running={running} />
    </div>
  );
}
