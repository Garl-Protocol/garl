"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  TrendingUp,
  Users,
  CheckCircle,
  XCircle,
  Clock,
} from "lucide-react";
import {
  formatScore,
  formatDelta,
  formatDuration,
  timeAgo,
  getStatusColor,
  getStatusIcon,
  getCategoryLabel,
} from "@/lib/utils";
import type { Trace, Stats } from "@/lib/api";

export default function DashboardPage() {
  const [feed, setFeed] = useState<Trace[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<"checking" | "healthy" | "down">("checking");

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const backendBase = apiBase.replace(/\/api\/v1$/, "");

  const fetchData = useCallback(async () => {
    try {
      const [feedRes, statsRes, healthRes] = await Promise.all([
        fetch(`${apiBase}/feed?limit=30`),
        fetch(`${apiBase}/stats`),
        fetch(`${backendBase}/health`).catch(() => null),
      ]);
      if (feedRes.ok) setFeed(await feedRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
      if (healthRes && healthRes.ok) {
        setHealthStatus("healthy");
      } else {
        setHealthStatus("down");
      }
    } catch {
      setHealthStatus("down");
    } finally {
      setLoading(false);
    }
  }, [apiBase, backendBase]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> dashboard
        </h1>
        <p className="mt-1 font-mono text-sm text-garl-muted">
          Real-time execution feed &amp; protocol metrics
        </p>
      </div>

      {/* Stats cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<Users className="h-5 w-5" />}
          label="Total Agents"
          value={stats?.total_agents?.toString() || "—"}
        />
        <StatCard
          icon={<Activity className="h-5 w-5" />}
          label="Total Traces"
          value={stats?.total_traces?.toString() || "—"}
        />
        <StatCard
          icon={<TrendingUp className="h-5 w-5" />}
          label="Top Agent"
          value={stats?.top_agent?.name?.slice(0, 18) || "—"}
          sub={
            stats?.top_agent
              ? `Score: ${formatScore(stats.top_agent.trust_score)}`
              : undefined
          }
        />
        <StatCard
          icon={healthStatus === "healthy" ? <CheckCircle className="h-5 w-5" /> : <XCircle className="h-5 w-5" />}
          label="Protocol Status"
          value={healthStatus === "checking" ? "Checking..." : healthStatus === "healthy" ? "Operational" : "Offline"}
          accent={healthStatus === "healthy"}
        />
      </div>

      {/* Live Feed */}
      <div className="rounded-xl border border-garl-border bg-garl-surface">
        <div className="flex items-center justify-between border-b border-garl-border px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-garl-accent animate-pulse" />
            <span className="font-mono text-sm font-semibold">Live Feed</span>
          </div>
          <span className="font-mono text-xs text-garl-muted">
            {feed.length} recent traces
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
          </div>
        ) : feed.length === 0 ? (
          <div className="py-20 text-center font-mono text-sm text-garl-muted">
            No traces yet. Run the mock script to populate data.
          </div>
        ) : (
          <div className="divide-y divide-garl-border/50">
            <AnimatePresence initial={false}>
              {feed.map((trace, i) => (
                <motion.div
                  key={trace.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="flex items-center gap-4 px-5 py-3 font-mono text-sm transition-colors hover:bg-garl-bg/50"
                >
                  <span
                    className={`text-lg ${getStatusColor(trace.status)}`}
                    title={trace.status}
                  >
                    {getStatusIcon(trace.status)}
                  </span>

                  <span className="w-20 shrink-0 truncate text-xs text-garl-muted">
                    {trace.agent_id.slice(0, 8)}
                  </span>

                  <span className="flex-1 truncate text-garl-text">
                    {trace.task_description}
                  </span>

                  <span className="hidden w-16 shrink-0 text-right text-xs text-garl-muted sm:block">
                    {getCategoryLabel(trace.category)}
                  </span>

                  <span
                    className={`w-14 shrink-0 text-right text-xs font-semibold ${
                      trace.trust_delta >= 0
                        ? "text-garl-accent"
                        : "text-garl-danger"
                    }`}
                  >
                    {formatDelta(trace.trust_delta)}
                  </span>

                  <span className="hidden w-14 shrink-0 text-right text-xs text-garl-muted lg:block">
                    {formatDuration(trace.duration_ms)}
                  </span>

                  <span className="w-14 shrink-0 text-right text-[11px] text-garl-muted">
                    {timeAgo(trace.created_at)}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-garl-border bg-garl-surface p-4">
      <div className="mb-2 flex items-center gap-2 text-garl-muted">
        {icon}
        <span className="font-mono text-xs uppercase tracking-wider">
          {label}
        </span>
      </div>
      <div
        className={`font-mono text-xl font-bold ${
          accent ? "text-garl-accent" : "text-garl-text"
        }`}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-1 font-mono text-xs text-garl-muted">{sub}</div>
      )}
    </div>
  );
}
