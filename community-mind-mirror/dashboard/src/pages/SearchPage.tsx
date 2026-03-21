import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Search as SearchIcon, TrendingUp, Users, Newspaper, MessageSquare, ExternalLink } from "lucide-react";
import { useSearch } from "../api/hooks";
import { timeAgo, formatNumber } from "../lib/utils";
import Badge from "../components/common/Badge";
import Skeleton from "../components/common/Skeleton";

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get("q") || "";
  const [input, setInput] = useState(initialQuery);
  const [query, setQuery] = useState(initialQuery);

  const { data, isLoading } = useSearch(query);

  useEffect(() => {
    const q = searchParams.get("q") || "";
    setInput(q);
    setQuery(q);
  }, [searchParams]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (input.trim().length >= 2) {
      setQuery(input.trim());
      setSearchParams({ q: input.trim() });
    }
  }

  const totalResults =
    (data?.posts?.length || 0) +
    (data?.news?.length || 0) +
    (data?.topics?.length || 0) +
    (data?.users?.length || 0);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
        <SearchIcon className="w-6 h-6 text-text-secondary" /> Search
      </h1>

      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="flex items-center gap-2 bg-bg-primary border border-border-primary rounded-lg px-3 py-2 flex-1 max-w-lg">
          <SearchIcon className="w-4 h-4 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search across topics, people, news, posts..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="bg-transparent text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none w-full"
          />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-brand text-white text-sm rounded-lg hover:bg-brand-dark transition-colors"
        >
          Search
        </button>
      </form>

      {query && (
        <p className="text-sm text-text-secondary">
          {isLoading ? "Searching..." : `${totalResults} results for "${query}"`}
        </p>
      )}

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="bg-bg-primary border border-border-primary rounded-xl p-4 space-y-2">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      )}

      {data && !isLoading && (
        <div className="space-y-6">
          {/* Topics */}
          {data.topics.length > 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
              <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-purple" /> Topics ({data.topics.length})
              </h2>
              <div className="space-y-2">
                {data.topics.map((t) => (
                  <Link
                    key={t.id}
                    to={`/topics/${t.id}`}
                    className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-bg-secondary"
                  >
                    <span className="text-sm text-text-primary">{t.name}</span>
                    <div className="flex items-center gap-2">
                      {t.status && <Badge label={t.status} />}
                      <span className="text-xs text-text-secondary">{formatNumber(t.total_mentions)} mentions</span>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {/* Users/Personas */}
          {data.users.length > 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
              <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Users className="w-5 h-5 text-purple" /> People ({data.users.length})
              </h2>
              <div className="space-y-2">
                {data.users.map((u) => (
                  <div key={u.id} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-bg-secondary">
                    <span className="text-sm text-text-primary">@{u.username}</span>
                    {u.platform_name && <span className="text-xs text-text-tertiary">{u.platform_name}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* News */}
          {data.news.length > 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
              <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Newspaper className="w-5 h-5 text-warning" /> News ({data.news.length})
              </h2>
              <div className="space-y-2">
                {data.news.map((n) => (
                  <div key={n.id} className="flex items-start justify-between py-2 px-3 rounded-lg hover:bg-bg-secondary">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary">{n.title}</p>
                      <span className="text-xs text-text-tertiary">{n.source_name} - {timeAgo(n.published_at)}</span>
                    </div>
                    {n.url && (
                      <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Posts */}
          {data.posts.length > 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
              <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-success" /> Posts ({data.posts.length})
              </h2>
              <div className="space-y-2">
                {data.posts.map((p) => (
                  <div key={p.id} className="flex items-start justify-between py-2 px-3 rounded-lg hover:bg-bg-secondary">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-primary">{p.title || (p.body || "").slice(0, 100)}</p>
                      <div className="flex items-center gap-2 mt-1">
                        {p.username && <span className="text-xs text-info">@{p.username}</span>}
                        {p.platform_name && <span className="text-xs text-text-tertiary">{p.platform_name}</span>}
                        <span className="text-xs text-text-tertiary">{timeAgo(p.posted_at)}</span>
                      </div>
                    </div>
                    {p.url && (
                      <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {totalResults === 0 && (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-8 text-center">
              <SearchIcon className="w-12 h-12 text-text-tertiary mx-auto mb-3" />
              <p className="text-sm text-text-secondary">No results found for "{query}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
