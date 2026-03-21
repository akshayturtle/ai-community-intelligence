import { Globe } from "lucide-react";
import { useGeo } from "../api/hooks";
import Skeleton from "../components/common/Skeleton";

export default function Geo() {
  const { data: geoData, isLoading } = useGeo();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-text-primary flex items-center gap-2">
        <Globe className="w-6 h-6 text-cyan-400" /> Geographic Distribution
      </h1>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-bg-primary border border-border-primary rounded-xl p-4 space-y-3">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      ) : (
        <>
          {(!geoData || geoData.length === 0) ? (
            <div className="bg-bg-primary border border-border-primary rounded-xl p-8 text-center">
              <Globe className="w-12 h-12 text-text-tertiary mx-auto mb-3" />
              <p className="text-sm text-text-secondary">No geographic data available yet.</p>
              <p className="text-xs text-text-tertiary mt-1">Locations are inferred from persona analysis.</p>
            </div>
          ) : (
            <>
              {/* Summary stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
                  <span className="text-xs text-text-secondary uppercase">Locations</span>
                  <p className="text-xl font-bold text-cyan-400 mt-1">{geoData.length}</p>
                </div>
                <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
                  <span className="text-xs text-text-secondary uppercase">Total Personas</span>
                  <p className="text-xl font-bold text-success mt-1">
                    {geoData.reduce((acc, g) => acc + g.user_count, 0)}
                  </p>
                </div>
                <div className="bg-bg-primary border border-border-primary rounded-xl p-4">
                  <span className="text-xs text-text-secondary uppercase">Avg Influence</span>
                  <p className="text-xl font-bold text-info mt-1">
                    {(geoData.reduce((acc, g) => acc + g.avg_influence, 0) / geoData.length * 100).toFixed(0)}%
                  </p>
                </div>
              </div>

              {/* Location cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {geoData.map((g) => (
                  <div key={g.location} className="bg-bg-primary border border-border-primary rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-text-primary">{g.location}</h3>
                      <span className="text-xs font-mono text-info">{(g.avg_influence * 100).toFixed(0)}%</span>
                    </div>
                    <p className="text-xs text-text-secondary">{g.user_count} persona{g.user_count !== 1 ? "s" : ""}</p>
                    {g.top_topics.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-3">
                        {g.top_topics.slice(0, 5).map((t) => (
                          <span key={t} className="px-1.5 py-0.5 bg-bg-tertiary rounded text-[10px] text-text-secondary">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
