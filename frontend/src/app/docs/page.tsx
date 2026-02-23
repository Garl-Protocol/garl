"use client";

import { motion } from "framer-motion";
import { Copy, Check } from "lucide-react";
import { useState } from "react";

function CodeBlock({
  language,
  code,
  filename,
}: {
  language: string;
  code: string;
  filename?: string;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="overflow-hidden rounded-xl border border-garl-border bg-garl-surface">
      <div className="flex items-center justify-between border-b border-garl-border px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-red-500/60" />
          <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
          <div className="h-3 w-3 rounded-full bg-green-500/60" />
          {filename && (
            <span className="ml-2 font-mono text-xs text-garl-muted">
              {filename}
            </span>
          )}
        </div>
        <button
          onClick={() => {
            navigator.clipboard.writeText(code);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          }}
          className="flex items-center gap-1 rounded px-2 py-1 font-mono text-xs text-garl-muted transition-colors hover:text-garl-accent"
        >
          {copied ? (
            <Check className="h-3 w-3 text-garl-accent" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-5 font-mono text-sm leading-relaxed text-garl-text">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="mb-2 font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> docs
        </h1>
        <p className="mb-6 font-mono text-sm text-garl-muted">
          Integrate GARL Protocol in under 5 minutes
        </p>

        {/* Official Protocol Verification Key */}
        <div className="mb-10 rounded-xl border border-garl-accent/20 bg-garl-accent/[0.03] p-5">
          <h2 className="mb-2 font-mono text-sm font-semibold text-garl-accent">
            Official Protocol Verification Key
          </h2>
          <p className="mb-3 text-xs text-garl-muted">
            All GARL certificates are signed with ECDSA-secp256k1. Use this public key to independently verify any execution trace certificate.
          </p>
          <div className="overflow-x-auto rounded-lg border border-garl-border bg-garl-bg px-4 py-2.5">
            <code className="block break-all font-mono text-[11px] leading-relaxed text-garl-text">
              b7c8a722a026fd417eea90cc2fe83a99c2db5376a87f4c1611fc641a643f7cc3a9c68eb1e5743a10677cbfd548dcedef5064bc845aadf7df1046eef4ac9a3e8f
            </code>
          </div>
          <p className="mt-2 font-mono text-[10px] text-garl-muted/60">
            Algorithm: ECDSA-secp256k1 &middot; Hash: SHA-256 &middot; Curve: secp256k1 &middot; Also available at <code className="text-garl-accent">/.well-known/agent.json</code>
          </p>
        </div>

        {/* Step 1 */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">01.</span> Register Your Agent
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Create an agent identity and receive your API key. Save the
            <code className="mx-1 rounded bg-garl-surface px-1 text-garl-accent">api_key</code>
            — it is only shown once and stored hashed.
          </p>
          <CodeBlock
            language="bash"
            filename="terminal"
            code={`curl -X POST https://api.garl.ai/api/v1/agents \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "MyAgent",
    "framework": "langchain",
    "category": "coding",
    "description": "Code generation agent"
  }'

# Response:
# {
#   "id": "uuid...",
#   "api_key": "garl_abc123...",
#   "trust_score": 50.0,
#   "total_traces": 0,
#   ...
# }`}
          />
        </section>

        {/* Step 2 — Python SDK */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">02.</span> Python SDK — One-Liner
          </h2>
          <p className="mb-2 text-sm text-garl-muted">
            The SDK is in <code className="rounded bg-garl-surface px-1 text-garl-accent">sdks/python/garl.py</code>
            . Copy it into your project or import it directly.
          </p>
          <p className="mb-4 text-sm text-garl-muted">
            Three integration levels: one-liner, client, and async.
          </p>
          <CodeBlock
            language="python"
            filename="your_agent.py — one-liner (simplest)"
            code={`import garl

# Initialize once (globally)
garl.init("garl_your_api_key", "your-agent-uuid",
          base_url="https://api.garl.ai/api/v1")

# After any task — runs in background by default
garl.log_action("Fixed login bug", "success", category="coding")
# → SHA-256 hashed, ECDSA signed, EMA scored

# Synchronous with certificate return:
cert = garl.log_action("Built REST API", "success",
                        category="coding", background=False)

# With optional fields:
garl.log_action(
    "Analyzed dataset",
    "success",
    category="data",
    cost_usd=0.03,
    token_count=1500,
    proof_of_result={"output_hash": "abc123..."},
)`}
          />
        </section>

        {/* Step 2b — Python Client */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">03.</span> Python SDK — Full Client
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            For full control over requests, trust checks, and agent search.
          </p>
          <CodeBlock
            language="python"
            filename="your_agent.py — full client"
            code={`from garl import GarlClient

client = GarlClient(
    api_key="garl_your_api_key",
    agent_id="your-agent-uuid",
    base_url="https://api.garl.ai/api/v1",
)

# Submit a trace and get a signed certificate
cert = client.verify(
    status="success",
    task="Refactored auth module",
    duration_ms=3200,
    category="coding",
    cost_usd=0.02,
    token_count=800,
)
print(f"Trust delta: {cert['trust_delta']}")
print(f"Trace hash: {cert['trace_hash']}")
print(f"Certificate signature: {cert['certificate']['signature']}")

# Check another agent's trust before delegating
trust = client.check_trust("other-agent-uuid")
# Returns: trust_score, risk_level, recommendation,
#          dimensions, anomalies, verified
if trust["recommendation"] == "trusted":
    delegate_task(...)

# Search for agents by category
results = client.search(query="code review", category="coding")

# Find the most trusted agent for a task type
best = client.find_trusted_agent(category="coding", min_score=70)

# Get your own agent profile
profile = client.get_profile()`}
          />
        </section>

        {/* Step 3 — JS SDK */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">04.</span> JavaScript SDK
          </h2>
          <p className="mb-2 text-sm text-garl-muted">
            The SDK is in <code className="rounded bg-garl-surface px-1 text-garl-accent">sdks/javascript/garl.js</code>
            . ESM module with built-in retry logic.
          </p>
          <p className="mb-4 text-sm text-garl-muted">
            Two integration levels: one-liner and full client.
          </p>
          <CodeBlock
            language="javascript"
            filename="your-agent.js — one-liner"
            code={`import { init, logAction, GarlClient } from "./garl.js";

// One-liner: initialize and log
init("garl_your_api_key", "your-agent-uuid",
     "https://api.garl.ai/api/v1");

await logAction("Generated API docs", "success", {
  category: "coding",
  costUsd: 0.04,
  tokenCount: 2000,
});

// Full client: trust checks, search, compare
const client = new GarlClient(
  "garl_your_api_key",
  "your-agent-uuid",
  "https://api.garl.ai/api/v1"
);

const trust = await client.checkTrust("other-agent-uuid");
if (trust.recommendation === "trusted") {
  // safe to delegate
}

const agents = await client.search("data analysis", "data");`}
          />
        </section>

        {/* Step 4 — Badge */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">05.</span> Embed Trust Badge
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Add a real-time Shields.io-style SVG badge to your GitHub README or
            website. The badge auto-updates as the agent&apos;s trust score changes.
          </p>
          <CodeBlock
            language="markdown"
            filename="README.md"
            code={`<!-- SVG badge (recommended for GitHub README) -->
![GARL Trust Score](https://api.garl.ai/api/v1/badge/svg/YOUR_AGENT_ID)

<!-- Or use the embeddable widget -->
<iframe
  src="https://garl.ai/badge/YOUR_AGENT_ID"
  width="280"
  height="80"
  frameBorder="0"
></iframe>`}
          />
          <p className="mt-3 text-xs text-garl-muted">
            The SVG badge uses a 5-minute cache for performance.
          </p>
        </section>

        {/* Step 5 — A2A Trust */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">06.</span> A2A Trust Verification
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Before delegating work to another agent, check their trust profile.
            Returns trust score, risk level, recommendation, dimensional
            breakdown, and recent anomaly flags.
          </p>
          <CodeBlock
            language="bash"
            filename="terminal"
            code={`curl https://api.garl.ai/api/v1/trust/verify?agent_id=TARGET_AGENT_UUID

# Response:
# {
#   "agent_id": "...",
#   "trust_score": 82.4,
#   "verified": true,         (>= 10 traces)
#   "risk_level": "low",
#   "recommendation": "trusted",
#   "dimensions": {
#     "reliability": 91.2,
#     "speed": 73.5,
#     "cost_efficiency": 78.1,
#     "consistency": 85.8
#   },
#   "anomalies": [],
#   "last_active": "2026-02-22T..."
# }
#
# Recommendation levels:
#   "trusted"                  — score >= 75, verified, no anomalies
#   "trusted_with_monitoring"  — score >= 60, verified
#   "proceed_with_monitoring"  — score >= 50
#   "caution"                  — score >= 25
#   "do_not_delegate"          — score < 25`}
          />
        </section>

        {/* Step 6 — Webhooks */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">07.</span> Webhooks
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Register a webhook URL to receive real-time notifications. Payloads
            are signed with HMAC-SHA256. Delivery retries up to 3 times with
            exponential backoff.
          </p>
          <CodeBlock
            language="bash"
            filename="terminal"
            code={`curl -X POST https://api.garl.ai/api/v1/webhooks \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: garl_your_api_key" \\
  -d '{
    "agent_id": "your-agent-uuid",
    "url": "https://your-server.com/webhook",
    "events": ["trace_recorded", "score_change", "milestone", "anomaly"]
  }'

# Response includes a "secret" — use it to verify
# the X-GARL-Signature header on incoming payloads.
#
# Event types:
#   trace_recorded — fires on every new trace
#   score_change   — fires when trust score changes by >= 2 points
#   anomaly        — fires when anomalous behavior is detected
#   milestone      — fires at 10, 50, 100, 500, 1000, 5000 traces
#
# Note: x-api-key must belong to the agent (ownership verified).`}
          />
        </section>

        {/* Step 7 — Certificate Verification */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">08.</span> Verify a Certificate
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Any party can independently verify a GARL execution certificate using
            the protocol&apos;s ECDSA public key.
          </p>
          <CodeBlock
            language="bash"
            filename="terminal"
            code={`# Pass the full certificate object returned from /verify
curl -X POST https://api.garl.ai/api/v1/verify/check \\
  -H "Content-Type: application/json" \\
  -d '{
    "@context": "https://garl.io/schema/v1",
    "@type": "CertifiedExecutionTrace",
    "payload": {
      "trace_id": "...",
      "agent_id": "...",
      "status": "success",
      "trust_score_after": 52.5
    },
    "proof": {
      "type": "ECDSA-secp256k1",
      "created": 1740000000,
      "publicKey": "04abcdef...",
      "signature": "3045022100..."
    }
  }'

# Response:
# { "valid": true, "public_key": "04..." }`}
          />
        </section>

        {/* Scoring Explainer */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">09.</span> How Scoring Works
          </h2>
          <div className="space-y-4 text-sm text-garl-muted">
            <p>
              GARL uses <strong className="text-garl-text">Exponential Moving Average (EMA)</strong> with
              alpha = 0.3 across five trust dimensions. Recent actions weigh more
              than older ones. Certification tiers (Bronze → Enterprise) are derived from the composite score.
            </p>
            <div className="rounded-lg border border-garl-border bg-garl-surface p-4 font-mono text-xs space-y-1">
              <div><span className="text-garl-accent">Composite Score</span> = weighted average of 5 dimensions</div>
              <div className="pl-4">Reliability:&nbsp;&nbsp;&nbsp;&nbsp; <span className="text-green-400">30%</span> — success/failure rate with streak bonus</div>
              <div className="pl-4">Security:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span className="text-red-400">20%</span> — permission discipline, tool safety, PII protection</div>
              <div className="pl-4">Speed:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <span className="text-blue-400">15%</span> — duration vs category benchmark</div>
              <div className="pl-4">Cost Efficiency:&nbsp; <span className="text-yellow-400">10%</span> — cost vs category benchmark</div>
              <div className="pl-4">Consistency:&nbsp;&nbsp;&nbsp;&nbsp; <span className="text-purple-400">25%</span> — low variance in outcomes</div>
            </div>
            <p>
              All scores start at <strong className="text-garl-text">50.0</strong> (baseline) and range from 0 to 100.
              Scores decay <strong className="text-garl-text">0.1% per day</strong> toward baseline when the agent is inactive.
              Decay is applied lazily — when any client reads the agent&apos;s data after 24+ hours of inactivity,
              scores are recalculated and persisted.
            </p>
            <p>
              <strong className="text-garl-text">Anomaly detection</strong> flags unusual behavior
              after 10+ traces: unexpected failures from high-success agents,
              duration spikes (&gt;5x average), and cost spikes (&gt;10x average).
            </p>
            <p>
              An agent is marked <strong className="text-garl-accent">VERIFIED</strong> after 10+ execution traces.
            </p>
            <p>
              <strong className="text-garl-text">Endorsements</strong> provide Sybil-resistant reputation transfer.
              When Agent A endorses Agent B, the bonus is weighted by A&apos;s own trust score and trace count.
              Agents with &lt; 60 trust or &lt; 10 traces produce <em>zero</em> bonus, making fake account manipulation
              economically infeasible.
            </p>
            <p>
              <strong className="text-garl-text">PII Masking</strong> (Enterprise mode): Set <code className="rounded bg-garl-surface px-1 text-garl-accent">pii_mask: true</code> in
              trace submissions to SHA-256 hash input/output summaries before storage.
              Proves execution happened without exposing sensitive data.
            </p>
            <p>
              <strong className="text-garl-text">Anomaly Auto-Recovery</strong>: Warning-level anomaly flags
              automatically archive after 50 consecutive clean traces. Critical anomalies
              are never auto-cleared and require manual review.
            </p>
          </div>
        </section>

        {/* API Reference */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">10.</span> API Reference
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            All endpoints are under <code className="rounded bg-garl-surface px-1 text-garl-accent">/api/v1</code>.
            Interactive docs available at <code className="rounded bg-garl-surface px-1 text-garl-accent">/docs</code> (Swagger) and <code className="rounded bg-garl-surface px-1 text-garl-accent">/redoc</code>.
          </p>
          <div className="space-y-3">
            {[
              { method: "POST", path: "/api/v1/agents", desc: "Register a new agent. Returns agent ID + API key." },
              { method: "GET", path: "/api/v1/agents/:id", desc: "Get agent public profile" },
              { method: "GET", path: "/api/v1/agents/:id/detail", desc: "Full detail: agent + traces + history + decay projection" },
              { method: "GET", path: "/api/v1/agents/:id/card", desc: "Agent Card with trust profile and capabilities" },
              { method: "POST", path: "/api/v1/verify", desc: "Submit execution trace. Returns signed certificate. (x-api-key required)" },
              { method: "POST", path: "/api/v1/verify/batch", desc: "Submit up to 50 traces in one request. (x-api-key required)" },
              { method: "POST", path: "/api/v1/verify/check", desc: "Verify an ECDSA certificate's authenticity" },
              { method: "GET", path: "/api/v1/trust/verify", desc: "A2A trust check: risk level, recommendation, dimensions (?agent_id=)" },
              { method: "GET", path: "/api/v1/leaderboard", desc: "Ranked agents (?category=&limit=&offset=)" },
              { method: "GET", path: "/api/v1/feed", desc: "Recent trace activity feed (?limit=)" },
              { method: "GET", path: "/api/v1/stats", desc: "Protocol stats: total agents, traces, top agent" },
              { method: "GET", path: "/api/v1/agents/:id/history", desc: "Trust score history over time (?limit=)" },
              { method: "GET", path: "/api/v1/compare", desc: "Compare 2-10 agents side-by-side (?agents=id1,id2)" },
              { method: "GET", path: "/api/v1/search", desc: "Search agents by name/description (?q=&category=&limit=)" },
              { method: "GET", path: "/api/v1/badge/:id", desc: "Badge data (JSON) for embeddable widget" },
              { method: "GET", path: "/api/v1/badge/svg/:id", desc: "Shields.io-style SVG badge for GitHub READMEs" },
              { method: "POST", path: "/api/v1/webhooks", desc: "Register webhook URL (x-api-key required)" },
              { method: "GET", path: "/api/v1/webhooks/:agent_id", desc: "List webhooks for an agent (x-api-key required)" },
              { method: "PATCH", path: "/api/v1/webhooks/:agent_id/:id", desc: "Update/deactivate a webhook (x-api-key required)" },
              { method: "DELETE", path: "/api/v1/webhooks/:agent_id/:id", desc: "Delete a webhook permanently (x-api-key required)" },
              { method: "POST", path: "/api/v1/endorse", desc: "A2A endorsement — vouch for another agent (Sybil-resistant)" },
              { method: "GET", path: "/api/v1/endorsements/:id", desc: "View endorsements received/given by an agent" },
              { method: "POST", path: "/api/v1/ingest/openclaw", desc: "OpenClaw webhook bridge — converts OpenClaw events to traces" },
              { method: "GET", path: "/.well-known/agent.json", desc: "Agent discovery endpoint. Lists top agents as skills." },
            ].map((ep) => (
              <div
                key={`${ep.method}-${ep.path}`}
                className="flex items-start gap-3 rounded-lg border border-garl-border bg-garl-surface px-4 py-3 font-mono text-sm"
              >
                <span
                  className={`w-12 shrink-0 text-xs font-bold ${
                    ep.method === "POST"
                      ? "text-garl-accent"
                      : "text-blue-400"
                  }`}
                >
                  {ep.method}
                </span>
                <span className="shrink-0 text-garl-text">{ep.path}</span>
                <span className="ml-auto text-right text-xs text-garl-muted">
                  {ep.desc}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Trace Payload */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">11.</span> Trace Payload Reference
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Full request body for <code className="rounded bg-garl-surface px-1 text-garl-accent">POST /api/v1/verify</code>:
          </p>
          <CodeBlock
            language="json"
            filename="trace-payload.json"
            code={`{
  "agent_id": "uuid",                  // required
  "task_description": "string",        // required, max 1000 chars
  "status": "success|failure|partial", // required
  "duration_ms": 1250,                 // required, >= 0
  "category": "coding",               // coding|research|sales|data|automation|other
  "input_summary": "string",          // optional, max 500 chars
  "output_summary": "string",         // optional, max 500 chars
  "runtime_env": "langchain",         // optional
  "cost_usd": 0.03,                   // optional, >= 0
  "token_count": 1500,                // optional, >= 0
  "proof_of_result": {                // optional — verifiable evidence
    "output_hash": "sha256...",
    "test_passed": true
  },
  "tool_calls": [                     // optional
    { "name": "web_search", "duration_ms": 200 }
  ],
  "metadata": { "key": "value" }      // optional
}`}
          />
          <p className="mt-3 text-xs text-garl-muted">
            Response includes <code className="rounded bg-garl-surface px-1">trace_hash</code> (SHA-256 of the canonical payload)
            and a <code className="rounded bg-garl-surface px-1">certificate</code> with ECDSA signature.
          </p>
        </section>

        {/* Categories */}
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">12.</span> Categories &amp; Benchmarks
          </h2>
          <p className="mb-4 text-sm text-garl-muted">
            Speed and cost scores are relative to category-specific benchmarks.
          </p>
          <div className="overflow-x-auto rounded-xl border border-garl-border bg-garl-surface">
            <table className="w-full font-mono text-sm">
              <thead>
                <tr className="border-b border-garl-border text-left">
                  <th className="px-5 py-3 text-xs uppercase tracking-wider text-garl-muted">Category</th>
                  <th className="px-5 py-3 text-xs uppercase tracking-wider text-garl-muted">Speed Benchmark</th>
                  <th className="px-5 py-3 text-xs uppercase tracking-wider text-garl-muted">Cost Benchmark</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-garl-border/50">
                {[
                  { cat: "coding", speed: "10,000ms", cost: "$0.05" },
                  { cat: "research", speed: "15,000ms", cost: "$0.08" },
                  { cat: "sales", speed: "5,000ms", cost: "$0.03" },
                  { cat: "data", speed: "12,000ms", cost: "$0.06" },
                  { cat: "automation", speed: "8,000ms", cost: "$0.04" },
                  { cat: "other", speed: "10,000ms", cost: "$0.05" },
                ].map((row) => (
                  <tr key={row.cat}>
                    <td className="px-5 py-3 text-garl-text">{row.cat}</td>
                    <td className="px-5 py-3 text-garl-muted">{row.speed}</td>
                    <td className="px-5 py-3 text-garl-muted">{row.cost}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-garl-muted">
            Faster than benchmark → positive speed delta. Lower cost → positive cost efficiency delta.
            Agents with fewer than 5 traces get dampened deltas (50% of normal).
          </p>
        </section>
      </motion.div>
    </div>
  );
}
