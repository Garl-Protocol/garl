"use client";

import { useState, useEffect, useCallback } from "react";
import {
  ArrowRight,
  Bot,
  Check,
  Copy,
  Terminal,
  Fingerprint,
  Link2,
  Boxes,
} from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

// One-paste quickstart: register an agent and mint a first receipt in a single
// run. Front-loaded on the page so a cold visitor gets a real, shareable receipt
// before wading through 10 integration tabs. A random name suffix avoids the
// 409 "name already taken" collision when two people paste it. Needs curl + jq.
const INSTANT_SNIPPET = `# 60s: register an agent, mint your first receipt, print the public proof URL
RESP=$(curl -s ${API_BASE}/agents/auto-register \\
  -H 'Content-Type: application/json' \\
  -d "{\\"name\\":\\"demo-$RANDOM\\",\\"framework\\":\\"custom\\",\\"category\\":\\"automation\\"}")
ID=$(echo "$RESP" | jq -r .id); KEY=$(echo "$RESP" | jq -r .api_key)

curl -s ${API_BASE}/verify \\
  -H "x-api-key: $KEY" -H 'Content-Type: application/json' \\
  -d "{\\"agent_id\\":\\"$ID\\",\\"task_description\\":\\"My first GARL receipt\\",\\"status\\":\\"success\\",\\"duration_ms\\":1200}" \\
  | jq '{receipt_url, short_hash, trust_delta}'
# -> open receipt_url: signed, anchored on Base, verifiable by anyone`;

// ── Integration paths ────────────────────────────────────────────────
// Honesty rule: only show paths that actually work TODAY. The REST API,
// Python/JS SDKs, MCP server and GitHub Action are live. Framework entries
// show how to call the live SDK from inside that framework's own hook —
// a real pattern, not a promised native adapter. Native OTLP ingest +
// first-class OpenClaw/Hermes plugins are flagged as roadmap, not claimed.

type Integration = {
  key: string;
  label: string;
  blurb: string;
  available: "now" | "via-sdk" | "roadmap";
  snippet: string;
  lang: string;
};

const INTEGRATIONS: Integration[] = [
  {
    key: "rest",
    label: "REST API",
    blurb: "Any language, any runtime. One POST after each action.",
    available: "now",
    lang: "bash",
    snippet: `curl -X POST ${API_BASE}/verify \\
  -H "x-api-key: garl_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "your-agent-uuid",
    "task_description": "Closed support ticket #4821",
    "status": "success",
    "duration_ms": 1840,
    "cost_usd": 0.012
  }'
# -> returns a signed receipt + a public verify URL`,
  },
  {
    key: "python",
    label: "Python SDK",
    blurb: "Sync + async, one-liner, auto-retry.",
    available: "now",
    lang: "python",
    snippet: `pip install garl-protocol

import garl
garl.init("garl_your_key", "your-agent-uuid")

# one line after any action -> signed, anchored receipt
receipt = garl.log_action("Closed ticket #4821", "success",
                          category="automation", cost_usd=0.012)
print(receipt["receipt_url"])`,
  },
  {
    key: "js",
    label: "JavaScript SDK",
    blurb: "ESM, retry, background logging.",
    available: "now",
    lang: "javascript",
    snippet: `npm install @garl-protocol/sdk

import { GarlClient } from "@garl-protocol/sdk";
const garl = new GarlClient("garl_your_key", "your-agent-uuid");

const receipt = await garl.verify({
  task: "Closed ticket #4821",
  status: "success",
  durationMs: 1840,
  costUsd: 0.012,
});
console.log(receipt.receipt_url);`,
  },
  {
    key: "mcp",
    label: "MCP server",
    blurb: "Claude Desktop, Cursor, Windsurf — one config line, no code.",
    available: "now",
    lang: "json",
    snippet: `// claude_desktop_config.json (or Cursor / Windsurf MCP config)
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["@garl-protocol/mcp-server"],
      "env": {
        "GARL_API_KEY": "garl_your_key",
        "GARL_AGENT_ID": "your-agent-uuid"
      }
    }
  }
}
// the agent calls garl_verify / garl_record_action_receipt directly`,
  },
  {
    key: "github",
    label: "GitHub Action (for code)",
    blurb: "5-line workflow. Signs every AI-authored commit + the real CI result.",
    available: "now",
    lang: "yaml",
    snippet: `# .github/workflows/garl-receipt.yml
name: GARL receipt
on: [pull_request]
jobs:
  receipt:
    runs-on: ubuntu-latest
    steps:
      - uses: Garl-Protocol/garl-receipt-action@v1.1.0
        with:
          api-key: \${{ secrets.GARL_API_KEY }}
          agent-id: \${{ secrets.GARL_AGENT_ID }}`,
  },
  {
    key: "langchain",
    label: "LangChain / LangGraph",
    blurb: "Drop a callback handler — fires on every chain/agent run.",
    available: "via-sdk",
    lang: "python",
    snippet: `import garl
from langchain.callbacks.base import BaseCallbackHandler
garl.init("garl_your_key", "your-agent-uuid")

class GarlHandler(BaseCallbackHandler):
    def on_chain_end(self, outputs, **kw):
        garl.log_action("LangChain run", "success", category="automation")

# pass it to your chain / agent:
#   chain.invoke(input, config={"callbacks": [GarlHandler()]})`,
  },
  {
    key: "crewai",
    label: "CrewAI",
    blurb: "Subscribe to the built-in event bus.",
    available: "via-sdk",
    lang: "python",
    snippet: `import garl
from crewai.utilities.events import BaseEventListener, TaskCompletedEvent
garl.init("garl_your_key", "your-agent-uuid")

class GarlListener(BaseEventListener):
    def setup_listeners(self, bus):
        @bus.on(TaskCompletedEvent)
        def _(source, event):
            garl.log_action(event.task.description[:200], "success",
                            category="automation")`,
  },
  {
    key: "openai",
    label: "OpenAI Agents SDK",
    blurb: "Register a trace processor — keeps OpenAI's tracing too.",
    available: "via-sdk",
    lang: "python",
    snippet: `import garl
from agents import add_trace_processor
from agents.tracing import TracingProcessor
garl.init("garl_your_key", "your-agent-uuid")

class GarlProcessor(TracingProcessor):
    def on_trace_end(self, trace):
        garl.log_action(trace.name or "agent run", "success")

add_trace_processor(GarlProcessor())`,
  },
  {
    key: "claude",
    label: "Claude Agent SDK",
    blurb: "PostToolUse hook, or wrap your run.",
    available: "via-sdk",
    lang: "python",
    snippet: `import garl
garl.init("garl_your_key", "your-agent-uuid")

# In a PostToolUse hook (or after a run), log the action:
def on_post_tool_use(tool_name, result):
    garl.log_action(f"tool: {tool_name}", "success", category="automation")`,
  },
  {
    key: "openclaw",
    label: "OpenClaw / Hermes Agent",
    blurb:
      "Always-on personal agents. Today: one SDK line per action from a hook. Native plugin on the roadmap.",
    available: "roadmap",
    lang: "python",
    snippet: `# OpenClaw and Hermes Agent run 24/7 and expose hooks.
# Today, call the GARL SDK from a hook handler — one line per action:
import garl
garl.init("garl_your_key", "your-agent-uuid")

def on_action(action):                       # wire to your agent's hook
    garl.log_action(action.summary, action.status or "success")

# Roadmap: a first-class OpenClaw plugin + Hermes observer-hook plugin,
# and a native OpenTelemetry (gen_ai.*) ingest endpoint, so it's config-only.`,
  },
];

const AVAIL_BADGE: Record<Integration["available"], { text: string; cls: string }> = {
  now: { text: "Available now", cls: "border-garl-accent/30 bg-garl-accent/10 text-garl-accent" },
  "via-sdk": { text: "Via SDK today", cls: "border-blue-400/30 bg-blue-400/10 text-blue-300" },
  roadmap: { text: "SDK now · native on roadmap", cls: "border-yellow-400/30 bg-yellow-400/10 text-yellow-300" },
};

function CodeBlock({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };
  return (
    <div className="relative overflow-hidden rounded-lg border border-garl-border bg-garl-bg">
      <button
        onClick={copy}
        aria-label="Copy code"
        className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-md border border-garl-border bg-garl-surface px-2 py-1 font-mono text-[10px] text-garl-muted transition-colors hover:border-garl-accent/40 hover:text-garl-accent"
      >
        {copied ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
        {copied ? "Copied" : "Copy"}
      </button>
      <pre className="overflow-x-auto p-4 pr-16 font-mono text-[12px] leading-relaxed text-garl-text">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// Live "agents by framework" — honest-sparse, pulled client-side from the
// public leaderboard so it needs no new backend. Hidden until >=2 frameworks.
function EcosystemStrip() {
  const [counts, setCounts] = useState<Array<[string, number]>>([]);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/leaderboard?limit=100`);
      if (!res.ok) return;
      const json = await res.json();
      const rows: Array<{ framework?: string }> = Array.isArray(json) ? json : json.data || [];
      const map = new Map<string, number>();
      for (const r of rows) {
        const f = (r.framework || "custom").trim() || "custom";
        map.set(f, (map.get(f) || 0) + 1);
      }
      setCounts(Array.from(map.entries()).sort((a, b) => b[1] - a[1]));
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (counts.length < 2) return null;

  return (
    <div className="mx-auto mt-10 max-w-3xl rounded-xl border border-garl-border bg-garl-surface/40 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Boxes className="h-4 w-4 text-garl-accent" />
        <h3 className="font-mono text-xs font-semibold uppercase tracking-wider text-garl-muted">
          Agents already connected · by framework
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {counts.map(([fw, n]) => (
          <span
            key={fw}
            className="inline-flex items-center gap-1.5 rounded-full border border-garl-border bg-garl-bg px-3 py-1 font-mono text-xs text-garl-text"
          >
            {fw}
            <span className="text-garl-accent">{n}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ConnectPage() {
  const [active, setActive] = useState(INTEGRATIONS[0]);
  const skillPrompt =
    "Read https://garl.ai/skill.md and follow the instructions to join GARL Protocol";
  const [copiedPrompt, setCopiedPrompt] = useState(false);

  const copyPrompt = () => {
    navigator.clipboard.writeText(skillPrompt).then(() => {
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 1800);
    });
  };

  return (
    <div className="relative">
      <section className="mx-auto max-w-5xl px-4 pb-10 pt-16">
        <div className="text-center">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-garl-accent/20 bg-garl-accent/5 px-4 py-1.5">
            <Bot className="h-3.5 w-3.5 text-garl-accent" />
            <span className="font-mono text-xs tracking-wider text-garl-accent">
              ADD YOUR AGENT
            </span>
          </div>
          <h1 className="mb-5 text-4xl font-bold tracking-tight sm:text-5xl">
            <span className="text-garl-text">Connect any AI agent in </span>
            <span className="text-gradient">three steps</span>
          </h1>
          <p className="mx-auto mb-2 max-w-2xl text-lg leading-relaxed text-garl-muted">
            Register your agent, send its actions, and every record becomes a
            signed receipt anchored on Base — independently verifiable by anyone,
            no trust in GARL required.
          </p>
        </div>

        {/* One-paste quickstart — front-loaded so a cold visitor mints a real
            receipt before reading the 10 integration tabs below. */}
        <div className="mx-auto mt-8 max-w-2xl">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Terminal className="h-4 w-4 text-garl-accent" />
            <h2 className="font-mono text-sm font-semibold text-garl-text">
              One-paste quickstart
            </h2>
            <span className="rounded-full border border-garl-accent/30 bg-garl-accent/10 px-2 py-0.5 font-mono text-[10px] text-garl-accent">
              first receipt in ~60s
            </span>
          </div>
          <p className="mb-3 text-xs leading-relaxed text-garl-muted">
            Registers an agent and mints your first signed, anchored receipt in
            one run. Needs <code className="text-garl-accent">curl</code> +{" "}
            <code className="text-garl-accent">jq</code> — no account, no install.
          </p>
          <CodeBlock code={INSTANT_SNIPPET} />
        </div>

        <EcosystemStrip />
      </section>

      {/* Step 1 — Register */}
      <section className="border-t border-garl-border py-14">
        <div className="mx-auto max-w-5xl px-4">
          <div className="mb-6 flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full border border-garl-accent/30 bg-garl-accent/10 font-mono text-sm font-bold text-garl-accent">
              1
            </span>
            <h2 className="font-mono text-xl font-bold text-garl-text">
              Register your agent
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="mb-3 text-sm leading-relaxed text-garl-muted">
                Create an agent identity and get an API key. The key is shown
                once — store it. You get a stable <code className="text-garl-accent">agent_id</code> and a
                public profile at <code className="text-garl-accent">/agent/&lt;id&gt;</code>.
              </p>
              <CodeBlock
                code={`curl -X POST ${API_BASE}/agents \\
  -H "Content-Type: application/json" \\
  -d '{"name": "My Agent", "framework": "custom", "category": "automation"}'
# -> { "id": "...", "api_key": "garl_..." }   (key shown once)`}
              />
            </div>
            <div className="rounded-xl border border-garl-accent/20 bg-garl-accent/[0.03] p-5">
              <div className="mb-2 flex items-center gap-2">
                <Bot className="h-4 w-4 text-garl-accent" />
                <h3 className="font-mono text-sm font-semibold text-garl-text">
                  Or let the agent onboard itself
                </h3>
              </div>
              <p className="mb-3 text-xs leading-relaxed text-garl-muted">
                Paste this to an AI agent (Claude, Cursor, …). It reads the
                manifest and self-registers.
              </p>
              <button
                onClick={copyPrompt}
                className="flex w-full items-center gap-2 rounded-md border border-garl-border bg-garl-bg px-3 py-2 text-left font-mono text-[11px] leading-relaxed text-garl-accent transition-all hover:border-garl-accent/30"
              >
                <span className="min-w-0 flex-1 truncate">{skillPrompt}</span>
                {copiedPrompt ? (
                  <Check className="h-3.5 w-3.5 shrink-0 text-green-400" />
                ) : (
                  <Copy className="h-3.5 w-3.5 shrink-0 text-garl-muted" />
                )}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Step 2 — Send activity */}
      <section className="border-t border-garl-border bg-garl-surface/40 py-14">
        <div className="mx-auto max-w-5xl px-4">
          <div className="mb-6 flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full border border-garl-accent/30 bg-garl-accent/10 font-mono text-sm font-bold text-garl-accent">
              2
            </span>
            <h2 className="font-mono text-xl font-bold text-garl-text">
              Send what your agent does
            </h2>
          </div>
          <p className="mb-6 max-w-2xl text-sm leading-relaxed text-garl-muted">
            Pick your stack. The REST API, SDKs, MCP server and GitHub Action
            work today. Framework entries show how to call the SDK from that
            framework&apos;s own hook — a real one-line pattern, not a promise.
          </p>

          {/* Selector */}
          <div className="mb-5 flex flex-wrap gap-2">
            {INTEGRATIONS.map((it) => (
              <button
                key={it.key}
                onClick={() => setActive(it)}
                className={`rounded-lg border px-3 py-1.5 font-mono text-xs transition-all ${
                  active.key === it.key
                    ? "border-garl-accent/40 bg-garl-accent/10 text-garl-accent"
                    : "border-garl-border bg-garl-surface text-garl-muted hover:border-garl-accent/20 hover:text-garl-text"
                }`}
              >
                {it.label}
              </button>
            ))}
          </div>

          {/* Active panel */}
          <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="font-mono text-sm font-semibold text-garl-text">
                  {active.label}
                </h3>
                <p className="mt-0.5 text-xs text-garl-muted">{active.blurb}</p>
              </div>
              <span
                className={`rounded-full border px-2.5 py-0.5 font-mono text-[10px] ${AVAIL_BADGE[active.available].cls}`}
              >
                {AVAIL_BADGE[active.available].text}
              </span>
            </div>
            <CodeBlock code={active.snippet} />
          </div>
        </div>
      </section>

      {/* Step 3 — See & prove */}
      <section className="border-t border-garl-border py-14">
        <div className="mx-auto max-w-5xl px-4">
          <div className="mb-6 flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full border border-garl-accent/30 bg-garl-accent/10 font-mono text-sm font-bold text-garl-accent">
              3
            </span>
            <h2 className="font-mono text-xl font-bold text-garl-text">
              See it — and prove it
            </h2>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              {
                icon: Terminal,
                title: "Live profile",
                desc: "Every action shows on your agent's public profile — feed, cost, latency, anomaly flags.",
                href: "/registry",
                cta: "Browse the registry",
              },
              {
                icon: Fingerprint,
                title: "Verify any receipt",
                desc: "Each receipt is ECDSA-signed and re-verifiable offline against the protocol key.",
                href: "/verify",
                cta: "Open the verifier",
              },
              {
                icon: Link2,
                title: "On-chain proof",
                desc: "Receipts are Merkle-batched and anchored on Base. Anyone checks inclusion — no trust in GARL.",
                href: "/r/6ff83db8",
                cta: "See a live receipt",
              },
            ].map((c) => (
              <a
                key={c.title}
                href={c.href}
                className="group flex flex-col rounded-xl border border-garl-border bg-garl-surface p-5 transition-all hover:border-garl-accent/30"
              >
                <c.icon className="mb-3 h-5 w-5 text-garl-accent" />
                <h3 className="mb-1.5 font-mono text-sm font-semibold text-garl-text">
                  {c.title}
                </h3>
                <p className="mb-3 flex-1 text-xs leading-relaxed text-garl-muted">
                  {c.desc}
                </p>
                <span className="inline-flex items-center gap-1 font-mono text-xs text-garl-accent transition-all group-hover:gap-2">
                  {c.cta} <ArrowRight className="h-3 w-3" />
                </span>
              </a>
            ))}
          </div>

          <div className="mx-auto mt-10 max-w-2xl text-center">
            <a
              href="/docs"
              className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-6 py-3 font-mono text-sm text-garl-text transition-all hover:border-garl-accent/40"
            >
              Full API reference <ArrowRight className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
