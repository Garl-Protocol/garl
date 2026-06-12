"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Plus,
  X,
  AlertTriangle,
  Activity,
  ShieldCheck,
  Loader2,
} from "lucide-react";

type Agent = {
  id: string;
  name: string;
  framework?: string;
  trust_score?: number;
  total_traces?: number;
  success_rate?: number;
  certification_tier?: string;
  last_trace_at?: string | null;
  anomaly_flags?: Array<{ type?: string; severity?: string; message?: string }>;
};

const tierColor: Record<string, string> = {
  gold: "border-yellow-400/30 bg-yellow-400/10 text-yellow-300",
  silver: "border-slate-300/30 bg-slate-300/10 text-slate-200",
  bronze: "border-orange-400/30 bg-orange-400/10 text-orange-300",
  enterprise: "border-garl-accent/30 bg-garl-accent/10 text-garl-accent",
};

function timeAgo(ts?: string | null): string {
  if (!ts) return "no activity yet";
  const diff = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function MyAgentsDashboard() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiKey, setApiKey] = useState("");
  const [claiming, setClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/account/agents", { cache: "no-store" });
      if (res.ok) {
        const json = await res.json();
        setAgents(Array.isArray(json.agents) ? json.agents : []);
      }
    } catch {
      /* leave as-is */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const claim = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const key = apiKey.trim();
      if (!key || claiming) return;
      setClaiming(true);
      setError(null);
      try {
        const res = await fetch("/api/account/claim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ apiKey: key }),
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          setError(json?.error || "Couldn't claim that agent.");
        } else {
          setApiKey("");
          await load();
        }
      } catch {
        setError("Network error. Try again.");
      } finally {
        setClaiming(false);
      }
    },
    [apiKey, claiming, load],
  );

  const unclaim = useCallback(
    async (agentId: string) => {
      try {
        await fetch("/api/account/unclaim", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agentId }),
        });
        setAgents((prev) => prev.filter((a) => a.id !== agentId));
      } catch {
        /* ignore */
      }
    },
    [],
  );

  return (
    <div>
      {/* Claim form */}
      <form
        onSubmit={claim}
        className="mb-6 rounded-lg border border-garl-border bg-garl-bg p-4"
      >
        <label className="mb-2 block font-mono text-xs font-semibold text-garl-text">
          Link an agent
        </label>
        <p className="mb-3 text-xs leading-relaxed text-garl-muted">
          Paste an agent&apos;s API key (the <code className="text-garl-accent">garl_…</code>{" "}
          key from registration). The key proves you control the agent — it&apos;s
          verified, never stored here.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="garl_..."
            autoComplete="off"
            className="min-w-0 flex-1 rounded-md border border-garl-border bg-garl-surface px-3 py-2 font-mono text-sm text-garl-text placeholder:text-garl-muted/50 focus:border-garl-accent/40 focus:outline-none"
          />
          <button
            type="submit"
            disabled={claiming || !apiKey.trim()}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-garl-accent px-4 py-2 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong disabled:opacity-50"
          >
            {claiming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            Link agent
          </button>
        </div>
        {error && (
          <p className="mt-2 font-mono text-xs text-red-400">{error}</p>
        )}
      </form>

      {/* Agents list */}
      {loading ? (
        <div className="flex items-center gap-2 py-8 font-mono text-xs text-garl-muted">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading your agents…
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-lg border border-dashed border-garl-border bg-garl-surface/40 p-6 text-center">
          <p className="text-sm text-garl-muted">
            No agents linked yet. Paste an agent&apos;s API key above, or{" "}
            <a href="/connect" className="text-garl-accent hover:underline">
              connect a new agent
            </a>
            .
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {agents.map((a) => {
            const anomalies = (a.anomaly_flags || []).filter(Boolean);
            const tier = (a.certification_tier || "bronze").toLowerCase();
            return (
              <div
                key={a.id}
                className="group relative rounded-xl border border-garl-border bg-garl-surface p-4 transition-all hover:border-garl-accent/30"
              >
                <button
                  onClick={() => unclaim(a.id)}
                  aria-label="Unlink agent"
                  title="Unlink from this account"
                  className="absolute right-2 top-2 rounded-md border border-transparent p-1 text-garl-muted/50 transition-colors hover:border-garl-border hover:text-garl-text"
                >
                  <X className="h-3.5 w-3.5" />
                </button>

                <a href={`/agent/${a.id}`} className="block pr-6">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="truncate font-mono text-sm font-semibold text-garl-text">
                      {a.name}
                    </span>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
                        tierColor[tier] || tierColor.bronze
                      }`}
                    >
                      {tier}
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 font-mono text-xs">
                    <div>
                      <div className="flex items-center gap-1 text-garl-muted">
                        <ShieldCheck className="h-3 w-3" /> trust
                      </div>
                      <div className="text-garl-text">
                        {a.trust_score != null ? a.trust_score.toFixed(1) : "—"}
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center gap-1 text-garl-muted">
                        <Activity className="h-3 w-3" /> traces
                      </div>
                      <div className="text-garl-text">
                        {(a.total_traces ?? 0).toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-garl-muted">success</div>
                      <div className="text-garl-text">
                        {a.success_rate != null ? `${a.success_rate.toFixed(0)}%` : "—"}
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 flex items-center justify-between font-mono text-[11px] text-garl-muted/70">
                    <span>last active {timeAgo(a.last_trace_at)}</span>
                    {anomalies.length > 0 && (
                      <span className="inline-flex items-center gap-1 text-yellow-400">
                        <AlertTriangle className="h-3 w-3" />
                        {anomalies.length} anomaly
                        {anomalies.length > 1 ? "ies" : ""}
                      </span>
                    )}
                  </div>

                  <span className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] text-garl-accent opacity-0 transition-opacity group-hover:opacity-100">
                    View activity <ArrowRight className="h-3 w-3" />
                  </span>
                </a>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
