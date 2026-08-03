import type { Metadata } from "next";
import { Anchor, ExternalLink, ShieldCheck, AlertTriangle } from "lucide-react";

export const dynamic = "force-dynamic";
export const revalidate = 60;

const API_BASE =
  process.env.GARL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.garl.ai/api/v1";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://garl.ai";

const CONTRACT = "0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2";

type AnchorBatch = {
  batch_id: number;
  onchain_batch_id: number;
  merkle_root: string;
  receipt_count: number;
  built_at: string | null;
  anchored: boolean;
  anchored_at: string | null;
  chain: string | null;
  chain_id: number | null;
  contract_address: string | null;
  tx_hash: string | null;
  explorer_url: string | null;
};

type AnchorsResponse = {
  total: number;
  batches: AnchorBatch[];
};

export const metadata: Metadata = {
  title: "Anchors · GARL Protocol",
  description:
    "Every Merkle batch of Action Receipts anchored on Base mainnet: root, receipt count, transaction hash. Cross-check each row on Basescan.",
  alternates: { canonical: `${SITE_URL}/anchors` },
  openGraph: {
    title: "GARL Protocol — On-chain Anchors",
    description:
      "The full anchor chain: Merkle roots of Action Receipt batches on Base mainnet.",
    url: `${SITE_URL}/anchors`,
    siteName: "GARL Protocol",
    type: "website",
  },
};

async function fetchAnchors(): Promise<AnchorsResponse | null> {
  try {
    const res = await fetch(`${API_BASE}/anchors?limit=200`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as AnchorsResponse;
  } catch {
    return null;
  }
}

function shortHex(h: string, head = 10, tail = 8): string {
  return h.length > head + tail + 2 ? `${h.slice(0, head)}…${h.slice(-tail)}` : h;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

export default async function AnchorsPage() {
  const data = await fetchAnchors();

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <header className="mb-10">
        <p className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-garl-muted">
          <Anchor className="h-3.5 w-3.5" />
          Base mainnet · chain 8453 · revalidates every 60 seconds
        </p>
        <h1 className="mb-3 font-mono text-3xl font-bold text-garl-text">
          On-chain anchors
        </h1>
        <p className="max-w-3xl font-mono text-sm leading-relaxed text-garl-muted">
          Every batch of Action Receipts is rolled into a Merkle tree and its
          root anchored on Base mainnet via the{" "}
          <a
            className="underline hover:text-garl-accent"
            href={`https://basescan.org/address/${CONTRACT}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            MerkleAnchor contract
          </a>{" "}
          (source-verified). Each row below links its transaction — the{" "}
          <code className="text-garl-text">Anchored</code> event's root must
          equal the Merkle root shown. Per-receipt inclusion proofs:{" "}
          <code className="text-garl-text">
            GET /api/v1/receipts/{"{id}"}/proof
          </code>
          . Raw data:{" "}
          <a
            className="underline hover:text-garl-accent"
            href="https://api.garl.ai/api/v1/anchors"
          >
            /api/v1/anchors
          </a>
          .
        </p>
      </header>

      {!data ? (
        <div className="rounded-xl border border-dashed border-garl-border bg-garl-surface p-8 text-center">
          <p className="font-mono text-sm text-garl-muted">
            The anchors endpoint is unreachable right now. Try{" "}
            <a
              className="underline hover:text-garl-accent"
              href="https://api.garl.ai/api/v1/anchors"
            >
              /api/v1/anchors
            </a>{" "}
            directly, or check the contract on{" "}
            <a
              className="underline hover:text-garl-accent"
              href={`https://basescan.org/address/${CONTRACT}`}
            >
              Basescan
            </a>
            .
          </p>
        </div>
      ) : (
        <>
          <section className="mb-8 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-garl-border bg-garl-surface p-4">
              <p className="font-mono text-[11px] uppercase tracking-wider text-garl-muted">
                Anchored batches
              </p>
              <p className="mt-1 font-mono text-2xl font-bold text-garl-text">
                {data.batches.filter((b) => b.anchored).length}
              </p>
            </div>
            <div className="rounded-xl border border-garl-border bg-garl-surface p-4">
              <p className="font-mono text-[11px] uppercase tracking-wider text-garl-muted">
                Receipts anchored
              </p>
              <p className="mt-1 font-mono text-2xl font-bold text-garl-text">
                {data.batches
                  .filter((b) => b.anchored)
                  .reduce((n, b) => n + (b.receipt_count || 0), 0)}
              </p>
            </div>
            <div className="rounded-xl border border-garl-border bg-garl-surface p-4">
              <p className="font-mono text-[11px] uppercase tracking-wider text-garl-muted">
                Latest anchor
              </p>
              <p className="mt-1 font-mono text-sm font-bold text-garl-text">
                {fmtDate(
                  data.batches.find((b) => b.anchored)?.anchored_at ?? null,
                )}
              </p>
            </div>
          </section>

          <div className="overflow-x-auto rounded-xl border border-garl-border bg-garl-surface">
            <table className="w-full font-mono text-sm">
              <thead>
                <tr className="border-b border-garl-border text-left text-[11px] uppercase tracking-wider text-garl-muted">
                  <th className="px-4 py-3">Batch</th>
                  <th className="px-4 py-3">Merkle root</th>
                  <th className="px-4 py-3">Receipts</th>
                  <th className="px-4 py-3">Anchored (UTC)</th>
                  <th className="px-4 py-3">Base tx</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-garl-border/50">
                {data.batches.map((b) => (
                  <tr key={b.batch_id} className="text-garl-text">
                    <td className="px-4 py-3">#{b.onchain_batch_id}</td>
                    <td className="px-4 py-3">
                      <span title={b.merkle_root}>{shortHex(b.merkle_root)}</span>
                    </td>
                    <td className="px-4 py-3">{b.receipt_count}</td>
                    <td className="px-4 py-3 text-garl-muted">
                      {fmtDate(b.anchored_at)}
                    </td>
                    <td className="px-4 py-3">
                      {b.anchored && b.explorer_url ? (
                        <a
                          className="inline-flex items-center gap-1.5 text-garl-accent underline-offset-2 hover:underline"
                          href={b.explorer_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                          {shortHex(b.tx_hash || "", 8, 6)}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 text-amber-300">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          built, not yet broadcast
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
                {data.batches.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-8 text-center text-garl-muted"
                    >
                      No batches yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <p className="mt-6 font-mono text-[11px] leading-relaxed text-garl-muted">
            Anchoring runs weekly (Mondays 03:17 UTC) via a public GitHub
            Actions workflow. Leaf ={" "}
            <code className="text-garl-text">SHA-256(0x00 ‖ output_hash)</code>,
            node ={" "}
            <code className="text-garl-text">SHA-256(0x01 ‖ left ‖ right)</code>{" "}
            (RFC 6962 domain separation). Contract:{" "}
            <a
              className="underline hover:text-garl-accent"
              href={`https://basescan.org/address/${CONTRACT}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {CONTRACT}
            </a>
          </p>
        </>
      )}
    </div>
  );
}
