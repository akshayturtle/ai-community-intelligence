import { useParams, Link } from "react-router-dom";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";
import { ExternalLink } from "lucide-react";
import { useTopic, useTopicTimeline, useTopicPosts, useTopicPlatformTones } from "../api/hooks";
import { formatNumber, timeAgo, sentimentColor, cn } from "../lib/utils";
import Badge from "../components/common/Badge";
import { CardSkeleton } from "../components/common/Skeleton";

const campColors = ["#1D9E75", "#E24B4A", "#BA7517", "#378ADD", "#534AB7"];

export default function TopicDetail() {
  const { id } = useParams<{ id: string }>();
  const topicId = Number(id);
  const { data: topic, isLoading } = useTopic(topicId);
  const { data: timeline } = useTopicTimeline(topicId);
  const { data: posts } = useTopicPosts(topicId, { per_page: "10" });
  const { data: platformTones } = useTopicPlatformTones(topicId);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (!topic) return <p className="text-text-secondary">Topic not found</p>;

  return (
    <div className="space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px]">
        <Link to="/" className="text-text-secondary hover:text-text-primary">Dashboard</Link>
        <span className="text-text-secondary">/</span>
        <span className="text-text-primary">{topic.name}</span>
      </div>

      {/* Title row */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-medium text-text-primary">{topic.name}</h1>
        {topic.status && <Badge label={topic.status} />}
        {topic.velocity != null && (
          <Badge
            label={`${topic.velocity > 0 ? "+" : ""}${(topic.velocity * 100).toFixed(0)}% velocity`}
            variant={topic.velocity > 0 ? "positive" : "negative"}
          />
        )}
      </div>

      {/* 4-col Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-0.5">Total mentions</div>
          <div className="text-lg font-medium text-text-primary">{formatNumber(topic.total_mentions)}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-0.5">Platforms active</div>
          <div className="text-lg font-medium text-text-primary">{topic.platforms_active ? Object.keys(topic.platforms_active).length : 0}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-0.5">Avg sentiment</div>
          <div className={cn("text-lg font-medium", sentimentColor(topic.sentiment_distribution?.avg ?? null))}>
            {topic.sentiment_distribution?.avg != null ? `${Number(topic.sentiment_distribution.avg) > 0 ? "+" : ""}${Number(topic.sentiment_distribution.avg).toFixed(2)}` : "—"}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-0.5">First seen</div>
          <div className="text-lg font-medium text-text-primary">{topic.first_seen_at ? timeAgo(topic.first_seen_at) : "—"}</div>
        </div>
      </div>

      {/* Sentiment Timeline */}
      {timeline && timeline.timeline.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-3">Sentiment over time (30 days)</h2>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={timeline.timeline}>
              <defs>
                <linearGradient id="posGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1D9E75" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#1D9E75" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="negGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#E24B4A" stopOpacity={0.08} />
                  <stop offset="95%" stopColor="#E24B4A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} tickFormatter={(v: string) => v.slice(5)} />
              <YAxis tick={{ fill: "var(--mm-text-tertiary)", fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "var(--mm-bg-primary)", border: "0.5px solid var(--mm-border-primary)", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "var(--mm-text-primary)" }}
              />
              <Area type="monotone" dataKey="positive_count" name="Positive" stroke="#1D9E75" fill="url(#posGrad)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="negative_count" name="Negative" stroke="#E24B4A" fill="url(#negGrad)" strokeWidth={1.5} dot={false} />
              <Area type="monotone" dataKey="neutral_count" name="Neutral" stroke="var(--mm-border-secondary)" fill="transparent" strokeWidth={1} strokeDasharray="4 4" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Opinion Camps — 3-col with colored left border */}
      {topic.opinion_camps && topic.opinion_camps.length > 0 && (
        <>
          <h2 className="text-sm font-medium text-text-primary">Opinion camps</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {topic.opinion_camps.map((camp: any, i: number) => {
              const color = campColors[i % campColors.length];
              return (
                <div key={i} className="border border-border-primary rounded-none p-3.5" style={{ borderLeft: `3px solid ${color}` }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-medium" style={{ color }}>{camp.name || `Camp ${i + 1}`}</span>
                    {camp.size && (
                      <span className="inline-block px-2 py-0.5 rounded-md text-[11px] font-medium bg-bg-success text-txt-success">
                        {camp.size}%
                      </span>
                    )}
                  </div>
                  <p className="text-[12px] text-text-secondary leading-relaxed mb-2">
                    {camp.description || camp.stance || "No description"}
                  </p>
                  {camp.key_arguments && (
                    <div className="text-[12px] text-text-secondary leading-relaxed">
                      {(Array.isArray(camp.key_arguments) ? camp.key_arguments : []).map((arg: string, j: number) => (
                        <div key={j}>- {arg}</div>
                      ))}
                    </div>
                  )}
                  {camp.top_voices && camp.top_voices.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-border-primary">
                      <div className="text-[12px] text-text-secondary mb-1">Top voices:</div>
                      <div className="flex flex-wrap gap-1">
                        {camp.top_voices.map((v: string) => (
                          <span key={v} className="tag">{v}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Platform Breakdown */}
      {platformTones && platformTones.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-text-primary">Platform breakdown</h2>
            <div className="flex gap-1">
              {platformTones.map((pt: any) => (
                <span key={pt.id} className="tag">{pt.platform_name}: {pt.post_count || 0}</span>
              ))}
            </div>
          </div>
          <p className="text-[12px] text-text-secondary mb-3">How each platform talks about this differently</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {platformTones.map((pt: any) => (
              <div key={pt.id} className="bg-bg-secondary rounded-lg p-3">
                <div className="text-[12px] font-medium text-text-primary mb-1 capitalize">{pt.platform_name} tone</div>
                <p className="text-[12px] text-text-secondary">{pt.tone_description || "No tone analysis yet"}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Posts */}
      <div className="card">
        <h2 className="text-sm font-medium text-text-primary mb-3">Top posts on this topic</h2>
        <div className="divide-y divide-border-primary">
          {(topic.top_posts || posts?.items || []).slice(0, 10).map((p: any) => (
            <div key={p.id} className="flex items-start justify-between py-2 gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-medium text-text-primary">{p.title || (p.body || "").slice(0, 100)}</div>
                <div className="text-[12px] text-text-secondary mt-0.5">
                  {p.comment_count != null && `${p.comment_count} comments`}
                  {p.platform_name && ` — ${p.platform_name}`}
                  {` — ${timeAgo(p.posted_at)}`}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {p.platform_name && <span className="tag">{p.platform_name}</span>}
                {p.score != null && <span className="text-[11px] text-success">{formatNumber(p.score)} pts</span>}
                {p.url && (
                  <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info">
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            </div>
          ))}
          {(topic.top_posts || posts?.items || []).length === 0 && (
            <p className="text-sm text-text-tertiary py-4">No posts yet</p>
          )}
        </div>
      </div>

      {/* Related News */}
      {topic.related_news && topic.related_news.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-3">Related News</h2>
          <div className="divide-y divide-border-primary">
            {topic.related_news.map((n: any) => (
              <div key={n.id} className="flex items-start gap-3 py-2">
                <div className="flex-1 min-w-0">
                  <div className="text-[12px] font-medium text-text-primary">{n.title}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[12px] text-text-secondary">{n.source_name}</span>
                    <span className="text-[12px] text-text-tertiary">{timeAgo(n.published_at)}</span>
                    {n.magnitude && <Badge label={n.magnitude} />}
                  </div>
                </div>
                {n.url && (
                  <a href={n.url} target="_blank" rel="noopener noreferrer" className="text-text-tertiary hover:text-info shrink-0">
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
