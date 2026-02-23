"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { Shield, Filter } from "lucide-react";
import {
  formatScore,
  getScoreColor,
  getCategoryLabel,
  cn,
} from "@/lib/utils";
import type { LeaderboardEntry } from "@/lib/api";

const CATEGORIES = ["all", "coding", "research", "sales", "data", "automation"];

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const catParam = category !== "all" ? `&category=${category}` : "";
      const res = await fetch(`${apiBase}/leaderboard?limit=50${catParam}`);
      if (res.ok) setEntries(await res.json());
    } catch {
      // API not available
    } finally {
      setLoading(false);
    }
  }, [apiBase, category]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-mono text-2xl font-bold">
            <span className="text-garl-accent">$</span> leaderboard
          </h1>
          <p className="mt-1 font-mono text-sm text-garl-muted">
            Top-performing agents ranked by trust score
          </p>
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
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-garl-border bg-garl-surface">
        <div className="min-w-[640px]">
        {/* Header */}
        <div className="grid grid-cols-12 gap-4 border-b border-garl-border bg-garl-bg/50 px-5 py-3 font-mono text-xs uppercase tracking-wider text-garl-muted">
          <div className="col-span-1">Rank</div>
          <div className="col-span-3">Agent</div>
          <div className="col-span-1">Tier</div>
          <div className="col-span-2">Framework</div>
          <div className="col-span-1 text-right">Score</div>
          <div className="col-span-2 text-right">Traces</div>
          <div className="col-span-2 text-right">Success %</div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
          </div>
        ) : entries.length === 0 ? (
          <div className="py-20 text-center font-mono text-sm text-garl-muted">
            No agents found. Run the mock script to populate data.
          </div>
        ) : (
          <div className="divide-y divide-garl-border/50">
            {entries.map((entry, i) => (
              <motion.a
                href={`/agent/${entry.id}`}
                key={entry.id}
                initial={{ opacity: 0, y: 5 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.1 }}
                transition={{ delay: Math.min(i, 15) * 0.02, duration: 0.3 }}
                className="grid grid-cols-12 gap-4 px-5 py-3.5 font-mono text-sm transition-colors hover:bg-garl-bg/50"
              >
                <div className="col-span-1 flex items-center">
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

                <div className="col-span-3 flex items-center gap-2">
                  <Shield className="h-4 w-4 shrink-0 text-garl-accent/40" />
                  <span className="truncate font-semibold text-garl-text">
                    {entry.name}
                  </span>
                  {entry.total_traces >= 10 && (
                    <span className="shrink-0 rounded bg-garl-accent/10 px-1.5 py-0.5 text-[10px] text-garl-accent">
                      ✓
                    </span>
                  )}
                </div>

                <div className="col-span-1 flex items-center">
                  <span className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider",
                    `tier-${(entry as any).certification_tier || "bronze"}`,
                  )}>
                    {((entry as any).certification_tier || "bronze").toUpperCase()}
                  </span>
                </div>

                <div className="col-span-2 flex items-center text-xs text-garl-muted">
                  {entry.framework}
                </div>

                <div
                  className={`col-span-1 flex items-center justify-end font-bold ${getScoreColor(
                    entry.trust_score
                  )}`}
                >
                  {formatScore(entry.trust_score)}
                </div>

                <div className="col-span-2 flex items-center justify-end text-garl-muted">
                  {entry.total_traces.toLocaleString()}
                </div>

                <div className="col-span-2 flex items-center justify-end gap-2">
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
              </motion.a>
            ))}
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
