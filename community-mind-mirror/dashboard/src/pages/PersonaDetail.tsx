import { useParams, Link } from "react-router-dom";
import { usePersona, usePersonaPosts } from "../api/hooks";
import { formatNumber, timeAgo, cn, initials } from "../lib/utils";
import Badge from "../components/common/Badge";
import { CardSkeleton } from "../components/common/Skeleton";

const styleColors: Record<string, string> = {
  "1": "#378ADD",
  "2": "#BA7517",
  "3": "#1D9E75",
  "4": "#534AB7",
};

function getConvictionStyle(score: number): { bg: string; text: string; label: string } {
  if (score >= 0.8) return { bg: "bg-bg-success", text: "text-txt-success", label: "Strong conviction" };
  if (score >= 0.6) return { bg: "bg-bg-success", text: "text-txt-success", label: "High conviction" };
  if (score >= 0.4) return { bg: "bg-bg-warning", text: "text-txt-warning", label: "Moderate" };
  return { bg: "bg-bg-danger", text: "text-txt-danger", label: "Bearish" };
}

function getConvictionColor(score: number): string {
  if (score >= 0.6) return "#1D9E75";
  if (score >= 0.4) return "#BA7517";
  return "#E24B4A";
}

export default function PersonaDetail() {
  const { id } = useParams<{ id: string }>();
  const personaId = Number(id);
  const { data: persona, isLoading } = usePersona(personaId);
  const { data: posts } = usePersonaPosts(personaId, { per_page: "10" });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (!persona) return <p className="text-text-secondary">Persona not found</p>;

  const username = persona.username || `User #${persona.user_id}`;

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px]">
        <Link to="/" className="text-text-secondary hover:text-text-primary">Dashboard</Link>
        <span className="text-text-secondary">/</span>
        <Link to="/people" className="text-text-secondary hover:text-text-primary">People</Link>
        <span className="text-text-secondary">/</span>
        <span className="text-text-primary">{username}</span>
      </div>

      {/* Profile Card */}
      <div className="card">
        <div className="flex items-start gap-4 flex-wrap">
          {/* Avatar */}
          <div className="w-14 h-14 rounded-full bg-bg-info flex items-center justify-center text-lg font-medium text-txt-info shrink-0">
            {initials(username)}
          </div>

          {/* Name + Meta */}
          <div className="flex-1 min-w-[200px]">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-lg font-medium text-text-primary">{username}</span>
              {persona.inferred_role && <Badge label={persona.inferred_role} variant="opinion leader" />}
              {persona.platform_name && <Badge label={persona.platform_name} variant="active" />}
            </div>
            <div className="flex items-center gap-4 flex-wrap text-[12px] text-text-secondary">
              {persona.inferred_role && <span>{persona.inferred_role}</span>}
              {persona.inferred_location && <span>{persona.inferred_location}</span>}
              <span>Active since {persona.first_seen ? new Date(persona.first_seen).getFullYear() : "—"}</span>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-lg font-medium text-text-primary">{formatNumber(persona.karma || 0)}</div>
              <div className="text-[12px] text-text-secondary">Karma</div>
            </div>
            <div>
              <div className="text-lg font-medium text-text-primary">
                {persona.influence_score != null ? persona.influence_score.toFixed(2) : "—"}
              </div>
              <div className="text-[12px] text-text-secondary">Influence</div>
            </div>
            <div>
              <div className="text-lg font-medium text-text-primary">{formatNumber(persona.post_count || 0)}</div>
              <div className="text-[12px] text-text-secondary">Posts tracked</div>
            </div>
          </div>
        </div>
      </div>

      {/* Personality Summary — blockquote style */}
      {persona.personality_summary && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-2">Personality summary</h2>
          <div className="text-[13px] leading-relaxed text-text-secondary border-l-2 border-border-secondary pl-3">
            {persona.personality_summary}
          </div>
        </div>
      )}

      {/* Core Beliefs + Communication Style — 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Core Beliefs with conviction bars */}
        {persona.core_beliefs && persona.core_beliefs.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Core beliefs</h2>
            <div className="space-y-1.5">
              {persona.core_beliefs.map((b: any, i: number) => {
                const belief = typeof b === "object" ? b : { topic: String(b), stance: "", confidence: 0.5 };
                const score = belief.confidence ?? belief.conviction ?? belief.score ?? 0.5;
                const label = belief.topic
                  ? `${belief.topic}${belief.stance ? ` — ${belief.stance}` : ""}`
                  : belief.text || belief.name || String(b);
                const style = getConvictionStyle(score);
                return (
                  <div key={i} className="border border-border-primary rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] font-medium text-text-primary">{label}</span>
                      <span className={cn("inline-block px-2 py-0.5 rounded-md text-[11px] font-medium", style.bg, style.text)}>{style.label}</span>
                    </div>
                    <div className="h-1 rounded-sm bg-bg-secondary">
                      <div className="h-full rounded-sm" style={{ width: `${score * 100}%`, background: getConvictionColor(score) }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Communication Style */}
        {persona.communication_style && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Communication style</h2>
            <div className="space-y-2.5">
              {Object.entries(persona.communication_style as Record<string, number>).map(([trait, level], i) => {
                const labels = ["Low", "Moderate", "High", "Very High"];
                const numLevel = typeof level === "number" ? Math.min(Math.max(Math.round(level * 4), 1), 4) : 2;
                const color = Object.values(styleColors)[i % 4];
                return (
                  <div key={trait}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] text-text-primary capitalize">{trait}</span>
                      <span className="text-[12px] font-medium text-text-primary">{labels[numLevel - 1]}</span>
                    </div>
                    <div className="flex gap-0.5">
                      {[1, 2, 3, 4].map((seg) => (
                        <div
                          key={seg}
                          className="flex-1 h-1.5 rounded-sm"
                          style={{ background: seg <= numLevel ? color : "var(--mm-bg-secondary)" }}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}

              {/* Emotional Triggers */}
              {persona.emotional_triggers && persona.emotional_triggers.length > 0 && (
                <div className="mt-1">
                  <div className="text-[12px] text-text-secondary mb-1">Emotional triggers</div>
                  <div className="flex flex-wrap gap-1">
                    {persona.emotional_triggers.map((trigger: any, i: number) => {
                      const t = typeof trigger === "object" ? trigger : { text: String(trigger), valence: i % 2 === 0 ? "negative" : "positive" };
                      return (
                        <span
                          key={i}
                          className={cn(
                            "inline-block px-2 py-0.5 rounded-md text-[11px] font-medium",
                            t.valence === "negative" ? "bg-bg-danger text-txt-danger" : "bg-bg-success text-txt-success"
                          )}
                        >
                          {t.text || t.name || String(trigger)}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Active Topics + Network Connections — 2-col */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Active Topics */}
        {persona.active_topics && persona.active_topics.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-3">Active in topics</h2>
            <div className="space-y-1.5">
              {persona.active_topics.map((t: any) => {
                const topic = typeof t === "object" ? t : { name: String(t) };
                return (
                  <div key={topic.name} className="flex items-center justify-between">
                    <span className="text-[12px] text-text-primary">{topic.name}</span>
                    <div className="flex items-center gap-1">
                      {topic.post_count && <span className="text-[12px] text-text-secondary">{topic.post_count} posts</span>}
                      {topic.camp && <Badge label={topic.camp} />}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Network Connections */}
        {persona.connections && persona.connections.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-1">Network connections</h2>
            <p className="text-[12px] text-text-secondary mb-3">Users they interact with most</p>
            <div className="space-y-1.5">
              {persona.connections.slice(0, 5).map((c: any, i: number) => {
                const name = c.connected_username || `User #${c.connected_user_id}`;
                const relationColors = ["bg-bg-success", "bg-bg-danger", "bg-bg-warning", "bg-bg-purple", "bg-bg-info"];
                const textColors = ["text-txt-success", "text-txt-danger", "text-txt-warning", "text-txt-purple", "text-txt-info"];
                return (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className={cn("w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-medium", relationColors[i % 5], textColors[i % 5])}>
                        {initials(name)}
                      </div>
                      <span className="text-[12px] text-text-primary">{name}</span>
                      <span className="text-[12px] text-text-secondary">({c.interaction_type || "connected"})</span>
                    </div>
                    {c.relationship_type && <Badge label={c.relationship_type} />}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Recent Posts */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-text-primary">Recent posts</h2>
          <span className="text-[11px] text-text-secondary">View all {formatNumber(persona.post_count || 0)}</span>
        </div>
        <div className="divide-y divide-border-primary">
          {(persona.top_posts || posts?.items || []).slice(0, 5).map((p: any) => (
            <div key={p.id} className="py-2">
              <div className="flex items-start justify-between gap-3 mb-0.5">
                <span className="text-[12px] font-medium text-text-primary">{p.title || (p.body || "").slice(0, 120)}</span>
                <div className="flex items-center gap-2 shrink-0">
                  {p.platform_name && <span className="tag">{p.platform_name}</span>}
                  {p.score != null && <span className="text-[11px] text-success">{formatNumber(p.score)} pts</span>}
                </div>
              </div>
              <div className="text-[12px] text-text-secondary">
                {timeAgo(p.posted_at)}
                {p.comment_count != null && ` — ${p.comment_count} comments`}
              </div>
            </div>
          ))}
          {(persona.top_posts || posts?.items || []).length === 0 && (
            <p className="text-sm text-text-tertiary py-4">No posts available</p>
          )}
        </div>
      </div>
    </div>
  );
}
