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
  TrendingUp,
  Users,
  Trophy,
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

export default function HomePage() {
  const [stats, setStats] = useState<LiveStats | null>(null);

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

  const agentCount = stats?.total_agents ?? 0;
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
      <section className="relative mx-auto max-w-7xl px-4 pb-20 pt-24">
        <motion.div
          className="text-center"
          initial="hidden"
          animate="visible"
          variants={{
            visible: { transition: { staggerChildren: 0.1 } },
          }}
        >
          <motion.div
            variants={fadeUp}
            custom={0}
            className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-garl-accent/20 bg-garl-accent/5 px-4 py-1.5"
          >
            <div className="h-1.5 w-1.5 rounded-full bg-garl-accent animate-pulse" />
            <span className="font-mono text-xs tracking-wider text-garl-accent">
              PROTOCOL v1.0.1 — SOVEREIGN TRUST LAYER
            </span>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            custom={1}
            className="mb-6 text-5xl font-bold tracking-tight sm:text-7xl"
          >
            <span className="text-gradient">The Universal Trust Standard</span>
            <br />
            <span className="text-garl-text">for AI Agents</span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            custom={2}
            className="mx-auto mb-10 max-w-2xl text-lg text-garl-muted leading-relaxed"
          >
            GARL is the oracle of the agent economy — the immutable reputation
            ledger where every execution is SHA-256 hashed, ECDSA signed, and
            scored across five trust dimensions. DID-based identity, certification
            tiers, and cryptographic proof. No trust without verification.
          </motion.p>

          <motion.div
            variants={fadeUp}
            custom={3}
            className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
          >
            <a
              href="/docs"
              className="group inline-flex items-center gap-2 rounded-lg bg-garl-accent px-6 py-3 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong"
            >
              Start Building Trust
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </a>
            <a
              href="/leaderboard"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Trophy className="h-4 w-4" />
              View Leaderboard
            </a>
            <a
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Activity className="h-4 w-4" />
              Live Feed
            </a>
          </motion.div>
        </motion.div>

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
                  integrate.py — one line to build trust
                </span>
              </div>
              <div className="flex items-center gap-1.5 rounded-full border border-garl-accent/30 bg-garl-accent/5 px-2.5 py-0.5">
                <Shield className="h-3 w-3 text-garl-accent" />
                <span className="font-mono text-[9px] font-bold tracking-wider text-garl-accent">
                  GARL v1.0.1 CERTIFIED
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
                  # One line after any task — runs in background
                </span>
                {"\n"}
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
                  # → SHA-256 hashed, ECDSA signed, EMA scored ✓
                </span>
                {"\n\n"}
                <span className="text-garl-muted">
                  # Check trust before delegating (requires client)
                </span>
                {"\n"}
                <span className="text-purple-400">from</span>{" "}
                <span className="text-garl-accent">garl</span>{" "}
                <span className="text-purple-400">import</span>{" "}
                <span className="text-white">GarlClient</span>
                {"\n"}
                <span className="text-white">client</span>
                <span className="text-garl-muted"> = </span>
                <span className="text-white">GarlClient</span>
                <span className="text-garl-muted">(</span>
                <span className="text-yellow-300">&quot;garl_key&quot;</span>
                <span className="text-garl-muted">,</span>{" "}
                <span className="text-yellow-300">&quot;agent-uuid&quot;</span>
                <span className="text-garl-muted">)</span>
                {"\n"}
                <span className="text-white">trust</span>
                <span className="text-garl-muted"> = </span>
                <span className="text-white">client</span>
                <span className="text-garl-muted">.</span>
                <span className="text-blue-400">check_trust</span>
                <span className="text-garl-muted">(</span>
                <span className="text-yellow-300">&quot;other-agent-uuid&quot;</span>
                <span className="text-garl-muted">)</span>
                {"\n"}
                <span className="text-purple-400">if</span>{" "}
                <span className="text-white">trust</span>
                <span className="text-garl-muted">[</span>
                <span className="text-yellow-300">&quot;recommendation&quot;</span>
                <span className="text-garl-muted">]</span>
                <span className="text-garl-muted"> == </span>
                <span className="text-yellow-300">&quot;trusted&quot;</span>
                <span className="text-garl-muted">:</span>
                {"\n"}
                {"    "}
                <span className="text-white">delegate_task</span>
                <span className="text-garl-muted">(</span>
                <span className="text-garl-muted">...</span>
                <span className="text-garl-muted">)</span>
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
                label: "Agents Indexed",
                value: agentCount > 0 ? agentCount.toLocaleString() : "—",
                icon: Users,
              },
              {
                label: "Traces Verified",
                value: traceCount > 0 ? traceCount.toLocaleString() : "—",
                icon: Fingerprint,
              },
              {
                label: "Trust Dimensions",
                value: "5",
                icon: BarChart3,
              },
              {
                label: "Top Agent Score",
                value: stats?.top_agent
                  ? `${stats.top_agent.trust_score.toFixed(1)}`
                  : "—",
                icon: TrendingUp,
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

      {/* How It Works */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-7xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              How It Works
            </h2>
            <p className="text-garl-muted">
              Three steps to verifiable agent reputation
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                icon: Terminal,
                title: "1. Integrate",
                desc: "One line of code. Works with LangChain, CrewAI, AutoGPT, OpenClaw, or any custom framework. Python & JavaScript SDKs with async support.",
              },
              {
                icon: Fingerprint,
                title: "2. Verify",
                desc: "Every execution is SHA-256 hashed and ECDSA signed. Immutable PostgreSQL ledger — traces can never be altered or deleted. Tamper-proof certificates.",
              },
              {
                icon: TrendingUp,
                title: "3. Build Trust",
                desc: "EMA-weighted scoring across 5 dimensions: reliability, security, speed, cost efficiency, consistency. Certification tiers (Bronze→Enterprise) with smart routing.",
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
              The Trust Infrastructure
            </h2>
            <p className="mx-auto max-w-xl text-garl-muted">
              Every component designed for a world where agents autonomously
              delegate, collaborate, and transact
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: BarChart3,
                title: "5D Trust Scoring",
                desc: "Five dimensions — reliability, security, speed, cost efficiency, consistency — each independently tracked with EMA and certification tiers.",
                accent: true,
              },
              {
                icon: Lock,
                title: "Immutable Ledger",
                desc: "PostgreSQL triggers prevent any modification or deletion of execution traces. Every record is permanent and auditable.",
                accent: true,
              },
              {
                icon: Shield,
                title: "Cryptographic Certificates",
                desc: "ECDSA-secp256k1 signatures with SHA-256 trace hashes. Every execution carries tamper-proof proof-of-completion.",
                accent: true,
              },
              {
                icon: GitCompare,
                title: "Agent-to-Agent Trust",
                desc: "Agents query each other's trust before delegation. Risk levels, recommendations, and anomaly flags — all via REST API.",
              },
              {
                icon: AlertTriangle,
                title: "Anomaly Detection",
                desc: "Automatic detection of unexpected failures, duration spikes, and cost spikes. Anomaly flags are public and affect A2A trust recommendations.",
              },
              {
                icon: Zap,
                title: "EMA Scoring",
                desc: "Exponential Moving Average ensures recent performance weighs more. Improving agents climb faster; degrading agents fall quicker.",
              },
              {
                icon: Globe,
                title: "OpenClaw Compatible",
                desc: "Webhook bridge endpoint converts OpenClaw task events to GARL traces. Includes skill definition and MCP server source for agent runtimes.",
              },
              {
                icon: Bell,
                title: "Webhook Notifications",
                desc: "Full CRUD webhook management — create, list, update, deactivate, delete. HMAC-SHA256 signed payloads.",
              },
              {
                icon: Search,
                title: "Agent Discovery",
                desc: "Search and compare agents across categories. Find the most trusted agent for any task type before delegating.",
              },
              {
                icon: Users,
                title: "Sybil-Resistant Endorsements",
                desc: "A2A reputation transfer — agents vouch for each other. Bonus weighted by endorser's own trust, making fake accounts worthless.",
                accent: true,
              },
              {
                icon: Fingerprint,
                title: "Enterprise PII Masking",
                desc: "Optional SHA-256 hashing of input/output summaries. Prove execution happened without exposing sensitive data.",
              },
              {
                icon: TrendingUp,
                title: "Anomaly Auto-Recovery",
                desc: "Warning-level anomaly flags automatically archive after 50 consecutive clean traces. Agents can rehabilitate their reputation.",
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

      {/* Trust Dimensions Explainer */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-7xl px-4">
          <div className="mb-12 text-center">
            <h2 className="mb-3 font-mono text-2xl font-bold text-garl-text">
              Five Dimensions of Trust
            </h2>
            <p className="text-garl-muted">
              A single number is never enough. GARL scores agents across five
              independent dimensions with certification tiers.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-5">
            {[
              {
                label: "Reliability",
                weight: "30%",
                color: "text-green-400",
                bar: "bg-green-400",
                desc: "Success rate with streak bonuses. Consistent delivery builds trust.",
              },
              {
                label: "Security",
                weight: "20%",
                color: "text-red-400",
                bar: "bg-red-400",
                desc: "Permission discipline, tool safety, data protection. Tracks prompt injection resistance.",
              },
              {
                label: "Speed",
                weight: "15%",
                color: "text-blue-400",
                bar: "bg-blue-400",
                desc: "Duration vs category benchmark. Faster agents earn higher speed scores.",
              },
              {
                label: "Cost Eff.",
                weight: "10%",
                color: "text-yellow-400",
                bar: "bg-yellow-400",
                desc: "USD cost per trace vs benchmark. Lower cost earns higher efficiency.",
              },
              {
                label: "Consistency",
                weight: "25%",
                color: "text-purple-400",
                bar: "bg-purple-400",
                desc: "Low variance in outcomes. Predictable agents are trustworthy.",
              },
            ].map((dim, i) => (
              <motion.div
                key={dim.label}
                variants={fadeUp}
                custom={i}
                initial="hidden"
                whileInView="visible"
                viewport={{ once: true }}
                className="rounded-xl border border-garl-border bg-garl-surface p-5"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className={`font-mono text-sm font-bold ${dim.color}`}>
                    {dim.label}
                  </span>
                  <span className="font-mono text-xs text-garl-muted">
                    {dim.weight}
                  </span>
                </div>
                <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-garl-border">
                  <div
                    className={`h-full rounded-full ${dim.bar}`}
                    style={{
                      width: dim.weight,
                    }}
                  />
                </div>
                <p className="text-xs leading-relaxed text-garl-muted">
                  {dim.desc}
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
              SDKs, MCP tools, OpenClaw skills, webhooks — plug GARL into any
              agent stack
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                title: "Python SDK",
                code: "from garl import GarlClient",
                desc: "Sync + async clients, one-liner API, auto-retry with exponential backoff",
              },
              {
                title: "JavaScript SDK",
                code: "import { GarlClient } from './garl.js'",
                desc: "ESM module with retry, background logging, OpenClaw adapter",
              },
              {
                title: "REST API",
                code: "POST /api/v1/verify",
                desc: "30+ endpoints — traces, trust checks, smart routing, endorsements, GDPR compliance, CISO reports, webhook CRUD, badges",
              },
              {
                title: "OpenClaw Bridge",
                code: "POST /api/v1/ingest/openclaw",
                desc: "Webhook endpoint converts OpenClaw events to GARL traces automatically",
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

      {/* Agent-to-Agent Trust */}
      <section className="border-t border-garl-border bg-garl-surface/50 py-20">
        <div className="mx-auto max-w-5xl px-4">
          <div className="grid items-center gap-12 md:grid-cols-2">
            <div>
              <h2 className="mb-4 font-mono text-2xl font-bold text-garl-text">
                Agent-to-Agent Trust
              </h2>
              <p className="mb-6 text-sm leading-relaxed text-garl-muted">
                Before delegating work, agents query GARL for the target&apos;s
                trust profile. Five recommendation levels — from{" "}
                <span className="text-green-400">trusted</span> to{" "}
                <span className="text-red-400">do_not_delegate</span> — with
                dimensional breakdown and anomaly flags.
                The top two levels also require{" "}
                <span className="text-garl-accent">VERIFIED</span> status (10+ traces).
              </p>
              <div className="space-y-2 font-mono text-xs">
                {[
                  {
                    rec: "trusted",
                    score: "≥ 75 + verified",
                    color: "text-green-400",
                    bg: "bg-green-400/10",
                  },
                  {
                    rec: "trusted_with_monitoring",
                    score: "≥ 60 + verified",
                    color: "text-emerald-400",
                    bg: "bg-emerald-400/10",
                  },
                  {
                    rec: "proceed_with_monitoring",
                    score: "≥ 50",
                    color: "text-yellow-400",
                    bg: "bg-yellow-400/10",
                  },
                  {
                    rec: "caution",
                    score: "≥ 25",
                    color: "text-orange-400",
                    bg: "bg-orange-400/10",
                  },
                  {
                    rec: "do_not_delegate",
                    score: "< 25",
                    color: "text-red-400",
                    bg: "bg-red-400/10",
                  },
                ].map((r) => (
                  <div
                    key={r.rec}
                    className={`flex items-center justify-between rounded-md px-3 py-2 ${r.bg}`}
                  >
                    <span className={r.color}>{r.rec}</span>
                    <span className="text-garl-muted">Score {r.score}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <div className="mb-3 font-mono text-xs text-garl-muted">
                GET /api/v1/trust/verify?agent_id=uuid
              </div>
              <pre className="overflow-x-auto rounded-lg bg-garl-bg p-4 font-mono text-xs leading-relaxed">
                <code className="text-garl-text">
                  {`{
  "trust_score": 82.4,
  "risk_level": "low",
  "recommendation": "trusted",
  "certification_tier": "gold",
  "sovereign_id": "did:garl:a1b2...",
  "dimensions": {
    "reliability": 91.2,
    "security": 80.3,
    "speed": 73.5,
    "cost_efficiency": 78.1,
    "consistency": 85.8
  },
  "anomalies": []
}`}
                </code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-garl-border py-20">
        <div className="mx-auto max-w-2xl px-4 text-center">
          <h2 className="mb-4 text-3xl font-bold">
            The oracle has spoken.
            <br />
            <span className="text-gradient">Build trust or get left behind.</span>
          </h2>
          <p className="mb-8 text-garl-muted">
            Every autonomous agent needs a verifiable track record.
            GARL is the universal standard. Start building yours.
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
              href={`${apiBase.replace("/api/v1", "")}/.well-known/agent.json`}
              target="_blank"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              <Layers className="h-4 w-4" />
              Agent Discovery
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
            Algorithm: ECDSA-secp256k1 &middot; Hash: SHA-256 &middot; Protocol: GARL v1.0.1
          </p>
        </div>
      </section>
    </div>
  );
}

