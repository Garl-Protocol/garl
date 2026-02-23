"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  Shield,
  ArrowLeft,
  Copy,
  Check,
  AlertTriangle,
  TrendingDown,
  Zap,
  Clock,
  DollarSign,
  Activity,
  FileCheck,
  FlaskConical,
} from "lucide-react";
import {
  formatScore,
  formatDelta,
  formatDuration,
  formatCost,
  timeAgo,
  getScoreColor,
  getStatusColor,
  getStatusIcon,
  getCategoryLabel,
} from "@/lib/utils";
import type { AgentDetail } from "@/lib/api";

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params.id as string;
  const [data, setData] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [authRequired, setAuthRequired] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [authError, setAuthError] = useState("");

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchData = useCallback(async (key?: string) => {
    setLoading(true);
    try {
      const headers: Record<string, string> = {};
      const storedKey = key || apiKey || (typeof window !== "undefined" ? localStorage.getItem("garl_api_key") || "" : "");
      if (storedKey) headers["x-api-key"] = storedKey;

      const res = await fetch(`${apiBase}/agents/${agentId}/detail`, { headers });
      if (res.status === 401) {
        // Auth required for /detail — fall back to public profile
        try {
          const publicRes = await fetch(`${apiBase}/agents/${agentId}`);
          if (publicRes.ok) {
            const publicData = await publicRes.json();
            setData({ agent: publicData, recent_traces: [], history: [], reputation_history: [], decay_projection: null } as unknown as AgentDetail);
            setAuthRequired(false);
          } else {
            setAuthRequired(true);
          }
        } catch {
          setAuthRequired(true);
        }
        setLoading(false);
        return;
      }
      if (res.ok) {
        setData(await res.json());
        setAuthRequired(false);
        if (storedKey && typeof window !== "undefined") localStorage.setItem("garl_api_key", storedKey);
      }
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [apiBase, agentId, apiKey]);

  const handleApiKeySubmit = () => {
    if (!apiKey.trim()) { setAuthError("API key is required"); return; }
    setAuthError("");
    fetchData(apiKey.trim());
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const badgeBase = "https://api.garl.ai/api/v1";
  const copyBadgeCode = () => {
    const code = `![GARL Trust](${badgeBase}/badge/svg/${agentId})`;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
      </div>
    );
  }

  if (authRequired) {
    return (
      <div className="mx-auto max-w-md px-4 py-20">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-garl-blue/30 bg-garl-surface p-8 text-center"
        >
          <Shield className="mx-auto mb-4 h-10 w-10 text-garl-blue" />
          <h2 className="mb-2 font-mono text-lg font-semibold text-garl-text">
            Protected Data
          </h2>
          <p className="mb-6 font-mono text-xs text-garl-muted">
            This endpoint requires an API key. Enter the key you received when registering your agent.
          </p>
          <div className="space-y-3">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleApiKeySubmit()}
              placeholder="Enter your API key"
              className="w-full rounded-lg border border-garl-border bg-garl-bg px-4 py-2.5 font-mono text-sm text-garl-text placeholder-garl-muted focus:border-garl-blue/50 focus:outline-none"
            />
            {authError && (
              <p className="font-mono text-xs text-garl-danger">{authError}</p>
            )}
            <button
              onClick={handleApiKeySubmit}
              className="w-full rounded-lg bg-garl-blue/20 px-4 py-2.5 font-mono text-sm font-semibold text-garl-blue transition-all hover:bg-garl-blue/30"
            >
              Unlock Agent Detail
            </button>
          </div>
          <a
            href="/leaderboard"
            className="mt-4 inline-block font-mono text-xs text-garl-muted hover:text-garl-accent"
          >
            ← Back to Leaderboard
          </a>
        </motion.div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20 text-center font-mono text-garl-muted">
        Agent not found.
      </div>
    );
  }

  const { agent, recent_traces, reputation_history, decay_projection } = data;
  const anomalies = agent.anomaly_flags || [];
  const dims = {
    reliability: agent.score_reliability ?? 50,
    security: agent.score_security ?? 50,
    speed: agent.score_speed ?? 50,
    cost_efficiency: agent.score_cost_efficiency ?? 50,
    consistency: agent.score_consistency ?? 50,
  };

  const tier = (agent as any).certification_tier || "bronze";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <a
        href="/leaderboard"
        className="mb-6 inline-flex items-center gap-1 font-mono text-xs text-garl-muted transition-colors hover:text-garl-accent"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to Leaderboard
      </a>

      {/* Anomaly alerts */}
      {anomalies.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 rounded-xl border border-garl-warning/30 bg-garl-warning/5 p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-garl-warning" />
            <span className="font-mono text-sm font-semibold text-garl-warning">
              Anomaly Detected
            </span>
          </div>
          {anomalies.slice(-3).map((a, i) => (
            <div key={i} className="font-mono text-xs text-garl-muted ml-6">
              <span className={a.severity === "critical" ? "text-garl-danger" : "text-garl-warning"}>
                [{a.severity}]
              </span>{" "}
              {a.message}
            </div>
          ))}
        </motion.div>
      )}

      {/* Sandbox banner */}
      {(agent as any).is_sandbox && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 rounded-xl border-2 border-amber-500/40 bg-amber-500/10 p-3 sm:p-4"
        >
          <div className="flex items-start gap-2.5 sm:items-center sm:gap-3">
            <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-amber-400 sm:mt-0" />
            <div className="min-w-0">
              <span className="font-mono text-xs font-bold tracking-wide text-amber-400 sm:text-sm">
                THIS IS A TEST AGENT
              </span>
              <p className="mt-0.5 font-mono text-[10px] leading-relaxed text-amber-400/70 sm:text-xs">
                Sandbox agents are excluded from the public leaderboard and do not affect protocol statistics.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Agent header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 rounded-xl border border-garl-border bg-garl-surface p-6"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-3">
              <Shield className="h-6 w-6 text-garl-accent" />
              <h1 className="font-mono text-2xl font-bold">{agent.name}</h1>
              {agent.total_traces >= 10 && (
                <span className="rounded bg-garl-accent/10 px-2 py-0.5 font-mono text-xs text-garl-accent">
                  VERIFIED
                </span>
              )}
              <span className={`rounded px-2 py-0.5 font-mono text-xs font-bold uppercase tracking-wider tier-${tier}`}>
                {tier}
              </span>
            </div>
            <p className="mb-3 text-sm text-garl-muted">{agent.description}</p>
            <div className="flex flex-wrap gap-3 font-mono text-xs text-garl-muted">
              <span className="rounded border border-garl-border px-2 py-1">
                {agent.framework}
              </span>
              <span className="rounded border border-garl-border px-2 py-1">
                {getCategoryLabel(agent.category)}
              </span>
              {agent.sovereign_id && (
                <span className="rounded border border-garl-border px-2 py-1 text-garl-blue">
                  {agent.sovereign_id}
                </span>
              )}
              <span className="rounded border border-garl-border px-2 py-1">
                ID: {agent.id.slice(0, 8)}...
              </span>
              {agent.last_trace_at && (
                <span className="rounded border border-garl-border px-2 py-1">
                  Last active: {timeAgo(agent.last_trace_at)}
                </span>
              )}
            </div>
            <a
              href={`/compliance?agent_id=${agent.id}`}
              className="mt-3 inline-flex items-center gap-2 rounded-lg border border-garl-blue/30 bg-garl-blue/5 px-4 py-2 font-mono text-xs text-garl-blue transition-all hover:border-garl-blue/60 hover:bg-garl-blue/10"
            >
              <FileCheck className="h-3.5 w-3.5" />
              View Compliance Report
            </a>
          </div>

          <div className="flex flex-wrap gap-5 text-center">
            <div>
              <div className={`font-mono text-3xl font-bold ${getScoreColor(agent.trust_score)}`}>
                {formatScore(agent.trust_score)}
              </div>
              <div className="mt-1 font-mono text-xs text-garl-muted">Composite</div>
            </div>
            <div>
              <div className="font-mono text-3xl font-bold text-garl-text">
                {agent.success_rate.toFixed(1)}%
              </div>
              <div className="mt-1 font-mono text-xs text-garl-muted">Success</div>
            </div>
            <div>
              <div className="font-mono text-3xl font-bold text-garl-text">
                {agent.total_traces}
              </div>
              <div className="mt-1 font-mono text-xs text-garl-muted">Traces</div>
            </div>
            {(agent.total_cost_usd ?? 0) > 0 && (
              <div>
                <div className="font-mono text-3xl font-bold text-garl-blue">
                  {formatCost(agent.total_cost_usd!)}
                </div>
                <div className="mt-1 font-mono text-xs text-garl-muted">Cost</div>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* Multi-dimensional scores + Decay + Badge */}
      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        {/* Dimension bars */}
        <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
          <div className="mb-4 flex items-center gap-2">
            <Activity className="h-4 w-4 text-garl-accent" />
            <span className="font-mono text-sm font-semibold">Trust Dimensions</span>
          </div>
          <div className="space-y-3">
            {[
              { key: "reliability", label: "Reliability", icon: Shield, value: dims.reliability, color: "bg-garl-accent", weight: "30%" },
              { key: "security", label: "Security", icon: Shield, value: dims.security, color: "bg-red-400", weight: "20%" },
              { key: "speed", label: "Speed", icon: Zap, value: dims.speed, color: "bg-garl-blue", weight: "15%" },
              { key: "cost_efficiency", label: "Cost Eff.", icon: DollarSign, value: dims.cost_efficiency, color: "bg-purple-400", weight: "10%" },
              { key: "consistency", label: "Consistency", icon: Clock, value: dims.consistency, color: "bg-amber-400", weight: "25%" },
            ].map((dim) => (
              <div key={dim.key}>
                <div className="mb-1 flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <dim.icon className="h-3 w-3 text-garl-muted" />
                    <span className="font-mono text-xs text-garl-muted">{dim.label}</span>
                  </div>
                  <span className="font-mono text-xs font-bold text-garl-text">
                    {dim.value.toFixed(1)}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-garl-border">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(dim.value, 100)}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                    className={`h-full rounded-full ${dim.color}`}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Decay projection */}
        <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
          <div className="mb-4 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-garl-warning" />
            <span className="font-mono text-sm font-semibold">Inactivity Projection</span>
          </div>
          <p className="mb-4 font-mono text-[11px] text-garl-muted">
            Scores decay 0.1%/day toward baseline when inactive. Projected values:
          </p>
          <div className="space-y-2">
            {(decay_projection || []).map((p) => (
              <div key={p.days} className="flex items-center justify-between">
                <span className="font-mono text-xs text-garl-muted">
                  +{p.days} days
                </span>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-20 overflow-hidden rounded-full bg-garl-border">
                    <div
                      className="h-full rounded-full bg-garl-warning/60"
                      style={{ width: `${Math.min(p.projected_score, 100)}%` }}
                    />
                  </div>
                  <span className={`font-mono text-xs font-bold ${getScoreColor(p.projected_score)}`}>
                    {p.projected_score.toFixed(1)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Badge embed */}
        <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
          <div className="mb-4 font-mono text-sm font-semibold">Embed Trust Badge</div>
          {/* SVG badge preview */}
          <div className="mb-4 flex justify-center">
            <img
              src={`${badgeBase}/badge/svg/${agentId}`}
              alt="GARL Trust Badge"
              className="h-5"
            />
          </div>
          <div className="mb-3 rounded-lg border border-garl-border bg-garl-bg p-2">
            <code className="block overflow-x-auto font-mono text-[10px] text-garl-muted whitespace-nowrap">
              ![GARL Trust]({badgeBase}/badge/svg/{agentId})
            </code>
          </div>
          <button
            onClick={copyBadgeCode}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-garl-border px-4 py-2 font-mono text-xs transition-all hover:border-garl-accent/40"
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-garl-accent" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                Copy Markdown
              </>
            )}
          </button>
        </div>
      </div>

      {/* Reputation timeline */}
      <div className="mb-6 rounded-xl border border-garl-border bg-garl-surface">
        <div className="border-b border-garl-border px-5 py-3">
          <span className="font-mono text-sm font-semibold">Reputation Timeline</span>
        </div>
        <div className="p-5">
          {reputation_history.length > 0 ? (
            <div className="flex items-end gap-0.5" style={{ height: 120 }}>
              {reputation_history
                .slice(0, 60)
                .reverse()
                .map((h, i) => {
                  const pct = (h.trust_score / 100) * 100;
                  return (
                    <div
                      key={i}
                      className="flex-1 rounded-t transition-all"
                      style={{
                        height: `${pct}%`,
                        backgroundColor:
                          h.event_type === "success"
                            ? "rgba(0,255,136,0.6)"
                            : h.event_type === "failure"
                            ? "rgba(255,68,68,0.6)"
                            : "rgba(255,170,0,0.6)",
                        minWidth: 3,
                      }}
                      title={`Score: ${h.trust_score} (${h.event_type})`}
                    />
                  );
                })}
            </div>
          ) : (
            <div className="flex h-[120px] items-center justify-center font-mono text-xs text-garl-muted">
              No history yet
            </div>
          )}
        </div>
      </div>

      {/* Recent traces */}
      <div className="rounded-xl border border-garl-border bg-garl-surface">
        <div className="border-b border-garl-border px-5 py-3">
          <span className="font-mono text-sm font-semibold">Recent Traces</span>
        </div>
        <div className="divide-y divide-garl-border/50">
          {recent_traces.length === 0 ? (
            <div className="py-12 text-center font-mono text-sm text-garl-muted">
              No traces yet
            </div>
          ) : (
            recent_traces.slice(0, 20).map((trace) => (
              <div
                key={trace.id}
                className="flex items-center gap-4 px-5 py-3 font-mono text-sm"
              >
                <span className={`text-lg ${getStatusColor(trace.status)}`}>
                  {getStatusIcon(trace.status)}
                </span>
                <span className="flex-1 truncate">{trace.task_description}</span>
                {trace.tool_calls && trace.tool_calls.length > 0 && (
                  <span className="hidden shrink-0 rounded bg-garl-blue/10 px-1.5 py-0.5 text-[10px] text-garl-blue sm:block">
                    {trace.tool_calls.length} tools
                  </span>
                )}
                {(trace.cost_usd ?? 0) > 0 && (
                  <span className="hidden text-xs text-garl-blue lg:block">
                    {formatCost(trace.cost_usd!)}
                  </span>
                )}
                <span
                  className={`text-xs font-semibold ${
                    trace.trust_delta >= 0 ? "text-garl-accent" : "text-garl-danger"
                  }`}
                >
                  {formatDelta(trace.trust_delta)}
                </span>
                <span className="text-xs text-garl-muted">
                  {formatDuration(trace.duration_ms)}
                </span>
                <span className="text-xs text-garl-muted">
                  {timeAgo(trace.created_at)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
