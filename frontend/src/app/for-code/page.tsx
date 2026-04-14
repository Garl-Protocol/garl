import type { Metadata } from "next";
import Link from "next/link";
import {
  ShieldCheck,
  GitPullRequest,
  CheckCircle,
  Fingerprint,
  Scale,
  Github,
} from "lucide-react";

export const metadata: Metadata = {
  title: "GARL for Code — Cryptographic proof for every AI-generated commit",
  description:
    "46% of new code is AI-generated. GARL for Code signs every AI-authored commit with ECDSA-secp256k1 and makes provenance verifiable via a 5-line GitHub Action. Open source, Apache 2.0.",
  alternates: { canonical: "https://garl.ai/for-code" },
  openGraph: {
    title: "GARL for Code — Cryptographic proof for AI-generated commits",
    description:
      "5-line GitHub Action. EU AI Act ready. Open source. Signs every Claude Code / Cursor / Copilot commit with ECDSA-secp256k1.",
    url: "https://garl.ai/for-code",
    siteName: "GARL Protocol",
    type: "article",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "GARL for Code" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "GARL for Code — Cryptographic proof for AI-generated commits",
    description:
      "5-line GitHub Action. Detects Claude Code / Cursor / Copilot. ECDSA-secp256k1 signed. Open source.",
    images: ["/og-image.png"],
  },
};

const WORKFLOW_YAML = `name: GARL Receipt
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  sign:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      checks: write
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: Garl-Protocol/garl-receipt-action@v1.0.0
        with:
          garl-api-key: \${{ secrets.GARL_API_KEY }}
          garl-agent-id: \${{ secrets.GARL_AGENT_ID }}`;

const PR_COMMENT = `🔐 GARL Verified AI Code
├── Model: claude-opus-4-6
├── Tool: Claude Code
├── Files touched: 12
├── Duration: 4m 12s
├── Signed: ECDSA-secp256k1 ✓
└── Receipt: https://garl.ai/r/a8f3c2d1`;

export default function ForCodePage() {
  return (
    <div className="relative">
      {/* Background grid */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,255,136,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,136,0.3) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Hero */}
      <section className="relative mx-auto max-w-6xl px-4 pt-20 pb-16">
        <div className="grid items-center gap-10 md:grid-cols-[1.1fr_1fr]">
          <div>
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-garl-accent/30 bg-garl-accent/10 px-3 py-1 font-mono text-xs tracking-wider text-garl-accent">
              <ShieldCheck className="h-3.5 w-3.5" />
              GARL FOR CODE · OPEN SOURCE
            </div>
            <h1 className="mb-5 text-4xl font-bold leading-[1.05] tracking-tight sm:text-6xl">
              <span className="text-gradient">Cryptographic proof</span>
              <br />
              <span className="text-garl-text">for every AI-generated commit.</span>
            </h1>
            <p className="mb-6 max-w-xl text-base leading-relaxed text-garl-muted sm:text-lg">
              <span className="font-semibold text-garl-text">
                46% of new code is AI-generated.
              </span>{" "}
              Who wrote it? Which model? Was it reviewed? GARL for Code signs
              every AI-authored commit with{" "}
              <code className="rounded bg-garl-surface px-1.5 py-0.5 text-garl-accent">
                ECDSA-secp256k1
              </code>{" "}
              and makes provenance verifiable.
            </p>
            <div className="flex flex-wrap gap-3">
              <a
                href="#install"
                className="inline-flex items-center gap-2 rounded-lg bg-garl-accent px-5 py-3 font-mono text-sm font-semibold text-garl-bg transition-opacity hover:opacity-90"
              >
                Install in 1 minute →
              </a>
              <a
                href="https://github.com/Garl-Protocol/garl-receipt-action"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-garl-border bg-garl-surface px-5 py-3 font-mono text-sm text-garl-text transition-colors hover:border-garl-accent/40 hover:text-garl-accent"
              >
                <Github className="h-4 w-4" />
                Source
              </a>
              <Link
                href="/r/6ff83db8"
                className="inline-flex items-center gap-2 rounded-lg border border-garl-border bg-garl-surface px-5 py-3 font-mono text-sm text-garl-text transition-colors hover:border-garl-accent/40 hover:text-garl-accent"
              >
                Live receipt example
              </Link>
            </div>
          </div>

          {/* PR mockup */}
          <div className="rounded-xl border border-garl-border bg-garl-surface shadow-[0_0_80px_-20px_rgba(0,255,136,0.15)]">
            <div className="flex items-center justify-between border-b border-garl-border px-4 py-2">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span className="ml-2 font-mono text-xs text-garl-muted">
                  pull/#1337
                </span>
              </div>
              <GitPullRequest className="h-3.5 w-3.5 text-garl-muted" />
            </div>
            <div className="space-y-3 p-5">
              <div className="flex items-center gap-2 rounded-md border border-garl-accent/30 bg-garl-accent/[0.05] px-3 py-2 font-mono text-[11px]">
                <CheckCircle className="h-3.5 w-3.5 text-garl-accent" />
                <span className="text-garl-accent">GARL Receipt</span>
                <span className="text-garl-muted">· 3 of 5 commits signed</span>
              </div>
              <pre className="overflow-x-auto rounded-md border border-garl-border bg-garl-bg p-4 font-mono text-[11px] leading-relaxed text-garl-text">
                {PR_COMMENT}
              </pre>
              <div className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
                ↪ PR comment + informational check · posted by the action
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="relative mx-auto max-w-6xl px-4 py-16">
        <div className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-garl-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-garl-accent" />
          The problem
        </div>
        <h2 className="mb-4 max-w-3xl text-3xl font-bold tracking-tight text-garl-text sm:text-4xl">
          AI is writing your code. Can you prove who wrote what?
        </h2>
        <div className="grid gap-5 md:grid-cols-3">
          {[
            {
              title: "Provenance gap",
              body:
                "Claude Code, Cursor, Copilot, Aider — every modern IDE invites an agent into the commit. Git history captures the author but not the model, the prompt, or the verifier.",
            },
            {
              title: "Compliance clock",
              body:
                "The EU AI Act's Article 50 provenance obligations land August 2026. Audit-ready AI provenance is becoming a procurement requirement, not a nice-to-have.",
              badge: "EU AI Act · Aug 2026",
            },
            {
              title: "Reviewer fatigue",
              body:
                "Reviewers need a concise signal that an AI assisted this diff, which tool, and when. A sticky PR comment with a verifiable receipt beats digging through commit trailers.",
            },
          ].map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-garl-border bg-garl-surface p-5"
            >
              <div className="mb-2 flex items-center gap-2">
                <h3 className="font-mono text-base font-semibold text-garl-text">
                  {card.title}
                </h3>
                {card.badge && (
                  <span className="rounded border border-garl-accent/40 bg-garl-accent/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-garl-accent">
                    {card.badge}
                  </span>
                )}
              </div>
              <p className="text-sm leading-relaxed text-garl-muted">{card.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="relative mx-auto max-w-6xl px-4 py-16">
        <div className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-garl-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-garl-accent" />
          How it works
        </div>
        <h2 className="mb-8 max-w-3xl text-3xl font-bold tracking-tight text-garl-text sm:text-4xl">
          5 lines of YAML. Every AI commit gets a signed receipt.
        </h2>

        <div className="grid gap-6 md:grid-cols-[1.2fr_1fr]">
          <div className="overflow-hidden rounded-xl border border-garl-border bg-garl-surface">
            <div className="flex items-center justify-between border-b border-garl-border px-4 py-2">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span className="ml-2 font-mono text-xs text-garl-muted">
                  .github/workflows/garl-receipt.yml
                </span>
              </div>
            </div>
            <pre className="overflow-x-auto p-5 font-mono text-[12px] leading-relaxed text-garl-text">
              <code>{WORKFLOW_YAML}</code>
            </pre>
          </div>
          <div className="space-y-4">
            {[
              {
                icon: Fingerprint,
                title: "1. Detect",
                body:
                  "The action walks the PR's base..head commits and matches co-author trailers (Claude, Cursor, Copilot, Aider, Codex) + Claude Code markers + model-name heuristics. Confidence scored 0.4–1.0.",
              },
              {
                icon: ShieldCheck,
                title: "2. Sign",
                body:
                  "Every qualifying commit is submitted to GARL as a signed trace. ECDSA-secp256k1 signature + SHA-256 hash + immutable ledger record.",
              },
              {
                icon: GitPullRequest,
                title: "3. Report",
                body:
                  "One sticky PR comment summarizes `N of M commits signed · breakdown by tool`. A neutral (informational) `GARL Receipt` check run lists every receipt URL.",
              },
              {
                icon: Scale,
                title: "4. Audit",
                body:
                  "Each receipt URL (garl.ai/r/{short}) is a public proof card — reviewable by auditors, compliance officers, reviewers, or your future self.",
              },
            ].map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="rounded-xl border border-garl-border bg-garl-surface p-4"
              >
                <div className="mb-2 flex items-center gap-2 text-garl-accent">
                  <Icon className="h-4 w-4" />
                  <h3 className="font-mono text-sm font-semibold text-garl-text">
                    {title}
                  </h3>
                </div>
                <p className="text-[13px] leading-relaxed text-garl-muted">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="relative mx-auto max-w-6xl px-4 py-16">
        <div className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-garl-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-garl-accent" />
          What you get
        </div>
        <h2 className="mb-8 max-w-3xl text-3xl font-bold tracking-tight text-garl-text sm:text-4xl">
          A single workflow. Four compounding benefits.
        </h2>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { t: "Signed PR check", d: "Informational `GARL Receipt` check run on every PR — never blocks, always visible." },
            { t: "Receipt URL", d: "Public, shareable garl.ai/r/{short} page per commit, with agent and ECDSA proof." },
            { t: "Rich previews", d: "Auto-generated 1200×630 Open Graph cards so receipts render beautifully in Slack, X, LinkedIn." },
            { t: "Audit trail", d: "Immutable ledger record with who/what/when — ready for EU AI Act Article 50 provenance." },
          ].map((f) => (
            <div
              key={f.t}
              className="rounded-xl border border-garl-border bg-garl-surface p-5"
            >
              <h3 className="mb-1 font-mono text-sm font-semibold text-garl-accent">
                {f.t}
              </h3>
              <p className="text-[13px] leading-relaxed text-garl-muted">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Install */}
      <section
        id="install"
        className="relative mx-auto max-w-6xl px-4 py-20"
      >
        <div className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-garl-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-garl-accent" />
          Install
        </div>
        <h2 className="mb-6 max-w-3xl text-3xl font-bold tracking-tight text-garl-text sm:text-4xl">
          1 minute, 2 secrets, 1 workflow file.
        </h2>
        <ol className="mb-8 space-y-4 text-sm leading-relaxed text-garl-muted">
          <li>
            <span className="font-mono text-garl-accent">1.</span>{" "}
            Register a repo agent — via the <code className="rounded bg-garl-surface px-1.5 py-0.5 text-garl-accent">garl_register_agent</code> MCP tool or curl:
            <pre className="mt-2 overflow-x-auto rounded-lg border border-garl-border bg-garl-bg p-3 font-mono text-[11px] text-garl-text">
{`curl -sX POST https://api.garl.ai/api/v1/agents/auto-register \\
  -H "Content-Type: application/json" \\
  -d '{"name":"gh-<owner>-<repo>","framework":"github-action"}'`}
            </pre>
          </li>
          <li>
            <span className="font-mono text-garl-accent">2.</span>{" "}
            Save the returned <code>agent_id</code> and <code>api_key</code> as GitHub secrets{" "}
            <code className="rounded bg-garl-surface px-1.5 py-0.5 text-garl-accent">GARL_AGENT_ID</code>{" "}
            and{" "}
            <code className="rounded bg-garl-surface px-1.5 py-0.5 text-garl-accent">GARL_API_KEY</code>.
          </li>
          <li>
            <span className="font-mono text-garl-accent">3.</span>{" "}
            Drop the workflow above into{" "}
            <code className="rounded bg-garl-surface px-1.5 py-0.5 text-garl-accent">.github/workflows/garl-receipt.yml</code>. Open a PR that
            contains an AI co-author trailer — the action signs it.
          </li>
        </ol>

        <div className="rounded-xl border border-garl-accent/30 bg-garl-accent/[0.04] p-5">
          <div className="mb-2 flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-garl-accent">
            <ShieldCheck className="h-4 w-4" />
            Open source · Apache 2.0
          </div>
          <p className="text-sm text-garl-muted">
            Built on{" "}
            <Link href="/" className="text-garl-accent underline">
              GARL Protocol
            </Link>
            {" "}— the open trust layer for AI systems. Source on{" "}
            <a
              href="https://github.com/Garl-Protocol/garl"
              target="_blank"
              rel="noopener noreferrer"
              className="text-garl-accent underline"
            >
              GitHub
            </a>
            . Python &amp; JS SDKs, MCP server (20 tools), and the full REST API
            are all part of the same monorepo. No SaaS lock-in, no black-box
            scoring — everything verifiable.
          </p>
        </div>
      </section>
    </div>
  );
}
