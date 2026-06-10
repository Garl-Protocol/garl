"use client";

import { motion } from "framer-motion";
import { useState, useCallback } from "react";
import { Shield, CheckCircle, XCircle, Copy, Check, Search, ExternalLink, Link2 } from "lucide-react";
import posthog from "posthog-js";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

interface VerifyResult {
  verified: boolean;
  trace_hash: string;
  trace_id: string;
  agent_id: string;
  status: string;
  category: string;
  created_at: string;
  certificate: {
    "@context": string;
    "@type": string;
    payload: Record<string, unknown>;
    proof: {
      type: string;
      created: number;
      publicKey: string;
      signature: string;
    };
  };
  public_key: string;
}

interface AnchorResult {
  chain: string;
  chain_id: number;
  contract_address: string;
  tx_hash: string;
  merkle_root: string;
  anchored_at: string;
  verify_proof_args: {
    batchId: number;
    leaf: string;
    proofSiblings: string[];
    proofPositions: boolean[];
  };
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1">
      <span className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
        {label}
      </span>
      <div
        className="group flex cursor-pointer items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2"
        onClick={() => {
          navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
      >
        <code className="min-w-0 flex-1 truncate font-mono text-[11px] text-garl-text">
          {value}
        </code>
        {copied ? (
          <Check className="h-3 w-3 shrink-0 text-garl-accent" />
        ) : (
          <Copy className="h-3 w-3 shrink-0 text-garl-muted opacity-0 transition-opacity group-hover:opacity-100" />
        )}
      </div>
    </div>
  );
}

export default function VerifyPage() {
  const [hash, setHash] = useState("");
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [anchor, setAnchor] = useState<AnchorResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleVerify = useCallback(async () => {
    const trimmed = hash.trim();
    if (!trimmed) return;
    setLoading(true);
    setResult(null);
    setAnchor(null);
    setError(null);
    // A trace hash resolves /verify; an Action Receipt id / output_hash resolves
    // /receipts/{id}/proof (on-chain anchor). Try both — either or both may hit.
    const [traceRes, proofRes] = await Promise.allSettled([
      fetch(`${API_BASE}/verify/${trimmed}`),
      fetch(`${API_BASE}/receipts/${trimmed}/proof`),
    ]);
    try {
      let foundTrace = false;
      let foundAnchor = false;
      if (traceRes.status === "fulfilled" && traceRes.value.ok) {
        setResult(await traceRes.value.json());
        foundTrace = true;
      }
      if (proofRes.status === "fulfilled" && proofRes.value.ok) {
        setAnchor(await proofRes.value.json());
        foundAnchor = true;
      }
      posthog.capture("verify_submitted", { found_trace: foundTrace, found_anchor: foundAnchor });
      if (foundAnchor) posthog.capture("onchain_proof_viewed");
      if (!foundTrace && !foundAnchor) {
        if (traceRes.status === "fulfilled") {
          const data = await traceRes.value.json().catch(() => null);
          setError(data?.detail || `HTTP ${traceRes.value.status}`);
        } else {
          setError("Network error");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  }, [hash]);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <motion.div initial={false} animate={{ opacity: 1, y: 0 }}>
        <h1 className="mb-2 font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> verify
        </h1>
        <p className="mb-8 font-mono text-sm text-garl-muted">
          Don&apos;t trust, verify. Paste any trace hash to cryptographically validate its authenticity.
        </p>

        {/* Search box */}
        <div className="mb-8 flex gap-3">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-garl-muted" />
            <input
              type="text"
              placeholder="Paste a trace hash, or an Action Receipt id / output hash..."
              value={hash}
              onChange={(e) => setHash(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleVerify()}
              className="w-full rounded-xl border border-garl-border bg-garl-surface py-3 pl-10 pr-4 font-mono text-sm text-garl-text placeholder:text-garl-muted/40 focus:border-garl-accent focus:outline-none"
            />
          </div>
          <button
            onClick={handleVerify}
            disabled={loading || !hash.trim()}
            className="flex items-center gap-2 rounded-xl bg-garl-accent px-6 py-3 font-mono text-sm font-semibold text-garl-bg transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            <Shield className="h-4 w-4" />
            {loading ? "Verifying..." : "Verify"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 flex items-center gap-3 rounded-xl border border-red-500/30 bg-red-500/[0.05] px-5 py-4"
          >
            <XCircle className="h-5 w-5 shrink-0 text-red-400" />
            <span className="font-mono text-sm text-red-300">{error}</span>
          </motion.div>
        )}

        {/* Result */}
        {result && (
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-5"
          >
            {/* Status banner */}
            <div
              className={`flex items-center gap-4 rounded-xl border p-5 ${
                result.verified
                  ? "border-garl-accent/30 bg-garl-accent/[0.05]"
                  : "border-red-500/30 bg-red-500/[0.05]"
              }`}
            >
              {result.verified ? (
                <CheckCircle className="h-8 w-8 shrink-0 text-garl-accent" />
              ) : (
                <XCircle className="h-8 w-8 shrink-0 text-red-400" />
              )}
              <div>
                <h2
                  className={`font-mono text-lg font-bold ${
                    result.verified ? "text-garl-accent" : "text-red-400"
                  }`}
                >
                  {result.verified
                    ? "Cryptographically Verified"
                    : "Verification Failed"}
                </h2>
                <p className="font-mono text-xs text-garl-muted">
                  {result.verified
                    ? "This execution trace has a valid ECDSA-secp256k1 signature from GARL Protocol."
                    : "The signature could not be verified. This trace may have been tampered with."}
                </p>
              </div>
            </div>

            {/* Trace details */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h3 className="mb-4 font-mono text-xs uppercase tracking-wider text-garl-muted">
                Trace Details
              </h3>
              <div className="grid gap-4 sm:grid-cols-2">
                <CopyField label="Trace Hash" value={result.trace_hash} />
                <CopyField label="Trace ID" value={result.trace_id} />
                <CopyField label="Agent ID" value={result.agent_id} />
                <div className="space-y-1">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
                    Status / Category
                  </span>
                  <div className="flex items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-[11px]">
                    <span
                      className={
                        result.status === "success"
                          ? "text-garl-accent"
                          : result.status === "failure"
                            ? "text-red-400"
                            : "text-yellow-400"
                      }
                    >
                      {result.status}
                    </span>
                    <span className="text-garl-border">|</span>
                    <span className="text-garl-muted">{result.category}</span>
                    <span className="text-garl-border">|</span>
                    <span className="text-garl-muted">
                      {new Date(result.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
                <div className="space-y-1">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
                    Agent Profile
                  </span>
                  <a
                    href={`/agent/${result.agent_id}`}
                    className="flex items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-[11px] text-garl-accent transition-colors hover:border-garl-accent/30"
                  >
                    View agent <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>

            {/* Cryptographic proof */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <h3 className="mb-4 font-mono text-xs uppercase tracking-wider text-garl-muted">
                Cryptographic Proof
              </h3>
              <div className="space-y-3">
                <div className="flex items-center gap-3 font-mono text-xs">
                  <span className="rounded bg-garl-accent/10 px-2 py-0.5 text-garl-accent">
                    {result.certificate.proof.type}
                  </span>
                  <span className="text-garl-muted">
                    Signed at{" "}
                    {new Date(
                      result.certificate.proof.created * 1000
                    ).toISOString()}
                  </span>
                </div>
                <CopyField
                  label="ECDSA Signature"
                  value={result.certificate.proof.signature}
                />
                <CopyField
                  label="Public Key"
                  value={result.certificate.proof.publicKey}
                />
              </div>
            </div>

            {/* Raw certificate */}
            <details className="rounded-xl border border-garl-border bg-garl-surface">
              <summary className="cursor-pointer px-5 py-3 font-mono text-xs uppercase tracking-wider text-garl-muted hover:text-garl-accent">
                Raw Certificate JSON
              </summary>
              <pre className="overflow-x-auto border-t border-garl-border px-5 py-4 font-mono text-[11px] leading-relaxed text-garl-text">
                {JSON.stringify(result.certificate, null, 2)}
              </pre>
            </details>
          </motion.div>
        )}

        {/* On-chain anchor (Action Receipts anchored on Base mainnet) */}
        {anchor && (
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            className="mt-5 rounded-xl border border-garl-accent/30 bg-garl-accent/[0.05] p-5"
          >
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Link2 className="h-4 w-4 text-garl-accent" />
              <h3 className="font-mono text-xs uppercase tracking-wider text-garl-muted">
                On-Chain Anchor
              </h3>
              <span className="rounded border border-garl-accent/30 bg-garl-accent/10 px-2 py-0.5 font-mono text-[11px] text-garl-accent">
                Base mainnet
              </span>
              <a
                href={`https://basescan.org/tx/${anchor.tx_hash}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => posthog.capture("basescan_click", { tx_hash: anchor.tx_hash })}
                className="flex items-center gap-1 font-mono text-[11px] text-garl-accent hover:underline"
              >
                View transaction <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <p className="mb-4 font-mono text-[11px] leading-relaxed text-garl-muted">
              This receipt&apos;s batch Merkle root is anchored on Base. Inclusion is
              verifiable against the on-chain root via{" "}
              <code className="text-garl-text">MerkleAnchor.verifyProof</code> — independently of GARL.
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <CopyField label="Merkle Root" value={anchor.merkle_root} />
              <CopyField label="Contract" value={anchor.contract_address} />
            </div>
            <details className="mt-4 rounded-lg border border-garl-border bg-garl-bg">
              <summary className="cursor-pointer px-4 py-2 font-mono text-[10px] uppercase tracking-wider text-garl-muted hover:text-garl-accent">
                verifyProof args (paste into a Base call)
              </summary>
              <pre className="overflow-x-auto border-t border-garl-border px-4 py-3 font-mono text-[11px] leading-relaxed text-garl-text">
                {JSON.stringify(anchor.verify_proof_args, null, 2)}
              </pre>
            </details>
          </motion.div>
        )}

        {/* Empty state */}
        {!result && !anchor && !error && !loading && (
          <div className="mt-12 text-center">
            <Shield className="mx-auto mb-4 h-12 w-12 text-garl-border" />
            <p className="font-mono text-sm text-garl-muted">
              Every GARL trace is SHA-256 hashed and ECDSA signed.
            </p>
            <p className="mt-1 font-mono text-xs text-garl-muted/60">
              You can find trace hashes in the{" "}
              <a href="/dashboard" className="text-garl-accent underline">
                dashboard feed
              </a>
              ,{" "}
              <a
                href={`${API_BASE}/feed?limit=5`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-garl-accent underline"
              >
                feed API
              </a>
              , or any execution certificate.
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}
