import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}

export function formatDelta(delta: number): string {
  const sign = delta >= 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

export function timeAgo(dateStr: string): string {
  const then = new Date(dateStr).getTime();
  if (isNaN(then)) return "unknown";

  const diff = Date.now() - then;
  if (diff < 0) return "just now";

  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return `${seconds}s ago`;
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

export function getScoreColor(score: number): string {
  if (score >= 80) return "text-garl-accent";
  if (score >= 60) return "text-green-400";
  if (score >= 40) return "text-garl-warning";
  return "text-garl-danger";
}

export function getStatusColor(status: string): string {
  switch (status) {
    case "success":
      return "text-garl-accent";
    case "failure":
      return "text-garl-danger";
    case "partial":
      return "text-garl-warning";
    default:
      return "text-garl-muted";
  }
}

export function getStatusIcon(status: string): string {
  switch (status) {
    case "success":
      return "●";
    case "failure":
      return "✕";
    case "partial":
      return "◐";
    default:
      return "○";
  }
}

export function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  if (usd < 1) return `$${usd.toFixed(3)}`;
  if (usd < 100) return `$${usd.toFixed(2)}`;
  return `$${usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function getCategoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    coding: "Coding",
    research: "Research",
    sales: "Sales",
    data: "Data",
    automation: "Automation",
    other: "Other",
  };
  return labels[cat] || cat;
}
