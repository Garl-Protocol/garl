import type { Metadata } from "next";
import {
  Users,
  Receipt,
  KeyRound,
  Undo2,
  ShieldCheck,
  ShieldAlert,
  ShieldX,
  Activity,
} from "lucide-react";

export const dynamic = "force-dynamic";
export const revalidate = 60;

const API_BASE =
  process.env.GARL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.garl.ai/api/v1";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://garl.ai";

type PublicStats = {
  total_agents: number;
  total_traces: number;
  active_agents_7d: number;
  protocol_version: string;
  top_agent: {
    name: string;
    trust_score: number;
    certification_tier: string;
  } | null;
  wave2: {
    action_receipts: {
      total: number;
      by_side_effect: {
        none: number;
        reversible: number;
        irreversible: number;
      };
    };
    capability_tokens_issued: number;
    compensations_recorded: number;
  };
  capability_tokens_active: number;
  compensations_succeeded: number;
};

export const metadata: Metadata = {
  title: "Stats · GARL Protocol",
  description:
    "Live counts: signed receipts, active agents, capability tokens, undo invocations.",
  alternates: { canonical: `${SITE_URL}/stats` },
  openGraph: {
    title: "GARL Protocol — Live Stats",
    description:
      "Cryptographic verification for AI agent actions, in numbers.",
    url: `${SITE_URL}/stats`,
    siteName: "GARL Protocol",
    type: "website",
  },
};

async function fetchStats(): Promise<PublicStats | null> {
  try {
    const res = await fetch(`${API_BASE}/public-stats`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicStats;
  } catch {
    return null;
  }
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString("en-US");
}

export default async function StatsPage() {
  const stats = await fetchStats();
  if (!stats) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16 text-center">
        <h1 className="font-mono text-2xl text-garl-text">Stats unavailable</h1>
        <p className="mt-4 font-mono text-sm text-garl-muted">
          The public-stats endpoint is unreachable right now. Try{" "}
          <a
            className="underline hover:text-garl-accent"
            href="https://api.garl.ai/api/v1/public-stats"
          >
            /api/v1/public-stats
          </a>{" "}
          directly.
        </p>
      </div>
    );
  }

  const totalReceipts = stats.total_traces + stats.wave2.action_receipts.total;
  const sideEffect = stats.wave2.action_receipts.by_side_effect;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <header className="mb-12">
        <p className="mb-2 font-mono text-[11px] uppercase tracking-wider text-garl-muted">
          Live · revalidates every 60 seconds
        </p>
        <h1 className="mb-3 font-mono text-3xl font-bold text-garl-text">
          GARL Protocol — by the numbers
        </h1>
        <p className="font-mono text-sm text-garl-muted">
          Protocol v{stats.protocol_version}. Counts pulled from the canonical
          registry at <code className="text-garl-text">api.garl.ai</code>.
        </p>
      </header>

      {/* Top-line counters */}
      <section className="mb-10 grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        <Counter
          icon={Receipt}
          label="Signed receipts"
          value={fmt(totalReceipts)}
          sub={`${fmt(stats.total_traces)} legacy + ${fmt(stats.wave2.action_receipts.total)} Action v0.1`}
        />
        <Counter
          icon={Users}
          label="Registered agents"
          value={fmt(stats.total_agents)}
          sub={`${fmt(stats.active_agents_7d)} active in last 7d`}
        />
        <Counter
          icon={KeyRound}
          label="Capability tokens"
          value={fmt(stats.wave2.capability_tokens_issued)}
          sub={`${fmt(stats.capability_tokens_active)} currently active`}
        />
        <Counter
          icon={Undo2}
          label="Undo invocations"
          value={fmt(stats.wave2.compensations_recorded)}
          sub={`${fmt(stats.compensations_succeeded)} succeeded`}
        />
      </section>

      {/* Side-effect breakdown */}
      <section className="mb-10">
        <h2 className="mb-4 font-mono text-base text-garl-text">
          Action Receipt v0.1 — by side-effect class
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <SideEffectCard
            icon={ShieldCheck}
            label="None"
            count={sideEffect.none}
            tone="border-emerald-500/30 bg-emerald-500/[0.05] text-emerald-300"
            help="Read-only. No state changed."
          />
          <SideEffectCard
            icon={ShieldAlert}
            label="Reversible"
            count={sideEffect.reversible}
            tone="border-amber-500/30 bg-amber-500/[0.05] text-amber-300"
            help="Mutation that one follow-up action cancels."
          />
          <SideEffectCard
            icon={ShieldX}
            label="Irreversible"
            count={sideEffect.irreversible}
            tone="border-red-500/30 bg-red-500/[0.05] text-red-300"
            help="No automatic undo path."
          />
        </div>
      </section>

      {/* Top agent (legacy spotlight) */}
      {stats.top_agent && (
        <section className="mb-10 rounded-xl border border-garl-border bg-garl-surface p-5">
          <div className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
            <Activity className="h-3 w-3" />
            Top trust score
          </div>
          <div className="font-mono text-lg text-garl-text">
            {stats.top_agent.name}{" "}
            <span className="text-garl-muted">
              · {stats.top_agent.trust_score.toFixed(2)} ·{" "}
              {stats.top_agent.certification_tier}
            </span>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="border-t border-garl-border pt-6 font-mono text-xs text-garl-muted">
        <p className="mb-2">
          GARL is open-source (Apache 2.0). The full surface lives at{" "}
          <a className="underline hover:text-garl-accent" href="https://github.com/Garl-Protocol/garl">
            github.com/Garl-Protocol/garl
          </a>
          .
        </p>
        <p>
          Want the same numbers as JSON for your own dashboard?{" "}
          <code className="text-garl-text">GET /api/v1/public-stats</code> — public, no auth.
        </p>
      </footer>
    </div>
  );
}

function Counter({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: typeof Receipt;
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
      <div className="mb-3 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mb-1 font-mono text-3xl font-bold text-garl-text tabular-nums">
        {value}
      </div>
      <div className="font-mono text-[11px] text-garl-muted">{sub}</div>
    </div>
  );
}

function SideEffectCard({
  icon: Icon,
  label,
  count,
  tone,
  help,
}: {
  icon: typeof ShieldCheck;
  label: string;
  count: number;
  tone: string;
  help: string;
}) {
  return (
    <div className={`rounded-xl border p-5 ${tone}`}>
      <div className="mb-3 inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mb-1 font-mono text-2xl font-bold tabular-nums">
        {fmt(count)}
      </div>
      <div className="font-mono text-[11px] opacity-80">{help}</div>
    </div>
  );
}
