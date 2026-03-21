import { useState } from "react";
import { Link } from "react-router-dom";
import { TrendingUp, Search } from "lucide-react";
import { useTopics } from "../api/hooks";
import { formatNumber, timeAgo } from "../lib/utils";
import Badge from "../components/common/Badge";
import Pagination from "../components/common/Pagination";
import Skeleton from "../components/common/Skeleton";

export default function Topics() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("velocity");

  const params: Record<string, string> = { page: String(page), per_page: "20", sort_by: sortBy };
  if (status) params.status = status;
  if (search) params.search = search;

  const { data, isLoading } = useTopics(params);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
          <TrendingUp className="w-6 h-6 text-purple" /> Topics
        </h1>
        <span className="text-sm text-text-secondary">{data?.total || 0} total</span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2 bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5">
          <Search className="w-4 h-4 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search topics..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none w-48"
          />
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1); }}
          className="bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-info"
        >
          <option value="">All Statuses</option>
          <option value="emerging">Emerging</option>
          <option value="active">Active</option>
          <option value="peaking">Peaking</option>
          <option value="declining">Declining</option>
        </select>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
          className="bg-bg-primary border border-border-primary rounded-lg px-3 py-1.5 text-sm text-text-primary focus:outline-none focus:border-info"
        >
          <option value="velocity">Sort by Velocity</option>
          <option value="total_mentions">Sort by Mentions</option>
          <option value="last_seen_at">Sort by Last Seen</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-bg-primary border border-border-primary rounded-xl overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-border-primary">
              <th className="px-4 py-3 text-xs text-text-secondary font-medium uppercase">Topic</th>
              <th className="px-4 py-3 text-xs text-text-secondary font-medium uppercase">Status</th>
              <th className="px-4 py-3 text-xs text-text-secondary font-medium uppercase text-right">Velocity</th>
              <th className="px-4 py-3 text-xs text-text-secondary font-medium uppercase text-right">Mentions</th>
              <th className="px-4 py-3 text-xs text-text-secondary font-medium uppercase text-right">Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-border-primary">
                    <td className="px-4 py-3"><Skeleton className="h-4 w-40" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-16" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-10 ml-auto" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-10 ml-auto" /></td>
                    <td className="px-4 py-3"><Skeleton className="h-4 w-16 ml-auto" /></td>
                  </tr>
                ))
              : (data?.items || []).map((t) => (
                  <tr key={t.id} className="border-b border-border-primary hover:bg-bg-secondary transition-colors">
                    <td className="px-4 py-3">
                      <Link to={`/topics/${t.id}`} className="text-sm text-text-primary hover:text-info">
                        {t.name}
                      </Link>
                      {t.description && (
                        <p className="text-xs text-text-tertiary mt-0.5 truncate max-w-xs">{t.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">{t.status && <Badge label={t.status} />}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-sm font-mono text-warning">{(t.velocity || 0).toFixed(1)}</span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-text-primary">{formatNumber(t.total_mentions)}</td>
                    <td className="px-4 py-3 text-right text-xs text-text-tertiary">{timeAgo(t.last_seen_at)}</td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <Pagination
        page={page}
        totalPages={Math.ceil((data?.total || 0) / 20)}
        onPageChange={setPage}
      />
    </div>
  );
}
