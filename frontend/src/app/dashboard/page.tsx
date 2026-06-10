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
  BarChart3,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
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

interface DailyData {
  date: string;
  traces: number;
  success: number;
  failure: number;
  avg_delta: number;
}

export default function DashboardPage() {
  const [feed, setFeed] = useState<Trace[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [dailyData, setDailyData] = useState<DailyData[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState<"checking" | "healthy" | "down">("checking");

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const backendBase = apiBase.replace(/\/api\/v1$/, "");

  const fetchData = useCallback(async () => {
    try {
      const [feedRes, statsRes, healthRes, dailyRes] = await Promise.all([
        fetch(`${apiBase}/feed?limit=30`),
        fetch(`${apiBase}/stats`),
        fetch(`${backendBase}/health`).catch(() => null),
        fetch(`${apiBase}/stats/daily?days=30`).catch(() => null),
      ]);
      if (feedRes.ok) {
        const feedJson = await feedRes.json();
        setFeed(Array.isArray(feedJson) ? feedJson : feedJson.data || []);
      }
      if (statsRes.ok) setStats(await statsRes.json());
      if (dailyRes && dailyRes.ok) {
        const dailyJson = await dailyRes.json();
        setDailyData(dailyJson.data || []);
      }
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

      {/* Trend Chart */}
      {dailyData.length >= 3 && (
        <div className="mb-8 rounded-xl border border-garl-border bg-garl-surface p-5">
          <div className="mb-4 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-garl-accent" />
            <span className="font-mono text-xs uppercase tracking-wider text-garl-muted">
              Daily Execution Activity (30 days)
            </span>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyData}>
                <defs>
                  <linearGradient id="traceGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00FF88" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00FF88" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  tickFormatter={(v: string) => v.slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }}
                  axisLine={false}
                  tickLine={false}
                  width={30}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0d0d1a",
                    border: "1px solid #1a1a2e",
                    borderRadius: "8px",
                    fontFamily: "monospace",
                    fontSize: "11px",
                  }}
                  labelFormatter={(v) => String(v)}
                  formatter={(value, name) => {
                    const labels: Record<string, string> = { traces: "Traces", success: "Success", failure: "Failure" };
                    return [String(value), labels[String(name)] || String(name)];
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="traces"
                  stroke="#00FF88"
                  strokeWidth={2}
                  fill="url(#traceGrad)"
                />
                <Area
                  type="monotone"
                  dataKey="success"
                  stroke="#22c55e"
                  strokeWidth={1}
                  fill="none"
                  strokeDasharray="4 4"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {dailyData.length > 0 && dailyData.length < 3 && (
        <div className="mb-8 rounded-xl border border-garl-border bg-garl-surface p-5 text-center">
          <BarChart3 className="mx-auto mb-2 h-6 w-6 text-garl-muted/40" />
          <p className="font-mono text-xs text-garl-muted">
            Building activity history... ({dailyData.reduce((s, d) => s + d.traces, 0)} traces across {dailyData.length} days)
          </p>
        </div>
      )}

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
                  initial={false}
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
