import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft, Play, Loader2, CheckCircle, XCircle,
  ThumbsUp, ThumbsDown, Users, FileText, Lightbulb, Eye,
  ExternalLink,
} from "lucide-react";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
} from "recharts";
import {
  useResearchProject, useResearchInsights, useResearchContacts,
  useResearchPosts, useRunResearch,
} from "../api/hooks";
import { formatNumber, cn } from "../lib/utils";
import { CardSkeleton } from "../components/common/Skeleton";
import Pagination from "../components/common/Pagination";

const PIE_COLORS = ["#1D9E75", "#E24B4A", "#94a3b8"];

const tabs = [
  { key: "overview", label: "Overview", icon: Eye },
  { key: "insights", label: "Products & Insights", icon: Lightbulb },
  { key: "contacts", label: "Contacts", icon: Users },
  { key: "posts", label: "Posts", icon: FileText },
] as const;

type TabKey = typeof tabs[number]["key"];

const STATUS_LABEL: Record<string, string> = {
  draft: "Draft",
  expanding: "Expanding keywords...",
  scraping: "Scraping Reddit...",
  processing: "Analyzing posts...",
  complete: "Complete",
  failed: "Failed",
};

export default function ResearchDetail() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id) || 0;
  const [tab, setTab] = useState<TabKey>("overview");
  const [contactPage, setContactPage] = useState(1);
  const [postPage, setPostPage] = useState(1);

  const { data: project, isLoading } = useResearchProject(projectId);
  const { data: insights } = useResearchInsights(projectId);
  const { data: contactsData } = useResearchContacts(projectId, { page: String(contactPage), per_page: "50" });
  const { data: postsData } = useResearchPosts(projectId, { page: String(postPage), per_page: "20" });
  const runMutation = useRunResearch();

  if (isLoading || !project) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}</div>
      </div>
    );
  }

  const isRunning = ["expanding", "scraping", "processing"].includes(project.status);
  const sentimentData = insights?.sentiment_breakdown
    ? [
        { name: "Positive", value: insights.sentiment_breakdown.positive || 0 },
        { name: "Negative", value: insights.sentiment_breakdown.negative || 0 },
        { name: "Neutral", value: insights.sentiment_breakdown.neutral || 0 },
      ]
    : [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link to="/research" className="p-1.5 rounded-lg hover:bg-bg-secondary text-text-tertiary hover:text-text-primary transition-colors">
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div className="flex-1">
          <h1 className="text-lg font-medium text-text-primary">{project.name}</h1>
          {project.description && <p className="text-[12px] text-text-secondary">{project.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            "inline-flex items-center gap-1 px-2 py-1 rounded-md text-[12px] font-medium",
            project.status === "complete" ? "bg-bg-success text-txt-success" :
            project.status === "failed" ? "bg-bg-danger text-txt-danger" :
            isRunning ? "bg-bg-info text-txt-info" :
            "bg-bg-secondary text-text-secondary"
          )}>
            {isRunning && <Loader2 className="w-3 h-3 animate-spin" />}
            {project.status === "complete" && <CheckCircle className="w-3 h-3" />}
            {project.status === "failed" && <XCircle className="w-3 h-3" />}
            {STATUS_LABEL[project.status] || project.status}
          </span>
          {!isRunning && (
            <button
              onClick={() => runMutation.mutate(projectId)}
              disabled={runMutation.isPending}
              className="flex items-center gap-1 px-3 py-1 rounded-lg text-sm bg-info text-white hover:opacity-90 disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              {project.status === "complete" ? "Re-run" : "Run"}
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-bg-primary border border-border-primary rounded-xl p-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors flex-1 justify-center",
              tab === t.key
                ? "bg-bg-info text-txt-info"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
            )}
          >
            <t.icon className="w-4 h-4" />
            <span className="hidden md:inline">{t.label}</span>
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab project={project} insights={insights} sentimentData={sentimentData} />}
      {tab === "insights" && <InsightsTab insights={insights} />}
      {tab === "contacts" && <ContactsTab data={contactsData} page={contactPage} onPageChange={setContactPage} />}
      {tab === "posts" && <PostsTab data={postsData} page={postPage} onPageChange={setPostPage} />}
    </div>
  );
}

function OverviewTab({ project, insights, sentimentData }: {
  project: any; insights: any; sentimentData: { name: string; value: number }[];
}) {
  return (
    <div className="space-y-3">
      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Posts Collected</div>
          <div className="text-[22px] font-medium text-text-primary">{formatNumber(project.post_count)}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Keywords Used</div>
          <div className="text-[22px] font-medium text-info">{(project.expanded_keywords || []).length}</div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Overall Sentiment</div>
          <div className={cn(
            "text-[18px] font-medium",
            insights?.overall_sentiment === "positive" ? "text-success" :
            insights?.overall_sentiment === "negative" ? "text-danger" : "text-warning"
          )}>
            {insights?.overall_sentiment || "—"}
          </div>
        </div>
        <div className="bg-bg-secondary rounded-lg p-3">
          <div className="text-[12px] text-text-secondary mb-1">Products Found</div>
          <div className="text-[22px] font-medium text-purple">{(insights?.products_mentioned || []).length}</div>
        </div>
      </div>

      {/* Keywords */}
      {project.expanded_keywords && project.expanded_keywords.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-2">Search keywords (auto-expanded)</h2>
          <div className="flex flex-wrap gap-1">
            {project.expanded_keywords.map((k: string, i: number) => (
              <span key={i} className={cn(
                "inline-block px-2 py-0.5 rounded-md text-[11px]",
                (project.initial_terms || []).includes(k)
                  ? "bg-bg-info text-txt-info font-medium"
                  : "bg-bg-secondary text-text-secondary"
              )}>
                {k}
              </span>
            ))}
          </div>
          <p className="text-[10px] text-text-tertiary mt-1">Blue = your original terms, gray = AI-expanded</p>
        </div>
      )}

      {/* Discussion Summary + Sentiment */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3">
        {insights?.discussion_summary && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Discussion summary</h2>
            <p className="text-[12px] text-text-secondary whitespace-pre-line">{insights.discussion_summary}</p>
          </div>
        )}
        {sentimentData.some(s => s.value > 0) && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Sentiment breakdown</h2>
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={sentimentData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%" cy="50%"
                  outerRadius={60}
                  label={({ name, value }: any) => `${name} ${value}%`}
                  labelLine={false}
                >
                  {sentimentData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Key Themes */}
      {insights?.key_themes && insights.key_themes.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-2">Key themes</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {insights.key_themes.map((t: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-[12px] pb-1.5 border-b border-border-primary last:border-0">
                <span className="text-text-primary font-medium">{t.theme}</span>
                <div className="flex items-center gap-2">
                  <span className="text-text-tertiary">{t.post_count} posts</span>
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[10px]",
                    t.sentiment === "positive" ? "bg-bg-success text-txt-success" :
                    t.sentiment === "negative" ? "bg-bg-danger text-txt-danger" :
                    "bg-bg-warning text-txt-warning"
                  )}>{t.sentiment}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function InsightsTab({ insights }: { insights: any }) {
  if (!insights) return <p className="text-sm text-text-tertiary text-center py-8">Run the research first to see insights.</p>;

  return (
    <div className="space-y-3">
      {/* Products Mentioned */}
      {insights.products_mentioned && insights.products_mentioned.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-medium text-text-primary mb-3">Products mentioned</h2>
          <div className="space-y-3">
            {insights.products_mentioned.map((p: any, i: number) => (
              <div key={i} className="pb-3 border-b border-border-primary last:border-0">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[13px] font-medium text-text-primary">{p.name}</span>
                  <span className="text-[11px] text-text-tertiary">{p.mention_count} mentions</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <div>
                    <div className="flex items-center gap-1 mb-0.5">
                      <ThumbsUp className="w-3 h-3 text-success" />
                      <span className="text-[11px] font-medium text-text-secondary">Pros</span>
                    </div>
                    {(p.pros || []).map((pro: string, j: number) => (
                      <div key={j} className="text-[12px] text-text-primary">+ {pro}</div>
                    ))}
                    {(!p.pros || p.pros.length === 0) && <span className="text-[11px] text-text-tertiary">None mentioned</span>}
                  </div>
                  <div>
                    <div className="flex items-center gap-1 mb-0.5">
                      <ThumbsDown className="w-3 h-3 text-danger" />
                      <span className="text-[11px] font-medium text-text-secondary">Cons</span>
                    </div>
                    {(p.cons || []).map((con: string, j: number) => (
                      <div key={j} className="text-[12px] text-text-primary">- {con}</div>
                    ))}
                    {(!p.cons || p.cons.length === 0) && <span className="text-[11px] text-text-tertiary">None mentioned</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Feature Requests + Unmet Needs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {insights.feature_requests && insights.feature_requests.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Feature requests</h2>
            <div className="space-y-1.5">
              {insights.feature_requests.map((f: any, i: number) => (
                <div key={i} className="flex items-start justify-between text-[12px]">
                  <span className="text-text-primary flex-1">{f.description}</span>
                  <div className="flex items-center gap-1.5 ml-2 shrink-0">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px]",
                      f.frequency === "common" ? "bg-bg-danger text-txt-danger" :
                      f.frequency === "occasional" ? "bg-bg-warning text-txt-warning" :
                      "bg-bg-secondary text-text-secondary"
                    )}>{f.frequency}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {insights.unmet_needs && insights.unmet_needs.length > 0 && (
          <div className="card">
            <h2 className="text-sm font-medium text-text-primary mb-2">Unmet needs</h2>
            <div className="space-y-2">
              {insights.unmet_needs.map((n: any, i: number) => (
                <div key={i} className="text-[12px]">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className="font-medium text-text-primary">{n.description}</span>
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px]",
                      n.intensity === "high" ? "bg-bg-danger text-txt-danger" :
                      n.intensity === "medium" ? "bg-bg-warning text-txt-warning" :
                      "bg-bg-secondary text-text-secondary"
                    )}>{n.intensity}</span>
                  </div>
                  {n.evidence && <p className="text-text-tertiary italic">"{n.evidence}"</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {(!insights.products_mentioned || insights.products_mentioned.length === 0) &&
       (!insights.feature_requests || insights.feature_requests.length === 0) &&
       (!insights.unmet_needs || insights.unmet_needs.length === 0) && (
        <p className="text-sm text-text-tertiary text-center py-8">No detailed insights extracted yet.</p>
      )}
    </div>
  );
}

function ContactsTab({ data, page, onPageChange }: { data: any; page: number; onPageChange: (p: number) => void }) {
  const contacts = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (contacts.length === 0) return <p className="text-sm text-text-tertiary text-center py-8">No contacts found. Users need at least 2 posts to appear here.</p>;

  return (
    <div className="space-y-3">
      <div className="card">
        <div className="text-[12px] text-text-tertiary mb-3">{data?.total || 0} contacts found</div>

        {/* Table Header */}
        <div className="grid grid-cols-[2fr_1fr_1fr_2fr] gap-0 text-[12px]">
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary">Username</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Posts</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary text-center">Sentiment</div>
          <div className="p-2 font-medium text-text-secondary border-b border-border-primary">Subreddits</div>

          {contacts.map((c: any) => (
            <div key={c.id} className="contents">
              <div className="p-2 border-b border-border-primary">
                <a
                  href={c.profile_url || `https://www.reddit.com/user/${c.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-info hover:underline flex items-center gap-1"
                >
                  u/{c.username}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
              <div className="p-2 border-b border-border-primary text-center text-text-primary font-mono">{c.post_count}</div>
              <div className="p-2 border-b border-border-primary text-center">
                {c.sentiment_leaning ? (
                  <span className={cn(
                    "px-1.5 py-0.5 rounded text-[10px]",
                    c.sentiment_leaning === "positive" ? "bg-bg-success text-txt-success" :
                    c.sentiment_leaning === "negative" ? "bg-bg-danger text-txt-danger" :
                    "bg-bg-secondary text-text-secondary"
                  )}>{c.sentiment_leaning}</span>
                ) : <span className="text-text-tertiary">—</span>}
              </div>
              <div className="p-2 border-b border-border-primary">
                <div className="flex flex-wrap gap-1">
                  {(c.topics_discussed || []).slice(0, 4).map((t: string, i: number) => (
                    <span key={i} className="inline-block px-1 py-0.5 rounded text-[10px] bg-bg-secondary text-text-secondary">r/{t}</span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />}
    </div>
  );
}

function PostsTab({ data, page, onPageChange }: { data: any; page: number; onPageChange: (p: number) => void }) {
  const posts = data?.items || [];
  const totalPages = data ? Math.ceil(data.total / data.per_page) : 1;

  if (posts.length === 0) return <p className="text-sm text-text-tertiary text-center py-8">No posts collected yet.</p>;

  return (
    <div className="space-y-2">
      <div className="text-[12px] text-text-tertiary">{data?.total || 0} posts collected</div>
      {posts.map((p: any) => (
        <div key={p.id} className="card">
          <div className="flex items-start justify-between mb-1">
            <div className="flex-1 min-w-0">
              {p.title && <h3 className="text-[13px] font-medium text-text-primary truncate">{p.title}</h3>}
              <div className="flex items-center gap-2 text-[11px] text-text-tertiary">
                {p.subreddit && <span>r/{p.subreddit}</span>}
                {p.posted_at && <span>{new Date(p.posted_at).toLocaleDateString()}</span>}
              </div>
            </div>
            {p.score != null && (
              <span className="text-[12px] font-mono text-text-secondary ml-2 shrink-0">{p.score} pts</span>
            )}
          </div>
          {p.body && (
            <p className="text-[12px] text-text-secondary line-clamp-3">{p.body.slice(0, 300)}</p>
          )}
          {p.url && (
            <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-info hover:underline mt-1 inline-flex items-center gap-1">
              View on Reddit <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      ))}
      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />}
    </div>
  );
}
