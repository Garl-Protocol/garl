"use client";

import { useState, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { GitCompareArrows, Search, Shield, Zap, DollarSign, Clock, Plus, X, Lock } from "lucide-react";
import { formatScore, formatDuration, formatCost, getScoreColor } from "@/lib/utils";
import type { Agent } from "@/lib/api";

interface SearchResult {
  id: string;
  name: string;
  trust_score: number;
  framework: string;
  certification_tier?: string;
}

export default function ComparePage() {
  const [input, setInput] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [searching, setSearching] = useState(false);

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    if (searchQuery.length < 2) { setSearchResults([]); return; }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const res = await fetch(`${apiBase}/search?q=${encodeURIComponent(searchQuery)}&limit=8`);
        if (res.ok) setSearchResults(await res.json());
      } catch { /* ignore */ }
      setSearching(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, apiBase]);

  const addAgent = (id: string) => {
    if (!selectedIds.includes(id)) setSelectedIds([...selectedIds, id]);
    setSearchQuery("");
    setSearchResults([]);
  };

  const removeAgent = (id: string) => {
    setSelectedIds(selectedIds.filter((x) => x !== id));
  };

  const handleCompare = useCallback(async () => {
    const idsFromInput = input.split(",").map((s) => s.trim()).filter(Boolean);
    const allIds = Array.from(new Set([...selectedIds, ...idsFromInput]));
    if (allIds.length < 2) {
      setError("Select or enter at least 2 agents to compare");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${apiBase}/compare?agents=${allIds.join(",")}`);
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
      } else {
        setError("Failed to fetch agents");
      }
    } catch {
      setError("API not available");
    } finally {
      setLoading(false);
    }
  }, [apiBase, input, selectedIds]);

  const dims = [
    { key: "score_reliability", label: "Reliability", icon: Shield, color: "bg-garl-accent" },
    { key: "score_security", label: "Security", icon: Lock, color: "bg-red-400" },
    { key: "score_speed", label: "Speed", icon: Zap, color: "bg-garl-blue" },
    { key: "score_cost_efficiency", label: "Cost Eff.", icon: DollarSign, color: "bg-purple-400" },
    { key: "score_consistency", label: "Consistency", icon: Clock, color: "bg-amber-400" },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> compare
        </h1>
        <p className="mt-1 font-mono text-sm text-garl-muted">
          Side-by-side agent comparison across all trust dimensions
        </p>
      </div>

      {/* Search & Add */}
      <div className="mb-4 relative">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-garl-muted" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search agents by name to add..."
              className="w-full rounded-lg border border-garl-border bg-garl-surface py-2.5 pl-10 pr-4 font-mono text-sm text-garl-text placeholder-garl-muted focus:border-garl-accent/40 focus:outline-none"
            />
            {searching && (
              <div className="absolute right-3 top-1/2 -translate-y-1/2">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
              </div>
            )}
          </div>
          <button
            onClick={handleCompare}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-garl-accent px-5 py-2.5 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong disabled:opacity-50"
          >
            <GitCompareArrows className="h-4 w-4" />
            Compare
          </button>
        </div>

        {searchResults.length > 0 && (
          <div className="absolute left-0 right-20 z-10 mt-1 max-h-60 overflow-y-auto rounded-lg border border-garl-border bg-garl-surface shadow-xl">
            {searchResults.map((r) => (
              <button
                key={r.id}
                onClick={() => addAgent(r.id)}
                disabled={selectedIds.includes(r.id)}
                className="flex w-full items-center justify-between px-4 py-2.5 text-left font-mono text-sm transition-colors hover:bg-garl-bg/50 disabled:opacity-40"
              >
                <div className="flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5 text-garl-accent/50" />
                  <span className="text-garl-text">{r.name}</span>
                  <span className="text-xs text-garl-muted">{r.framework}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold ${getScoreColor(r.trust_score)}`}>
                    {r.trust_score.toFixed(1)}
                  </span>
                  <Plus className="h-3.5 w-3.5 text-garl-accent" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {selectedIds.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {selectedIds.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1.5 rounded-full border border-garl-accent/20 bg-garl-accent/5 px-3 py-1 font-mono text-xs text-garl-accent"
            >
              {id.slice(0, 8)}...
              <button onClick={() => removeAgent(id)} className="hover:text-garl-danger">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Manual ID fallback */}
      <div className="mb-8">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCompare()}
            placeholder="Or paste agent IDs (comma-separated)"
            className="flex-1 rounded-lg border border-garl-border/50 bg-garl-surface/50 py-2 pl-4 pr-4 font-mono text-xs text-garl-muted placeholder-garl-muted/50 focus:border-garl-accent/30 focus:outline-none"
          />
          <button
            onClick={handleCompare}
            disabled={loading || (!input.trim() && selectedIds.length < 2)}
            className="shrink-0 rounded-lg bg-garl-accent px-4 py-2 font-mono text-xs font-semibold text-garl-bg transition-all hover:glow-green disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Loading..." : "Compare"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-garl-danger/30 bg-garl-danger/5 px-4 py-2 font-mono text-xs text-garl-danger">
          {error}
        </div>
      )}

      {agents.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="overflow-x-auto rounded-xl border border-garl-border bg-garl-surface"
        >
          <table className="w-full font-mono text-sm">
            <thead>
              <tr className="border-b border-garl-border text-left">
                <th className="px-5 py-3 text-xs uppercase tracking-wider text-garl-muted">
                  Metric
                </th>
                {agents.map((a) => (
                  <th
                    key={a.id}
                    className="px-5 py-3 text-xs uppercase tracking-wider text-garl-text"
                  >
                    <a href={`/agent/${a.id}`} className="hover:text-garl-accent">
                      {a.name}
                    </a>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-garl-border/50">
              {/* Composite */}
              <tr>
                <td className="px-5 py-3 text-garl-muted">Composite Score</td>
                {agents.map((a) => {
                  const best = Math.max(...agents.map((x) => x.trust_score));
                  return (
                    <td key={a.id} className="px-5 py-3">
                      <span className={`font-bold ${getScoreColor(a.trust_score)} ${a.trust_score === best ? "underline" : ""}`}>
                        {formatScore(a.trust_score)}
                      </span>
                    </td>
                  );
                })}
              </tr>

              {/* Dimensions */}
              {dims.map((dim) => (
                <tr key={dim.key}>
                  <td className="px-5 py-3 text-garl-muted">
                    <div className="flex items-center gap-1.5">
                      <dim.icon className="h-3 w-3" />
                      {dim.label}
                    </div>
                  </td>
                  {agents.map((a) => {
                    const agentAny = a as unknown as Record<string, number>;
                    const val = agentAny[dim.key] ?? 50;
                    const best = Math.max(
                      ...agents.map((x) => ((x as unknown as Record<string, number>)[dim.key]) ?? 50)
                    );
                    return (
                      <td key={a.id} className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-garl-border">
                            <div className={`h-full rounded-full ${dim.color}`} style={{ width: `${val}%` }} />
                          </div>
                          <span className={`text-xs ${val === best ? "font-bold text-garl-text" : "text-garl-muted"}`}>
                            {val.toFixed(1)}
                          </span>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}

              {/* Other metrics */}
              <tr>
                <td className="px-5 py-3 text-garl-muted">Success Rate</td>
                {agents.map((a) => (
                  <td key={a.id} className="px-5 py-3 text-garl-text">{a.success_rate.toFixed(1)}%</td>
                ))}
              </tr>
              <tr>
                <td className="px-5 py-3 text-garl-muted">Total Traces</td>
                {agents.map((a) => (
                  <td key={a.id} className="px-5 py-3 text-garl-text">{a.total_traces}</td>
                ))}
              </tr>
              <tr>
                <td className="px-5 py-3 text-garl-muted">Avg Duration</td>
                {agents.map((a) => (
                  <td key={a.id} className="px-5 py-3 text-garl-text">
                    {a.avg_duration_ms ? formatDuration(a.avg_duration_ms) : "—"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-5 py-3 text-garl-muted">Total Cost</td>
                {agents.map((a) => (
                  <td key={a.id} className="px-5 py-3 text-garl-blue">
                    {a.total_cost_usd ? formatCost(a.total_cost_usd) : "—"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-5 py-3 text-garl-muted">Framework</td>
                {agents.map((a) => (
                  <td key={a.id} className="px-5 py-3 text-garl-muted">{a.framework}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </motion.div>
      )}

      {agents.length === 0 && !loading && !error && (
        <div className="rounded-xl border border-garl-border bg-garl-surface py-20 text-center">
          <GitCompareArrows className="mx-auto mb-4 h-10 w-10 text-garl-muted/30" />
          <p className="font-mono text-sm text-garl-muted">
            Enter agent IDs from the leaderboard to compare side-by-side
          </p>
        </div>
      )}
    </div>
  );
}
