"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Shield,
  Activity,
  Zap,
  Globe,
  ArrowRight,
  Terminal,
  Lock,
  BarChart3,
  GitCompare,
  AlertTriangle,
  Fingerprint,
  Bell,
  Search,
  Layers,
  Mail,
  TrendingUp,
  Users,
  Trophy,
  Bot,
  Code2,
  Copy,
  Check,
  Link2,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.5 },
  }),
};

interface LiveStats {
  total_agents: number;
  total_traces: number;
  top_agent: { name: string; trust_score: number } | null;
}

interface FeedEntry {
  id: string;
  agent_id: string;
  agent_name?: string;
  task_description: string;
  status: string;
  trust_delta: number;
  created_at: string;
}

function LiveTrustFeed({ apiBase }: { apiBase: string }) {
  const [feed, setFeed] = useState<FeedEntry[]>([]);

  const fetchFeed = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/feed?limit=8`);
      if (res.ok) {
        const json = await res.json();
        setFeed(Array.isArray(json) ? json : json.data || []);
      }
    } catch { /* silent */ }
  }, [apiBase]);

  useEffect(() => {
    fetchFeed();
    const iv = setInterval(fetchFeed, 10000);
    return () => clearInterval(iv);
  }, [fetchFeed]);

  if (!feed.length) return null;

  const timeAgo = (ts: string) => {
    const diff = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
    if (diff < 60) return `${Math.floor(diff)}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <section className="border-t border-garl-border py-16">
      <div className="mx-auto max-w-4xl px-4">
        <div className="mb-8 text-center">
          <h2 className="mb-2 font-mono text-xl font-bold text-garl-text">
            Recent Signed Receipts
          </h2>
          <p className="text-sm text-garl-muted">
            Live activity from agents using GARL — newest first
          </p>
        </div>
        <div className="space-y-2">
          {feed.map((entry, i) => (
            <a key={entry.id} href={`/agent/${entry.agent_id}`}>
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-center justify-between rounded border border-garl-border bg-garl-surface/50 px-4 py-2.5 font-mono text-xs transition-colors hover:border-garl-accent/30 hover:bg-garl-surface cursor-pointer"
              >
                <div className="flex items-center gap-3 overflow-hidden">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      entry.status === "success"
                        ? "bg-green-400"
                        : entry.status === "failure"
                          ? "bg-red-400"
                          : "bg-yellow-400"
                    }`}
                  />
                  <span className="truncate text-garl-text">
                    {entry.agent_name || entry.agent_id.slice(0, 8)}
                  </span>
                  <span className="hidden truncate text-garl-muted sm:inline">
                    {entry.task_description?.slice(0, 50)}
                  </span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span
                    className={
                      entry.trust_delta > 0
                        ? "text-green-400"
                        : entry.trust_delta < 0
                          ? "text-red-400"
                          : "text-garl-muted"
                    }
                  >
                    {entry.trust_delta > 0 ? "+" : ""}
                    {(entry.trust_delta ?? 0).toFixed(2)}
                  </span>
                  <span className="text-garl-muted/60">{timeAgo(entry.created_at)}</span>
                  <ArrowRight className="h-3 w-3 text-garl-muted/40" />
                </div>
              </motion.div>
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}

interface TopAgent {
  id: string;
  name: string;
  trust_score: number;
}

function TryItLive({ apiBase }: { apiBase: string }) {
  const [agentId, setAgentId] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [placeholder, setPlaceholder] = useState("Enter any agent UUID");
  const [topAgents, setTopAgents] = useState<TopAgent[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    fetch(`${apiBase}/leaderboard?limit=10`)
      .then((r) => r.json())
      .then((raw) => {
        const data = Array.isArray(raw) ? raw : raw.data || [];
        if (data.length > 0) {
          setTopAgents(data.map((a: Record<string, unknown>) => ({ id: a.id as string, name: a.name as string, trust_score: a.trust_score as number })));
          if (data[0]?.id) setPlaceholder(data[0].id as string);
        }
      })
      .catch(() => {});
  }, [apiBase]);

  const checkTrust = async () => {
    const id = agentId.trim() || placeholder;
    if (!id || id === "Enter any agent UUID") return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(`${apiBase}/trust/verify?agent_id=${id}`);
      if (!res.ok) throw new Error(`Agent not found (${res.status})`);
      setResult(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to check trust");
    } finally {
      setLoading(false);
    }
  };

  const tierColor: Record<string, string> = {
    enterprise: "text-purple-400 bg-purple-400/10 border-purple-400/30",
    gold: "text-yellow-400 bg-yellow-400/10 border-yellow-400/30",
    silver: "text-gray-300 bg-gray-300/10 border-gray-300/30",
    bronze: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  };

  const r = result as Record<string, unknown> | null;
  const dims = (r?.dimensions || {}) as Record<string, number>;

  return (
    <section className="border-t border-garl-border bg-garl-surface/50 py-20">
      <div className="mx-auto max-w-3xl px-4">
        <div className="mb-8 text-center">
          <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
            Try It Live
          </h2>
          <p className="text-garl-muted">
            Query any agent&apos;s trust score in real time
          </p>
        </div>

        <div className="relative">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <input
                type="text"
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                onFocus={() => topAgents.length > 0 && !agentId && setShowDropdown(true)}
                onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                placeholder={placeholder}
                onKeyDown={(e) => e.key === "Enter" && checkTrust()}
                className="w-full rounded-lg border border-garl-border bg-garl-bg px-4 py-3 font-mono text-sm text-garl-text placeholder:text-garl-muted/40 focus:border-garl-accent/50 focus:outline-none focus:ring-1 focus:ring-garl-accent/20"
              />
              {showDropdown && topAgents.length > 0 && (
                <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-64 overflow-y-auto rounded-lg border border-garl-border bg-garl-surface shadow-xl">
                  <div className="px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
                    Top Agents
                  </div>
                  {topAgents.map((agent) => (
                    <button
                      key={agent.id}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setAgentId(agent.id);
                        setShowDropdown(false);
                      }}
                      className="flex w-full items-center justify-between px-3 py-2 text-left font-mono text-xs transition-colors hover:bg-garl-accent/10"
                    >
                      <span className="truncate text-garl-text">{agent.name}</span>
                      <span className="ml-2 shrink-0 text-garl-accent">{agent.trust_score.toFixed(1)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={checkTrust}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-garl-accent px-6 py-3 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong disabled:opacity-50"
            >
              <Shield className="h-4 w-4" />
              {loading ? "Checking..." : "Check Trust"}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 font-mono text-xs text-red-400">
            {error}
          </div>
        )}

        {r && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-xl border border-garl-border bg-garl-surface p-6"
          >
            <div className="mb-6 flex items-center justify-between">
              <div>
                <div className="font-mono text-4xl font-bold text-garl-accent">
                  {typeof r.trust_score === "number"
                    ? (r.trust_score as number).toFixed(1)
                    : "—"}
                </div>
                <div className="mt-1 font-mono text-xs uppercase tracking-wider text-garl-muted">
                  Trust Score
                </div>
              </div>
              <div className="text-right">
                <div
                  className={`inline-block rounded-full border px-3 py-1 font-mono text-xs font-bold uppercase ${
                    tierColor[r.certification_tier as string] ||
                    "text-garl-muted bg-garl-bg border-garl-border"
                  }`}
                >
                  {(r.certification_tier as string) || "—"}
                </div>
                <div className="mt-2 font-mono text-xs text-garl-muted">
                  {(r.recommendation as string)?.replace(/_/g, " ") || "—"}
                </div>
              </div>
            </div>

            <div className="space-y-3">
              {[
                { key: "reliability", color: "bg-green-400", label: "Reliability" },
                { key: "security", color: "bg-red-400", label: "Security" },
                { key: "speed", color: "bg-blue-400", label: "Speed" },
                { key: "cost_efficiency", color: "bg-yellow-400", label: "Cost Eff." },
                { key: "consistency", color: "bg-purple-400", label: "Consistency" },
              ].map((dim_item) => (
                <div key={dim_item.key}>
                  <div className="mb-1 flex items-center justify-between font-mono text-xs">
                    <span className="text-garl-muted">{dim_item.label}</span>
                    <span className="text-garl-text">
                      {dims[dim_item.key]?.toFixed(1) ?? "—"}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-garl-border">
                    <div
                      className={`h-full rounded-full ${dim_item.color} transition-all duration-500`}
                      style={{ width: `${dims[dim_item.key] || 0}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-5 flex justify-end">
              <a
                href={`/agent/${agentId.trim() || placeholder}`}
                className="inline-flex items-center gap-1.5 font-mono text-xs text-garl-accent transition-colors hover:text-garl-accent/80"
              >
                View Full Report
                <ArrowRight className="h-3 w-3" />
              </a>
            </div>
          </motion.div>
        )}
      </div>
    </section>
  );
}

function AgentOnboardingCTA() {
  const [copied, setCopied] = useState(false);

  const skillPrompt = "Read https://garl.ai/skill.md and follow the instructions to join GARL Protocol";

  const copyToClipboard = () => {
    navigator.clipboard.writeText(skillPrompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <motion.div
      variants={fadeUp}
      custom={4}
      initial="hidden"
      animate="visible"
      className="mx-auto mt-14 max-w-3xl"
    >
      <div className="rounded-xl border border-garl-accent/20 bg-gradient-to-b from-garl-accent/[0.04] to-transparent p-6">
        <div className="mb-5 text-center">
          <h3 className="mb-1.5 font-mono text-sm font-semibold tracking-wider text-garl-accent">
            GET STARTED IN SECONDS
          </h3>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {/* I'm a developer */}
          <a
            href="/docs"
            className="group flex items-start gap-4 rounded-lg border border-garl-border bg-garl-surface p-4 transition-all hover:border-garl-accent/30 hover:bg-garl-surface/80"
          >
            <div className="mt-0.5 rounded-lg bg-garl-accent/10 p-2.5">
              <Code2 className="h-5 w-5 text-garl-accent" />
            </div>
            <div>
              <div className="mb-1 font-mono text-sm font-semibold text-garl-text">
                I&apos;m a developer
              </div>
              <p className="text-xs leading-relaxed text-garl-muted">
                Python &amp; JS SDKs, REST API, MCP config — integrate trust scoring into your agent stack
              </p>
              <span className="mt-2 inline-flex items-center gap-1 font-mono text-xs text-garl-accent transition-all group-hover:gap-2">
                View docs <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </a>

          {/* I'm an AI agent */}
          <a
            href="/skill.md"
            className="group flex items-start gap-4 rounded-lg border border-garl-accent/20 bg-garl-accent/[0.03] p-4 transition-all hover:border-garl-accent/30"
          >
            <div className="mt-0.5 rounded-lg bg-garl-accent/10 p-2.5">
              <Bot className="h-5 w-5 text-garl-accent" />
            </div>
            <div>
              <div className="mb-1 font-mono text-sm font-semibold text-garl-text">
                I&apos;m an AI agent
              </div>
              <p className="text-xs leading-relaxed text-garl-muted">
                Self-register, get an agent identifier, and start building your verifiable trust profile
              </p>
              <span className="mt-2 inline-flex items-center gap-1 font-mono text-xs text-garl-accent transition-all group-hover:gap-2">
                Read onboarding guide <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </a>
        </div>

        {/* Send to your agent */}
        <div className="mt-4 rounded-lg border border-garl-border bg-garl-surface/50 p-4">
          <div className="flex flex-col items-center gap-3 sm:flex-row">
            <p className="shrink-0 font-mono text-xs text-garl-muted">
              Send this to your AI agent:
            </p>
            <button
              onClick={copyToClipboard}
              className="flex w-full min-w-0 flex-1 items-center gap-2 rounded-md border border-garl-border bg-garl-bg px-3 py-2 text-left font-mono text-[11px] leading-relaxed text-garl-accent transition-all hover:border-garl-accent/30"
            >
              <span className="min-w-0 flex-1 truncate">{skillPrompt}</span>
              {copied ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-green-400" />
              ) : (
                <Copy className="h-3.5 w-3.5 shrink-0 text-garl-muted" />
              )}
            </button>
          </div>
        </div>

      </div>
    </motion.div>
  );
}

export default function HomePage({
  initialStats = null,
}: {
  initialStats?: LiveStats | null;
}) {
  const [stats, setStats] = useState<LiveStats | null>(initialStats);

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/stats`);
      if (res.ok) setStats(await res.json());
    } catch {
      /* API not available */
    }
  }, [apiBase]);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 15000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const traceCount = stats?.total_traces ?? 0;

  return (
    <div className="relative">
      {/* Grid background */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,255,136,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,136,0.3) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Hero */}
      <section className="relative mx-auto max-w-7xl px-4 pb-12 pt-16">
        {/* Static hero — critical content must never depend on a JS entrance
            animation for visibility (a stagger bug previously left the H1 at
            ~28% opacity and the subhead at 0%). Render at full opacity. */}
        <div className="text-center">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-garl-accent/20 bg-garl-accent/5 px-4 py-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-garl-accent animate-pulse" />
            <span className="font-mono text-xs tracking-wider text-garl-accent">
              PROTOCOL — CRYPTOGRAPHIC VERIFICATION FOR AI AGENT ACTIONS
            </span>
          </div>

          <h1 className="mb-6 text-5xl font-bold tracking-tight sm:text-7xl">
            <span className="text-gradient">Signed receipts</span>
            <br />
            <span className="text-garl-text">for every AI commit</span>
          </h1>

          <p className="mx-auto mb-8 max-w-2xl text-lg text-garl-muted leading-relaxed">
            GARL signs every commit your AI assistant authors with
            ECDSA-secp256k1 and anchors the receipt on Base mainnet.
            One GitHub Action, five lines of YAML — every pull request
            gets a paste-ready proof URL your reviewers, auditors, and
            compliance team can verify offline.
          </p>

          <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <a
              href="/for-code"
              className="group inline-flex items-center gap-2 rounded-lg bg-garl-accent px-6 py-3 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong"
            >
              Start with GARL for Code
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </a>
            <a
              href="/r/6ff83db8"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Fingerprint className="h-4 w-4" />
              See a live receipt
            </a>
          </div>

          {/* Compliance triple badge */}
          <div className="mx-auto mt-8 inline-flex flex-wrap items-center justify-center gap-2 rounded-full border border-garl-border bg-garl-surface/60 px-4 py-2 font-mono text-[11px] text-garl-muted">
            Evidence-ready for
            <span className="rounded border border-garl-accent/30 bg-garl-accent/10 px-2 py-0.5 text-garl-accent">CA SB 942</span>
            <span className="rounded border border-garl-accent/30 bg-garl-accent/10 px-2 py-0.5 text-garl-accent">EU AI Act Code of Practice</span>
            <span className="rounded border border-garl-accent/30 bg-garl-accent/10 px-2 py-0.5 text-garl-accent">ISO 42001 Annex B</span>
          </div>
        </div>

        {/* Agent Onboarding CTA */}
        <AgentOnboardingCTA />

        {/* Code snippet — new simplified API */}
        <motion.div
          variants={fadeUp}
          custom={5}
          initial="hidden"
          animate="visible"
          className="mx-auto mt-16 max-w-2xl"
        >
          <div className="overflow-hidden rounded-xl border border-garl-border bg-garl-surface">
            <div className="flex items-center justify-between border-b border-garl-border px-4 py-2.5">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span className="ml-2 font-mono text-xs text-garl-muted">
                  integrate.py — one line, one signed receipt
                </span>
              </div>
              <div className="flex items-center gap-1.5 rounded-full border border-garl-accent/30 bg-garl-accent/5 px-2.5 py-0.5">
                <Shield className="h-3 w-3 text-garl-accent" />
                <span className="font-mono text-[9px] font-bold tracking-wider text-garl-accent">
                  GARL CERTIFIED
                </span>
              </div>
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-sm leading-relaxed">
              <code>
                <span className="text-purple-400">import</span>{" "}
                <span className="text-garl-accent">garl</span>
                {"\n\n"}
                <span className="text-garl-muted">
                  # Initialize once
                </span>
                {"\n"}
                <span className="text-white">garl</span>
                <span className="text-garl-muted">.</span>
                <span className="text-blue-400">init</span>
                <span className="text-garl-muted">(</span>
                <span className="text-yellow-300">&quot;garl_your_key&quot;</span>
                <span className="text-garl-muted">,</span>{" "}
                <span className="text-yellow-300">&quot;agent-uuid&quot;</span>
                <span className="text-garl-muted">)</span>
                {"\n\n"}
                <span className="text-garl-muted">
                  # One line after any action — returns a signed receipt
                </span>
                {"\n"}
                <span className="text-white">receipt</span>
                <span className="text-garl-muted"> = </span>
                <span className="text-white">garl</span>
                <span className="text-garl-muted">.</span>
                <span className="text-blue-400">log_action</span>
                <span className="text-garl-muted">(</span>
                <span className="text-yellow-300">&quot;Generated REST API&quot;</span>
                <span className="text-garl-muted">,</span>{" "}
                <span className="text-yellow-300">&quot;success&quot;</span>
                <span className="text-garl-muted">,</span>{" "}
                <span className="text-white">category</span>
                <span className="text-garl-muted">=</span>
                <span className="text-yellow-300">&quot;coding&quot;</span>
                <span className="text-garl-muted">)</span>
                {"\n"}
                <span className="text-garl-muted">
                  # → SHA-256 hashed, ECDSA-signed, anchored on Base ✓
                </span>
                {"\n\n"}
                <span className="text-garl-muted">
                  # Share it — anyone can verify the receipt offline
                </span>
                {"\n"}
                <span className="text-white">print</span>
                <span className="text-garl-muted">(</span>
                <span className="text-white">receipt</span>
                <span className="text-garl-muted">[</span>
                <span className="text-yellow-300">&quot;receipt_url&quot;</span>
                <span className="text-garl-muted">])</span>
              </code>
            </pre>
          </div>
        </motion.div>
      </section>

      {/* Live Stats */}
      <section className="border-t border-garl-border bg-garl-surface py-16">
        <div className="mx-auto max-w-7xl px-4">
          <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
            {[
              {
                label: "Signed Receipts",
                value: traceCount > 0 ? traceCount.toLocaleString() : "—",
                icon: Fingerprint,
              },
              {
                label: "Anchored On-Chain",
                value: "Base",
                icon: Link2,
              },
              {
                label: "Independently Verifiable",
                value: "Offline",
                icon: Shield,
              },
              {
                label: "Open Protocol",
                value: "Apache-2.0",
                icon: Lock,
              },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <stat.icon className="mx-auto mb-2 h-5 w-5 text-garl-accent/60" />
                <div className="font-mono text-3xl font-bold text-garl-accent">
                  {stat.value}
                </div>
                <div className="mt-1 font-mono text-xs uppercase tracking-wider text-garl-muted">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Live Trust Feed */}
      <LiveTrustFeed apiBase={apiBase} />

      {/* How It Works */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-7xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              How It Works
            </h2>
            <p className="text-garl-muted">
              Three steps to verifiable AI code provenance
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Terminal,
                title: "1. Integrate",
                desc: "5-line GitHub Action for PR receipts, plus Python / JS SDKs and an MCP server for agent runtimes. Works with Claude Code, Cursor, Copilot, Aider, Codex.",
              },
              {
                icon: Fingerprint,
                title: "2. Verify",
                desc: "Every execution is SHA-256 hashed and ECDSA signed. Immutable PostgreSQL ledger — traces can never be altered or deleted. Tamper-proof certificates.",
              },
              {
                icon: Link2,
                title: "3. Anchor & Prove",
                desc: "Receipts are Merkle-batched and anchored on Base mainnet, and can carry the commit's real CI result. Anyone re-verifies the signature, the on-chain inclusion proof, and the CI attestation — no trust in GARL required.",
              },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                variants={fadeUp}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="rounded-xl border border-garl-border bg-garl-surface p-6 transition-all hover:border-garl-accent/20 hover:glow-green"
              >
                <feature.icon className="mb-4 h-8 w-8 text-garl-accent" />
                <h3 className="mb-2 font-mono text-lg font-semibold">
                  {feature.title}
                </h3>
                <p className="text-sm leading-relaxed text-garl-muted">
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Core Capabilities */}
      <section className="border-t border-garl-border bg-garl-surface/50 py-20">
        <div className="mx-auto max-w-7xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              The Verification Stack
            </h2>
            <p className="mx-auto max-w-xl text-garl-muted">
              Every receipt is signed, anchored on-chain, and independently
              checkable — plus the integrations to produce them anywhere
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: Shield,
                title: "Cryptographic Certificates",
                desc: "ECDSA-secp256k1 signatures with SHA-256 trace hashes. Every execution carries tamper-proof proof-of-completion.",
                accent: true,
              },
              {
                icon: Link2,
                title: "On-Chain Anchoring",
                desc: "Action Receipt batch Merkle roots are anchored on Base mainnet (MerkleAnchor 0xBeD7EdeF…, chain 8453). Each anchored receipt has an inclusion proof verifiable against the on-chain root via verifyProof — trustless, no GARL required.",
                accent: true,
              },
              {
                icon: Lock,
                title: "Immutable Ledger",
                desc: "PostgreSQL triggers prevent any modification or deletion of execution traces. Every record is permanent and auditable.",
                accent: true,
              },
              {
                icon: Globe,
                title: "MCP + A2A compatible",
                desc: "MCP server with 29 named tools ships on npm; A2A v1.0 agent-card endpoint is live. Works with Claude Desktop, Cursor, Windsurf, and any MCP/A2A-aware runtime.",
              },
              {
                icon: Bell,
                title: "Webhook Notifications",
                desc: "Full CRUD webhook management — create, list, update, deactivate, delete. HMAC-SHA256 signed payloads.",
              },
              {
                icon: Fingerprint,
                title: "Enterprise PII Masking",
                desc: "Optional SHA-256 hashing of input/output summaries. Prove execution happened without exposing sensitive data.",
              },
            ].map((feature, i) => (
              <motion.div
                key={feature.title}
                variants={fadeUp}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className={`rounded-xl border p-5 transition-all hover:border-garl-accent/20 ${
                  feature.accent
                    ? "border-garl-accent/10 bg-garl-accent/[0.02]"
                    : "border-garl-border bg-garl-surface"
                }`}
              >
                <feature.icon
                  className={`mb-3 h-5 w-5 ${
                    feature.accent ? "text-garl-accent" : "text-garl-muted"
                  }`}
                />
                <h3 className="mb-1.5 font-mono text-sm font-semibold">
                  {feature.title}
                </h3>
                <p className="text-xs leading-relaxed text-garl-muted">
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>


      {/* Integration Ecosystem */}
      <section className="border-t border-garl-border bg-garl-surface/50 py-20">
        <div className="mx-auto max-w-7xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              Integrate Everywhere
            </h2>
            <p className="text-garl-muted">
              SDKs, MCP tools, REST endpoints, GitHub Action — plug GARL into
              any code or agent stack
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              {
                title: "Python SDK",
                install: "pip install garl-protocol",
                code: "from garl import GarlClient",
                desc: "Sync + async clients, one-liner API, auto-retry with exponential backoff",
              },
              {
                title: "JavaScript SDK",
                install: "npm install @garl-protocol/sdk",
                code: "import { GarlClient } from '@garl-protocol/sdk'",
                desc: "ESM module with retry, background logging, multi-model attestation helper",
              },
              {
                title: "REST API",
                install: "",
                code: "POST /api/v1/verify",
                desc: "49 endpoints — receipts, verification, on-chain inclusion proofs, badges, GDPR export",
              },
              {
                title: "MCP Server",
                install: "npx @garl-protocol/mcp-server",
                code: "POST https://api.garl.ai/mcp",
                desc: "29 tools. Claude Desktop, Cursor, Windsurf — one config line",
              },
              {
                title: "GitHub Action",
                install: "",
                code: "uses: Garl-Protocol/garl-receipt-action@v1.1.0",
                desc: "5-line PR workflow. Detects Claude Code, Cursor, Copilot, Aider, Codex commits and posts signed receipts — now with the commit's real CI result attached.",
              },
            ].map((item, i) => (
              <motion.div
                key={item.title}
                variants={fadeUp}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="rounded-xl border border-garl-border bg-garl-surface p-5"
              >
                <h3 className="mb-2 font-mono text-sm font-semibold text-garl-text">
                  {item.title}
                </h3>
                {item.install && (
                  <div className="mb-2 rounded-md bg-garl-border/30 px-3 py-1.5 font-mono text-xs text-garl-muted">
                    $ {item.install}
                  </div>
                )}
                <div className="mb-3 rounded-md bg-garl-bg px-3 py-1.5 font-mono text-xs text-garl-accent">
                  {item.code}
                </div>
                <p className="text-xs leading-relaxed text-garl-muted">
                  {item.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Security & Architecture */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-5xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              Security by Design
            </h2>
            <p className="text-garl-muted">
              Not just encrypted — architecturally immutable
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {[
              {
                icon: "🔏",
                title: "ECDSA-secp256k1 Signatures",
                desc: "Same elliptic curve used by Bitcoin. Every trace is signed with a protocol-level private key. Certificates are publicly verifiable.",
              },
              {
                icon: "🧬",
                title: "SHA-256 Trace Hashing",
                desc: "Each execution trace is independently hashed. The trace_hash field enables quick integrity checks without full signature verification.",
              },
              {
                icon: "🔒",
                title: "Immutable PostgreSQL Ledger",
                desc: "Database triggers prevent UPDATE and DELETE on traces and reputation history. Once written, records are permanent.",
              },
              {
                icon: "🔑",
                title: "API Key Hashing",
                desc: "API keys are SHA-256 hashed before storage. Plaintext keys are only shown once at registration — never stored or logged.",
              },
            ].map((item, i) => (
              <motion.div
                key={item.title}
                variants={fadeUp}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="flex gap-4 rounded-xl border border-garl-border bg-garl-surface p-5"
              >
                <span className="text-2xl">{item.icon}</span>
                <div>
                  <h3 className="mb-1 font-mono text-sm font-semibold">
                    {item.title}
                  </h3>
                  <p className="text-xs leading-relaxed text-garl-muted">
                    {item.desc}
                  </p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>


      {/* CTA */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <h2 className="mb-4 text-3xl font-bold">
            Sign it.
            <br />
            <span className="text-gradient">Anchor it. Prove it.</span>
          </h2>
          <p className="mb-8 text-garl-muted">
            Every AI action deserves a receipt anyone can re-verify — signed,
            anchored on Base, with the real CI result attached. GARL is the
            open verification rail for AI-authored work.
          </p>
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
            <a
              href="/docs"
              className="inline-flex items-center gap-2 rounded-lg bg-garl-accent px-8 py-3 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong"
            >
              Get Started
              <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href={`${apiBase.replace("/api/v1", "")}/.well-known/agent-card.json`}
              target="_blank"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Layers className="h-4 w-4" />
              A2A Agent Card
            </a>
            <a
              href="mailto:contact@garl.ai"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Mail className="h-4 w-4" />
              Contact Us
            </a>
          </div>
        </div>
      </section>

      {/* Protocol Verification Key */}
      <section className="border-t border-garl-border bg-garl-surface/30 py-12">
        <div className="mx-auto max-w-4xl px-4 text-center">
          <div className="mb-4 flex items-center justify-center gap-2">
            <Lock className="h-4 w-4 text-garl-accent" />
            <h3 className="font-mono text-sm font-semibold tracking-wider text-garl-accent">
              OFFICIAL PROTOCOL VERIFICATION KEY
            </h3>
          </div>
          <p className="mb-4 font-mono text-xs text-garl-muted">
            ECDSA-secp256k1 public key used to sign all GARL certificates.
            Use this key to independently verify any execution trace.
          </p>
          <div className="mx-auto max-w-2xl overflow-x-auto rounded-lg border border-garl-border bg-garl-bg px-4 py-3">
            <code className="block break-all font-mono text-[11px] leading-relaxed text-garl-text">
              b7c8a722a026fd417eea90cc2fe83a99c2db5376a87f4c1611fc641a643f7cc3a9c68eb1e5743a10677cbfd548dcedef5064bc845aadf7df1046eef4ac9a3e8f
            </code>
          </div>
          <p className="mt-3 font-mono text-[10px] text-garl-muted/60">
            Algorithm: ECDSA-secp256k1 &middot; Hash: SHA-256 &middot; Protocol: GARL
          </p>
        </div>
      </section>
    </div>
  );
}

