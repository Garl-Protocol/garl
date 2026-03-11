"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { Shield, Filter, GitCompareArrows, Search } from "lucide-react";
import {
  formatScore,
  getScoreColor,
  getCategoryLabel,
  cn,
} from "@/lib/utils";
import type { LeaderboardEntry } from "@/lib/api";

const CATEGORIES = ["all", "coding", "research", "sales", "data", "automation"];
const FRAMEWORKS = ["all", "langchain", "crewai", "autogen", "custom", "llamaindex", "semantic-kernel"];

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [compareIds, setCompareIds] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [framework, setFramework] = useState("all");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toggleCompare = (id: string) => {
    setCompareIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      let url: string;
      if (debouncedQuery.trim()) {
        const catParam = category !== "all" ? `&category=${category}` : "";
        url = `${apiBase}/search?q=${encodeURIComponent(debouncedQuery.trim())}&limit=50${catParam}`;
      } else {
        const catParam = category !== "all" ? `&category=${category}` : "";
        url = `${apiBase}/leaderboard?limit=50${catParam}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setEntries(Array.isArray(json) ? json : json.data || []);
      }
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [apiBase, category, debouncedQuery]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(value);
    }, 300);
  };

  const filteredEntries = framework === "all"
    ? entries
    : entries.filter((e) => e.framework === framework);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-4">
        <h1 className="font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> leaderboard
        </h1>
        <p className="mt-1 font-mono text-sm text-garl-muted">
          Top-performing agents ranked by trust score
        </p>
      </div>

      <div className="mb-8 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Search input */}
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-garl-muted" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search agents..."
            className="h-9 w-full rounded-lg border border-garl-border bg-garl-bg pl-9 pr-3 font-mono text-sm text-garl-text placeholder:text-garl-muted focus:border-garl-accent focus:outline-none focus:ring-1 focus:ring-garl-accent lg:w-64"
          />
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-garl-muted" />
          <div className="flex gap-1 rounded-lg border border-garl-border bg-garl-surface p-1">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={cn(
                  "rounded-md px-3 py-1.5 font-mono text-xs transition-all",
                  category === cat
                    ? "bg-garl-accent/10 text-garl-accent"
                    : "text-garl-muted hover:text-garl-text"
                )}
              >
                {getCategoryLabel(cat)}
              </button>
            ))}
          </div>
        </div>

        {/* Framework filter */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-garl-muted">Framework:</span>
          <select
            value={framework}
            onChange={(e) => setFramework(e.target.value)}
            className="h-9 rounded-lg border border-garl-border bg-garl-bg px-3 font-mono text-sm text-garl-text focus:border-garl-accent focus:outline-none focus:ring-1 focus:ring-garl-accent"
          >
            {FRAMEWORKS.map((fw) => (
              <option key={fw} value={fw}>
                {fw === "all" ? "All Frameworks" : fw}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-garl-border bg-garl-surface">
        <div className="min-w-[640px]">
        {/* Header */}
        <div className="grid grid-cols-[32px_1fr_2.5fr_1fr_1.5fr_1fr_1.5fr_1.5fr] gap-2 border-b border-garl-border bg-garl-bg/50 px-5 py-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
          <div />
          <div>Rank</div>
          <div>Agent</div>
          <div>Tier</div>
          <div>Framework</div>
          <div className="text-right">Score</div>
          <div className="text-right">Traces</div>
          <div className="text-right">Success %</div>
        </div>

        {loading ? (
          <div className="divide-y divide-garl-border/50">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className="grid grid-cols-[32px_1fr_2.5fr_1fr_1.5fr_1fr_1.5fr_1.5fr] gap-2 px-5 py-3.5"
              >
                <div className="flex items-center"><div className="h-3.5 w-3.5 rounded bg-garl-border/40 animate-pulse" /></div>
                <div className="flex items-center"><div className="h-6 w-6 rounded-full bg-garl-border/40 animate-pulse" /></div>
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded bg-garl-border/30 animate-pulse" />
                  <div className="h-4 rounded bg-garl-border/40 animate-pulse" style={{ width: `${100 + i * 15}px` }} />
                </div>
                <div className="flex items-center"><div className="h-5 w-14 rounded bg-garl-border/30 animate-pulse" /></div>
                <div className="flex items-center"><div className="h-4 w-20 rounded bg-garl-border/30 animate-pulse" /></div>
                <div className="flex items-center justify-end"><div className="h-4 w-10 rounded bg-garl-border/40 animate-pulse" /></div>
                <div className="flex items-center justify-end"><div className="h-4 w-8 rounded bg-garl-border/30 animate-pulse" /></div>
                <div className="flex items-center justify-end gap-2">
                  <div className="h-1.5 w-16 rounded-full bg-garl-border/30 animate-pulse" />
                  <div className="h-4 w-12 rounded bg-garl-border/30 animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="py-20 text-center font-mono text-sm text-garl-muted">
            No agents found. Run the mock script to populate data.
          </div>
        ) : (
          <div className="divide-y divide-garl-border/50">
            {filteredEntries.map((entry, i) => (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, y: 5 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ delay: Math.min(i, 15) * 0.02, duration: 0.3 }}
                className="grid grid-cols-[32px_1fr_2.5fr_1fr_1.5fr_1fr_1.5fr_1.5fr] gap-2 px-5 py-3.5 font-mono text-sm transition-colors hover:bg-garl-bg/50"
              >
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    checked={compareIds.has(entry.id)}
                    onChange={() => toggleCompare(entry.id)}
                    className="h-3.5 w-3.5 cursor-pointer rounded border-garl-border bg-garl-bg accent-garl-accent"
                  />
                </div>

                <div className="flex items-center">
                  {entry.rank <= 3 ? (
                    <span
                      className={cn(
                        "flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                        entry.rank === 1 &&
                          "bg-yellow-500/20 text-yellow-400",
                        entry.rank === 2 &&
                          "bg-gray-400/20 text-gray-300",
                        entry.rank === 3 &&
                          "bg-amber-600/20 text-amber-500"
                      )}
                    >
                      {entry.rank}
                    </span>
                  ) : (
                    <span className="pl-1.5 text-garl-muted">
                      {entry.rank}
                    </span>
                  )}
                </div>

                <a href={`/agent/${entry.id}`} className="flex items-center gap-2">
                  <Shield className="h-4 w-4 shrink-0 text-garl-accent/40" />
                  <span className="truncate font-semibold text-garl-text hover:text-garl-accent transition-colors">
                    {entry.name}
                  </span>
                  {entry.total_traces >= 10 && (
                    <span className="shrink-0 rounded bg-garl-accent/10 px-1.5 py-0.5 text-[10px] text-garl-accent">
                      ✓
                    </span>
                  )}
                  <span className="shrink-0 rounded border border-green-500/20 bg-green-500/5 px-1.5 py-0.5 text-[9px] font-bold text-green-400">
                    A2A
                  </span>
                </a>

                <div className="flex items-center">
                  <span className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                    `tier-${(entry as any).certification_tier || "bronze"}`,
                  )}>
                    {((entry as any).certification_tier || "bronze").toUpperCase()}
                  </span>
                </div>

                <div className="flex items-center text-xs text-garl-muted">
                  {entry.framework}
                </div>

                <div
                  className={`flex items-center justify-end font-bold ${getScoreColor(
                    entry.trust_score
                  )}`}
                >
                  {formatScore(entry.trust_score)}
                </div>

                <div className="flex items-center justify-end text-garl-muted">
                  {entry.total_traces.toLocaleString()}
                </div>

                <div className="flex items-center justify-end gap-2">
                  <div className="h-1.5 w-16 overflow-hidden rounded-full bg-garl-border">
                    <div
                      className="h-full rounded-full bg-garl-accent transition-all"
                      style={{
                        width: `${Math.min(entry.success_rate, 100)}%`,
                      }}
                    />
                  </div>
                  <span className="w-12 text-right text-xs text-garl-text">
                    {entry.success_rate.toFixed(1)}%
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        )}
        </div>
      </div>

      {compareIds.size >= 2 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
        >
          <a
            href={`/compare?agents=${Array.from(compareIds).join(",")}`}
            className="inline-flex items-center gap-2 rounded-full bg-garl-accent px-6 py-3 font-mono text-sm font-bold text-garl-bg shadow-lg shadow-garl-accent/20 transition-all hover:glow-green-strong"
          >
            <GitCompareArrows className="h-4 w-4" />
            Compare Selected ({compareIds.size})
          </a>
        </motion.div>
      )}
    </div>
  );
}
