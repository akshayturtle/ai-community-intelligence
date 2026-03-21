import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Activity } from "lucide-react";
import { useHealth } from "../api/hooks";

export default function TopBar() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();
  const { data: health } = useHealth();
  const isHealthy = health?.status === "ok";

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim().length >= 2) {
      navigate(`/search?q=${encodeURIComponent(query.trim())}`);
    }
  }

  return (
    <header className="h-14 bg-bg-primary border-b border-border-primary flex items-center justify-between px-6 sticky top-0 z-30">
      <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 max-w-md">
        <Search className="w-4 h-4 text-text-tertiary" />
        <input
          type="text"
          placeholder="Search topics, people, news..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="bg-bg-secondary border border-border-primary rounded-lg px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary w-full focus:outline-none focus:border-info"
        />
      </form>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs">
          <Activity className={`w-3.5 h-3.5 ${isHealthy ? "text-success" : "text-danger"}`} />
          <span className={isHealthy ? "text-success" : "text-danger"}>
            {isHealthy ? "API Online" : "API Offline"}
          </span>
        </div>
      </div>
    </header>
  );
}
