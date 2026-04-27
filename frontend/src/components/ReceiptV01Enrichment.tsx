"use client";

/**
 * Receipt page enrichment — shows side_effect badge + Undo button when the
 * receipt is an Action Receipt v0.1.
 *
 * Why client-side: the legacy `/verify/{hash}` endpoint returns the trace
 * shape (no side_effect). The new `/receipts/{hash}/cert.json` endpoint
 * returns the v0.1 envelope. Until the new endpoint is the default, this
 * component graceful-degrades: it tries the v0.1 cert, renders nothing on
 * 404/network error.
 */

import { useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck, ShieldX, Undo2 } from "lucide-react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

type Envelope = {
  receipt_id: string;
  version: string;
  side_effect?: "none" | "reversible" | "irreversible";
  capability_request?: { token_hash?: string; side_effect_class?: string };
  policy_decision?: "allowed" | "denied" | "requires_human";
  attestations?: string[];
};

const SIDE_EFFECT_META: Record<
  NonNullable<Envelope["side_effect"]>,
  { label: string; tone: string; icon: typeof ShieldCheck; help: string }
> = {
  none: {
    label: "No side effect",
    tone: "border-emerald-500/40 bg-emerald-500/[0.05] text-emerald-300",
    icon: ShieldCheck,
    help: "Read-only action. Nothing in the world changed.",
  },
  reversible: {
    label: "Reversible",
    tone: "border-amber-500/40 bg-amber-500/[0.05] text-amber-300",
    icon: ShieldAlert,
    help:
      "State changed, but a single follow-up action cancels it. UETA §10(b) undo path may apply.",
  },
  irreversible: {
    label: "Irreversible",
    tone: "border-red-500/40 bg-red-500/[0.05] text-red-300",
    icon: ShieldX,
    help: "No automatic undo path. Disputes only via the operator.",
  },
};

export default function ReceiptV01Enrichment({ hash }: { hash: string }) {
  const [env, setEnv] = useState<Envelope | null>(null);
  const [missing, setMissing] = useState(false);
  const [undoState, setUndoState] = useState<{
    busy: boolean;
    result: string | null;
    error: string | null;
  }>({ busy: false, result: null, error: null });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(
          `${API_BASE}/receipts/${encodeURIComponent(hash)}/cert.json`,
          { cache: "no-store" },
        );
        if (cancelled) return;
        if (!res.ok) {
          setMissing(true);
          return;
        }
        const json = (await res.json()) as Envelope;
        // Only treat it as v0.1 if it actually announces v0.1
        if (json && typeof json.version === "string" && json.version.includes("action-receipt/v0.1")) {
          setEnv(json);
        } else {
          setMissing(true);
        }
      } catch {
        if (!cancelled) setMissing(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hash]);

  if (missing || !env || !env.side_effect) return null;

  const meta = SIDE_EFFECT_META[env.side_effect];
  const Icon = meta.icon;

  async function handleUndo() {
    if (!env) return;
    if (!confirm("Trigger UETA §10(b) consumer-undo for this receipt?")) return;
    setUndoState({ busy: true, result: null, error: null });
    try {
      const res = await fetch(
        `${API_BASE}/receipts/${encodeURIComponent(env.receipt_id)}/undo`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ reason: "consumer-initiated-undo" }),
        },
      );
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json.detail || `HTTP ${res.status}`);
      }
      setUndoState({
        busy: false,
        result: `Undo recorded — compensation ${json.compensation_id}. Status: ${json.status}.`,
        error: null,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setUndoState({ busy: false, result: null, error: msg });
    }
  }

  return (
    <div className="mb-6 rounded-xl border border-garl-border bg-garl-surface p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 font-mono text-xs uppercase tracking-wider ${meta.tone}`}>
          <Icon className="h-3.5 w-3.5" />
          {meta.label}
        </div>
        <span className="font-mono text-[10px] uppercase tracking-wider text-garl-muted">
          Action Receipt v0.1
        </span>
      </div>
      <p className="mb-4 font-mono text-xs text-garl-muted">{meta.help}</p>

      {/* Capability + policy attestation row */}
      {(env.capability_request?.token_hash || env.policy_decision || (env.attestations && env.attestations.length > 0)) && (
        <div className="mb-4 grid gap-2 sm:grid-cols-3">
          {env.capability_request?.token_hash && (
            <Tag label="Capability" value={env.capability_request.token_hash.slice(0, 12) + "…"} />
          )}
          {env.policy_decision && (
            <Tag label="Policy" value={env.policy_decision} />
          )}
          {env.attestations && env.attestations.length > 0 && (
            <Tag label="Attestations" value={env.attestations.join(", ")} />
          )}
        </div>
      )}

      {env.side_effect === "reversible" && (
        <div className="space-y-2">
          <button
            onClick={handleUndo}
            disabled={undoState.busy || !!undoState.result}
            className="inline-flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/[0.08] px-4 py-2 font-mono text-xs uppercase tracking-wider text-amber-300 transition-colors hover:border-amber-500/60 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Undo2 className="h-3.5 w-3.5" />
            {undoState.busy ? "Triggering…" : "Undo this action (UETA §10(b))"}
          </button>
          {undoState.result && (
            <p className="font-mono text-xs text-emerald-300">{undoState.result}</p>
          )}
          {undoState.error && (
            <p className="font-mono text-xs text-red-300">Undo refused: {undoState.error}</p>
          )}
          <p className="font-mono text-[10px] text-garl-muted">
            Triggers the recorded compensation. The actual reversal action runs on the
            tool server (Stripe refund, Calendly cancel, etc.).
          </p>
        </div>
      )}

      {env.side_effect === "irreversible" && (
        <p className="font-mono text-xs text-red-300/80">
          No automatic undo path. Disputes go through the operator.
        </p>
      )}
    </div>
  );
}

function Tag({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-garl-border bg-garl-bg px-3 py-2">
      <div className="mb-0.5 font-mono text-[9px] uppercase tracking-wider text-garl-muted">
        {label}
      </div>
      <div className="break-all font-mono text-[11px] text-garl-text">{value}</div>
    </div>
  );
}
