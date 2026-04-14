import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { CheckCircle, XCircle, ExternalLink, Shield } from "lucide-react";
import ReceiptActions from "@/components/ReceiptActions";

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.GARL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.garl.ai/api/v1";

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://garl.ai";

type Receipt = {
  verified: boolean;
  trace_hash: string;
  trace_id: string;
  agent_id: string;
  agent_name: string | null;
  agent_framework: string | null;
  agent_tier: string | null;
  agent_trust_score: number | null;
  task_description: string | null;
  status: string | null;
  category: string | null;
  duration_ms: number | null;
  runtime_env: string | null;
  created_at: string | null;
  receipt_url: string | null;
  short_hash: string | null;
  certificate: {
    proof?: {
      type?: string;
      created?: number;
      publicKey?: string;
      signature?: string;
    };
  };
  public_key: string;
};

async function fetchReceipt(short: string): Promise<Receipt | null> {
  try {
    // Receipts are immutable per short hash; cache hard at the framework
    // level too so repeat hits never re-fetch the backend.
    const res = await fetch(`${API_BASE}/verify/${short}`, {
      next: { revalidate: 86400 },
    });
    if (!res.ok) return null;
    return (await res.json()) as Receipt;
  } catch {
    return null;
  }
}

function tierColor(tier: string | null): string {
  switch (tier) {
    case "enterprise":
      return "text-garl-accent";
    case "gold":
      return "text-yellow-400";
    case "silver":
      return "text-garl-text";
    case "bronze":
    default:
      return "text-garl-muted";
  }
}

function formatDuration(ms: number | null): string {
  if (!ms || ms <= 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

export async function generateMetadata({
  params,
}: {
  params: { short: string };
}): Promise<Metadata> {
  const receipt = await fetchReceipt(params.short);
  if (!receipt) {
    return {
      title: "Receipt not found · GARL",
      robots: { index: false, follow: false },
    };
  }

  const agent = receipt.agent_name || "AI agent";
  const task = receipt.task_description?.trim() || "Execution trace";
  const title = `${agent} · ${task.slice(0, 60)}${task.length > 60 ? "…" : ""}`;
  const description = `Cryptographically verified AI execution receipt — ECDSA-secp256k1 signed · ${formatDuration(
    receipt.duration_ms,
  )} · ${receipt.status ?? "unknown"}.`;

  const ogUrl = `${SITE_URL}/api/og/r/${params.short}`;
  const pageUrl = receipt.receipt_url || `${SITE_URL}/r/${params.short}`;

  return {
    title: `${title} · GARL Receipt`,
    description,
    alternates: { canonical: pageUrl },
    openGraph: {
      title,
      description,
      url: pageUrl,
      siteName: "GARL Protocol",
      type: "article",
      images: [{ url: ogUrl, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogUrl],
    },
  };
}

export default async function ReceiptPage({
  params,
}: {
  params: { short: string };
}) {
  const receipt = await fetchReceipt(params.short);
  if (!receipt) notFound();

  const verified = receipt.verified;
  const agentName = receipt.agent_name || "Unknown agent";
  const tier = receipt.agent_tier || "unclassified";
  const task =
    receipt.task_description?.trim() || "(no task description provided)";
  const proof = receipt.certificate?.proof;
  const signedAt = proof?.created
    ? new Date(proof.created * 1000).toISOString()
    : receipt.created_at
      ? new Date(receipt.created_at).toISOString()
      : null;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      {/* Verified banner */}
      <div
        className={`mb-6 flex items-center gap-4 rounded-xl border p-5 ${
          verified
            ? "border-garl-accent/40 bg-garl-accent/[0.05]"
            : "border-red-500/40 bg-red-500/[0.05]"
        }`}
      >
        {verified ? (
          <CheckCircle className="h-10 w-10 shrink-0 text-garl-accent" />
        ) : (
          <XCircle className="h-10 w-10 shrink-0 text-red-400" />
        )}
        <div className="min-w-0">
          <h1
            className={`font-mono text-xl font-bold ${
              verified ? "text-garl-accent" : "text-red-400"
            }`}
          >
            {verified ? "Cryptographically Verified" : "Verification Failed"}
          </h1>
          <p className="font-mono text-xs text-garl-muted">
            ECDSA-secp256k1 signed · SHA-256 hashed · immutable on GARL Protocol
          </p>
        </div>
      </div>

      {/* Agent header */}
      <div className="mb-6 rounded-xl border border-garl-border bg-garl-surface p-5">
        <div className="mb-3 flex items-center justify-between gap-4">
          <Link
            href={`/agent/${receipt.agent_id}`}
            className="group flex items-center gap-3 min-w-0"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-garl-accent/30 bg-garl-accent/10 font-mono text-sm font-bold text-garl-accent">
              {agentName.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate font-mono text-base font-semibold text-garl-text group-hover:text-garl-accent">
                  {agentName}
                </span>
                <ExternalLink className="h-3 w-3 shrink-0 text-garl-muted opacity-0 transition-opacity group-hover:opacity-100" />
              </div>
              {receipt.agent_framework && (
                <span className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
                  {receipt.agent_framework}
                </span>
              )}
            </div>
          </Link>
          <div className="flex shrink-0 items-center gap-3 font-mono text-xs">
            <span
              className={`rounded border border-current/30 bg-current/[0.05] px-2 py-1 uppercase tracking-wider ${tierColor(tier)}`}
            >
              {tier}
            </span>
            {receipt.agent_trust_score !== null && (
              <span className="text-garl-muted">
                trust{" "}
                <span className="text-garl-text">
                  {receipt.agent_trust_score.toFixed(1)}
                </span>
              </span>
            )}
          </div>
        </div>

        <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
          Task
        </div>
        <p className="font-mono text-sm text-garl-text">{task}</p>
      </div>

      {/* Facts grid */}
      <div className="mb-6 grid gap-3 sm:grid-cols-4">
        <Fact label="Status" value={receipt.status || "—"} accent={receipt.status === "success"} />
        <Fact label="Duration" value={formatDuration(receipt.duration_ms)} />
        <Fact label="Category" value={receipt.category || "—"} />
        <Fact
          label="Signed"
          value={signedAt ? signedAt.replace("T", " ").slice(0, 19) + "Z" : "—"}
        />
      </div>

      {/* Hash */}
      <div className="mb-6 rounded-xl border border-garl-border bg-garl-surface p-5">
        <div className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
          <Shield className="h-3 w-3" />
          SHA-256 Trace Hash
        </div>
        <code className="block break-all rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-[11px] text-garl-text">
          {receipt.trace_hash}
        </code>
        {proof?.signature && (
          <>
            <div className="mt-4 mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
              <Shield className="h-3 w-3" />
              ECDSA Signature
            </div>
            <code className="block break-all rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-[10px] text-garl-muted">
              {proof.signature}
            </code>
          </>
        )}
      </div>

      {/* Share actions (client) */}
      <div className="mb-6">
        <ReceiptActions
          receiptUrl={
            receipt.receipt_url || `${SITE_URL}/r/${receipt.short_hash || params.short}`
          }
          agentName={agentName}
          shortHash={receipt.short_hash || params.short}
          verified={verified}
        />
      </div>

      {/* Footer actions */}
      <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
        <Link
          href={`/verify?h=${receipt.trace_hash}`}
          className="rounded-lg border border-garl-border bg-garl-surface px-4 py-2 text-garl-text transition-colors hover:border-garl-accent/50 hover:text-garl-accent"
        >
          Verify independently
        </Link>
        <Link
          href={`/agent/${receipt.agent_id}`}
          className="rounded-lg border border-garl-border bg-garl-surface px-4 py-2 text-garl-text transition-colors hover:border-garl-accent/50 hover:text-garl-accent"
        >
          View agent profile
        </Link>
        <a
          href={`${API_BASE}/verify/${receipt.trace_hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-garl-muted transition-colors hover:text-garl-accent"
        >
          Raw JSON ↗
        </a>
      </div>
    </div>
  );
}

function Fact({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-garl-border bg-garl-surface px-4 py-3">
      <div className="mb-1 font-mono text-[10px] uppercase tracking-wider text-garl-muted">
        {label}
      </div>
      <div
        className={`font-mono text-sm ${accent ? "text-garl-accent" : "text-garl-text"}`}
      >
        {value}
      </div>
    </div>
  );
}
