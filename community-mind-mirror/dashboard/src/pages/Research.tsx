import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Play, Loader2, CheckCircle, XCircle, Clock, Trash2 } from "lucide-react";
import { useResearchProjects, useCreateResearch, useRunResearch, useDeleteResearch } from "../api/hooks";
import { formatNumber, cn } from "../lib/utils";
import { CardSkeleton } from "../components/common/Skeleton";

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  draft: { bg: "bg-bg-secondary", text: "text-text-secondary", label: "Draft" },
  expanding: { bg: "bg-bg-info", text: "text-txt-info", label: "Expanding keywords..." },
  scraping: { bg: "bg-bg-info", text: "text-txt-info", label: "Scraping Reddit..." },
  processing: { bg: "bg-bg-warning", text: "text-txt-warning", label: "Analyzing..." },
  complete: { bg: "bg-bg-success", text: "text-txt-success", label: "Complete" },
  failed: { bg: "bg-bg-danger", text: "text-txt-danger", label: "Failed" },
};

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.draft;
  const isRunning = ["expanding", "scraping", "processing"].includes(status);
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium", s.bg, s.text)}>
      {isRunning && <Loader2 className="w-3 h-3 animate-spin" />}
      {status === "complete" && <CheckCircle className="w-3 h-3" />}
      {status === "failed" && <XCircle className="w-3 h-3" />}
      {s.label}
    </span>
  );
}

export default function Research() {
  const { data, isLoading } = useResearchProjects();
  const createMutation = useCreateResearch();
  const runMutation = useRunResearch();
  const deleteMutation = useDeleteResearch();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [terms, setTerms] = useState("");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !terms.trim()) return;

    const termList = terms.split(",").map((t) => t.trim()).filter(Boolean);
    await createMutation.mutateAsync({ name: name.trim(), description: description.trim() || undefined, initial_terms: termList });
    setName("");
    setDescription("");
    setTerms("");
    setShowForm(false);
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-medium text-text-primary">Market Research</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      </div>
    );
  }

  const projects = data?.items || [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-text-primary">Market Research</h1>
          <p className="text-[12px] text-text-secondary">Research any concept — get insights, product analysis, and contact lists from Reddit</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm bg-info text-white hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" />
          New Research
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <form onSubmit={handleCreate} className="card space-y-3">
          <h2 className="text-sm font-medium text-text-primary">Create research project</h2>
          <div>
            <label className="text-[12px] text-text-secondary block mb-1">Project Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., AI Design Tools"
              className="w-full px-3 py-1.5 text-sm bg-bg-secondary border border-border-primary rounded-lg text-text-primary placeholder:text-text-tertiary"
              required
            />
          </div>
          <div>
            <label className="text-[12px] text-text-secondary block mb-1">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What are you researching?"
              className="w-full px-3 py-1.5 text-sm bg-bg-secondary border border-border-primary rounded-lg text-text-primary placeholder:text-text-tertiary"
            />
          </div>
          <div>
            <label className="text-[12px] text-text-secondary block mb-1">Search Terms (comma-separated)</label>
            <input
              type="text"
              value={terms}
              onChange={(e) => setTerms(e.target.value)}
              placeholder="e.g., AI design tool, generative design, AI graphic design"
              className="w-full px-3 py-1.5 text-sm bg-bg-secondary border border-border-primary rounded-lg text-text-primary placeholder:text-text-tertiary"
              required
            />
            <p className="text-[11px] text-text-tertiary mt-1">Enter 2-5 seed terms. The system will expand them into 15-20 keywords automatically.</p>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-4 py-1.5 rounded-lg text-sm bg-info text-white hover:opacity-90 disabled:opacity-50"
            >
              {createMutation.isPending ? "Creating..." : "Create Project"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-1.5 rounded-lg text-sm bg-bg-secondary text-text-secondary hover:text-text-primary"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Project Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {projects.map((p) => {
          const isRunning = ["expanding", "scraping", "processing"].includes(p.status);
          return (
            <div key={p.id} className="card">
              <div className="flex items-start justify-between mb-2">
                <Link to={`/research/${p.id}`} className="text-sm font-medium text-text-primary hover:text-info transition-colors">
                  {p.name}
                </Link>
                <StatusBadge status={p.status} />
              </div>

              {p.description && (
                <p className="text-[12px] text-text-secondary mb-2 line-clamp-2">{p.description}</p>
              )}

              {p.initial_terms && (
                <div className="flex flex-wrap gap-1 mb-2">
                  {p.initial_terms.slice(0, 4).map((t, i) => (
                    <span key={i} className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-bg-secondary text-text-secondary">{t}</span>
                  ))}
                  {p.initial_terms.length > 4 && (
                    <span className="text-[10px] text-text-tertiary">+{p.initial_terms.length - 4}</span>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between text-[11px] text-text-tertiary">
                <div className="flex items-center gap-3">
                  <span>{formatNumber(p.post_count)} posts</span>
                  {p.created_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(p.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {(p.status === "draft" || p.status === "complete" || p.status === "failed") && (
                    <button
                      onClick={() => runMutation.mutate(p.id)}
                      disabled={runMutation.isPending}
                      className="p-1 rounded hover:bg-bg-secondary text-text-tertiary hover:text-info transition-colors"
                      title={p.status === "complete" ? "Re-run research" : "Run research"}
                    >
                      <Play className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {!isRunning && (
                    <button
                      onClick={() => { if (confirm("Delete this research project?")) deleteMutation.mutate(p.id); }}
                      disabled={deleteMutation.isPending}
                      className="p-1 rounded hover:bg-bg-secondary text-text-tertiary hover:text-danger transition-colors"
                      title="Delete"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {p.error_message && (
                <p className="text-[11px] text-danger mt-1 line-clamp-2">{p.error_message}</p>
              )}
            </div>
          );
        })}
      </div>

      {projects.length === 0 && !showForm && (
        <div className="text-center py-12">
          <p className="text-sm text-text-tertiary mb-3">No research projects yet</p>
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 rounded-lg text-sm bg-info text-white hover:opacity-90"
          >
            Create your first research project
          </button>
        </div>
      )}
    </div>
  );
}
