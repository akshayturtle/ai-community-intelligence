import { useState } from "react";
import { Link } from "react-router-dom";
import { Users, Search } from "lucide-react";
import { usePersonas } from "../api/hooks";
import { truncate } from "../lib/utils";
import Badge from "../components/common/Badge";
import Pagination from "../components/common/Pagination";
import Skeleton from "../components/common/Skeleton";

export default function People() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState("");

  const params: Record<string, string> = { page: String(page), per_page: "20" };
  if (search) params.search = search;
  if (platform) params.platform = platform;

  const { data, isLoading } = usePersonas(params);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
          <Users className="w-6 h-6 text-purple" /> People
        </h1>
        <span className="text-sm text-text-secondary">{data?.total || 0} personas</span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2 bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5">
          <Search className="w-4 h-4 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search personas..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none w-48"
          />
        </div>
        <select
          value={platform}
          onChange={(e) => { setPlatform(e.target.value); setPage(1); }}
          className="bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-info"
        >
          <option value="">All Platforms</option>
          <option value="reddit">Reddit</option>
          <option value="hackernews">Hacker News</option>
          <option value="youtube">YouTube</option>
        </select>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading
          ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="bg-bg-primary border border-border-primary rounded-xl p-4 space-y-3">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ))
          : (data?.items || []).map((p) => (
              <Link
                key={p.id}
                to={`/people/${p.id}`}
                className="bg-bg-primary border border-border-primary rounded-xl p-4 hover:border-info/50 transition-colors block"
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="text-sm font-semibold text-text-primary">{p.username || `User #${p.user_id}`}</span>
                    {p.platform_name && (
                      <span className="text-xs text-text-tertiary ml-2">{p.platform_name}</span>
                    )}
                  </div>
                  <span className="text-xs font-mono text-info">
                    {p.influence_score != null ? (p.influence_score * 100).toFixed(0) + "%" : "N/A"}
                  </span>
                </div>
                {p.inferred_role && <Badge label={p.inferred_role} className="mb-2" />}
                {p.personality_summary && (
                  <p className="text-xs text-text-secondary line-clamp-2">{truncate(p.personality_summary, 120)}</p>
                )}
                <div className="flex flex-wrap gap-1 mt-3">
                  {(p.active_topics || []).slice(0, 3).map((t) => (
                    <span key={t} className="px-1.5 py-0.5 bg-bg-tertiary rounded text-[10px] text-text-secondary">
                      {t}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-3 mt-3 text-xs text-text-tertiary">
                  {p.inferred_location && <span>{p.inferred_location}</span>}
                </div>
              </Link>
            ))}
      </div>

      <Pagination
        page={page}
        totalPages={Math.ceil((data?.total || 0) / 20)}
        onPageChange={setPage}
      />
    </div>
  );
}
