import { useState } from "react";
import { Newspaper, ExternalLink, Search } from "lucide-react";
import { useNews, useResearch, useFunding, useJobs } from "../api/hooks";
import { timeAgo } from "../lib/utils";
import Badge from "../components/common/Badge";
import Pagination from "../components/common/Pagination";
import Skeleton from "../components/common/Skeleton";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

const tabs = [
  { id: "all", label: "All News" },
  { id: "arxiv", label: "ArXiv" },
  { id: "funding", label: "Funding" },
  { id: "jobs", label: "Jobs" },
];

export default function News() {
  const [activeTab, setActiveTab] = useState("all");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const params: Record<string, string> = { page: String(page), per_page: "20" };
  if (search) params.search = search;
  if (activeTab === "arxiv") params.source_type = "arxiv";

  const { data: newsData, isLoading: loadingNews } = useNews(activeTab === "all" || activeTab === "arxiv" ? params : undefined);
  useResearch();
  const { data: funding } = useFunding();
  const { data: jobs } = useJobs();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
        <Newspaper className="w-6 h-6 text-warning" /> News & Intelligence
      </h1>

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-primary border border-border-primary rounded-lg p-1 w-fit">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setPage(1); }}
            className={`px-4 py-1.5 rounded-md text-sm transition-colors ${
              activeTab === t.id
                ? "bg-brand text-white"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* All / ArXiv tab */}
      {(activeTab === "all" || activeTab === "arxiv") && (
        <>
          <div className="flex items-center gap-2 bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5 w-fit">
            <Search className="w-4 h-4 text-text-tertiary" />
            <input
              type="text"
              placeholder="Search news..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none w-64"
            />
          </div>

          <div className="space-y-3">
            {loadingNews
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="bg-bg-primary border border-border-primary rounded-xl p-4 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))
              : (newsData?.items || []).map((n) => (
                  <div key={n.id} className="bg-bg-primary border border-border-primary rounded-xl p-4 hover:border-border-primary transition-colors">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-text-primary">{n.title}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-text-tertiary">{n.source_name || n.source_type}</span>
                          <span className="text-xs text-text-tertiary">{timeAgo(n.published_at)}</span>
                          {n.magnitude && <Badge label={n.magnitude} />}
                          {n.sentiment != null && (
                            <span className={`text-xs ${n.sentiment > 0.05 ? "text-success" : n.sentiment < -0.05 ? "text-danger" : "text-text-secondary"}`}>
                              {n.sentiment > 0 ? "+" : ""}{n.sentiment.toFixed(2)}
                            </span>
                          )}
                        </div>
                        {n.entities && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {((n.entities as any).companies || []).slice(0, 3).map((c: string) => (
                              <span key={c} className="px-1.5 py-0.5 bg-bg-info text-info text-[10px] rounded">{c}</span>
                            ))}
                            {((n.entities as any).technologies || []).slice(0, 3).map((t: string) => (
                              <span key={t} className="px-1.5 py-0.5 bg-purple/10 text-purple text-[10px] rounded">{t}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      {n.url && (
                        <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
          </div>

          <Pagination page={page} totalPages={Math.ceil((newsData?.total || 0) / 20)} onPageChange={setPage} />
        </>
      )}

      {/* Funding tab */}
      {activeTab === "funding" && (
        <div className="space-y-3">
          {(funding || []).length === 0 && <p className="text-sm text-text-tertiary">No funding signals found</p>}
          {(funding || []).map((f) => (
            <div key={f.id} className="bg-bg-primary border border-border-primary rounded-xl p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text-primary">{f.title}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs text-text-tertiary">{f.source_name}</span>
                    <span className="text-xs text-text-tertiary">{timeAgo(f.published_at)}</span>
                    {f.magnitude && <Badge label={f.magnitude} />}
                  </div>
                </div>
                {f.url && (
                  <a href={f.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Jobs tab */}
      {activeTab === "jobs" && (
        <div className="space-y-6">
          {jobs?.weekly_counts && jobs.weekly_counts.length > 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-5">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Weekly Job Postings</h2>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={jobs.weekly_counts}>
                  <XAxis dataKey="week" tick={{ fill: "#94a3b8", fontSize: 11 }} tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#e2e8f0" }}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="space-y-3">
            {(jobs?.recent_listings || []).map((j, idx) => (
              <div key={String(j.id ?? idx)} className="bg-bg-primary border border-border-primary rounded-xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-text-primary">{String(j.title || "")}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-text-tertiary">{String(j.source_name || "")}</span>
                      <span className="text-xs text-text-tertiary">{timeAgo(j.published_at as string | null)}</span>
                    </div>
                  </div>
                  {j.url ? (
                    <a href={String(j.url)} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
