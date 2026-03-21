export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toString();
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return "";
  return new Date(d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function timeAgo(d: string | null | undefined): string {
  if (!d) return "";
  const now = Date.now();
  const then = new Date(d).getTime();
  const diff = now - then;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(d);
}

export function sentimentColor(val: number | null | undefined): string {
  if (val == null) return "text-text-tertiary";
  if (val > 0.05) return "text-success";
  if (val < -0.05) return "text-danger";
  return "text-text-tertiary";
}

export function sentimentLabel(val: number | null | undefined): string {
  if (val == null) return "N/A";
  if (val > 0.05) return "Positive";
  if (val < -0.05) return "Negative";
  return "Neutral";
}

export function truncate(str: string, len: number): string {
  if (str.length <= len) return str;
  return str.slice(0, len) + "...";
}

export function initials(name: string): string {
  return name
    .split(/[\s_-]+/)
    .map((w) => w[0]?.toUpperCase() || "")
    .slice(0, 2)
    .join("");
}
