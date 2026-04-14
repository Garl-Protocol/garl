import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

const API_BASE =
  process.env.GARL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.garl.ai/api/v1";

type Receipt = {
  verified: boolean;
  trace_hash: string;
  short_hash: string | null;
  agent_name: string | null;
  agent_framework: string | null;
  agent_tier: string | null;
  agent_trust_score: number | null;
  task_description: string | null;
  status: string | null;
  category: string | null;
  duration_ms: number | null;
};

function formatDuration(ms: number | null): string {
  if (!ms || ms <= 0) return "—";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

function tierColor(tier: string | null): string {
  switch (tier) {
    case "enterprise":
      return "#00ff88";
    case "gold":
      return "#facc15";
    case "silver":
      return "#e4e4e7";
    case "bronze":
    default:
      return "#9ca3af";
  }
}

export async function GET(
  _req: NextRequest,
  { params }: { params: { short: string } },
) {
  const short = params.short;

  let receipt: Receipt | null = null;
  try {
    const res = await fetch(`${API_BASE}/verify/${short}`, {
      next: { revalidate: 60 },
    });
    if (res.ok) receipt = (await res.json()) as Receipt;
  } catch {
    receipt = null;
  }

  const verified = receipt?.verified ?? false;
  const agentName = receipt?.agent_name || "AI agent";
  const tier = receipt?.agent_tier || "unclassified";
  const task = (receipt?.task_description || "Execution trace").slice(0, 110);
  const status = receipt?.status || "—";
  const duration = formatDuration(receipt?.duration_ms ?? null);
  const category = receipt?.category || "other";
  const hash = (receipt?.trace_hash || short).slice(0, 16);
  const trustScore = receipt?.agent_trust_score;

  // Receipt OG cards are immutable per short hash. ImageResponse from
  // next/og already sets `Cache-Control: public, immutable, no-transform,
  // max-age=31536000` by default — which is exactly the right policy for
  // content-addressed images. Don't pass our own `headers` option here:
  // doing so appends to the default, producing a malformed two-directive
  // Cache-Control header in the response.

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#0a0a0f",
          padding: 64,
          fontFamily:
            "'JetBrains Mono', 'Fira Code', ui-monospace, Menlo, monospace",
          color: "#e4e4e7",
          position: "relative",
        }}
      >
        {/* Accent glow */}
        <div
          style={{
            position: "absolute",
            top: -120,
            right: -120,
            width: 420,
            height: 420,
            borderRadius: 9999,
            background: verified
              ? "radial-gradient(circle, rgba(0,255,136,0.18), transparent 70%)"
              : "radial-gradient(circle, rgba(255,68,68,0.18), transparent 70%)",
          }}
        />

        {/* Top row: GARL brand + verified chip */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 40,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 10,
                background: "rgba(0,255,136,0.1)",
                border: "1px solid rgba(0,255,136,0.35)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#00ff88",
                fontSize: 26,
                fontWeight: 700,
              }}
            >
              G
            </div>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
              }}
            >
              <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: 2 }}>
                GARL
              </span>
              <span style={{ fontSize: 14, color: "#6b7280", letterSpacing: 1 }}>
                RECEIPT
              </span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "10px 18px",
              borderRadius: 999,
              background: verified ? "rgba(0,255,136,0.12)" : "rgba(255,68,68,0.12)",
              border: verified
                ? "1px solid rgba(0,255,136,0.4)"
                : "1px solid rgba(255,68,68,0.4)",
              color: verified ? "#00ff88" : "#ff4444",
              fontSize: 18,
              fontWeight: 600,
            }}
          >
            {verified ? "✓ SIGNED" : "✗ UNVERIFIED"}
          </div>
        </div>

        {/* Agent + tier */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 20,
          }}
        >
          <span
            style={{
              fontSize: 44,
              fontWeight: 700,
              color: "#ffffff",
              maxWidth: 780,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {agentName}
          </span>
          <span
            style={{
              fontSize: 18,
              padding: "6px 12px",
              borderRadius: 8,
              border: `1px solid ${tierColor(tier)}55`,
              color: tierColor(tier),
              textTransform: "uppercase",
              letterSpacing: 2,
            }}
          >
            {tier}
          </span>
          {trustScore !== null && trustScore !== undefined && (
            <span style={{ fontSize: 18, color: "#6b7280" }}>
              trust{" "}
              <span style={{ color: "#e4e4e7", fontWeight: 600 }}>
                {trustScore.toFixed(1)}
              </span>
            </span>
          )}
        </div>

        {/* Task */}
        <div
          style={{
            fontSize: 28,
            color: "#e4e4e7",
            lineHeight: 1.35,
            marginBottom: "auto",
            maxWidth: 1060,
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}
        >
          {task}
        </div>

        {/* Bottom row: facts */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            marginTop: 40,
            paddingTop: 28,
            borderTop: "1px solid #1e1e2e",
          }}
        >
          <div style={{ display: "flex", gap: 36 }}>
            <Fact label="STATUS" value={status} accent={status === "success"} />
            <Fact label="DURATION" value={duration} />
            <Fact label="CATEGORY" value={category} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
            <span style={{ fontSize: 13, color: "#6b7280", letterSpacing: 1 }}>
              ECDSA-SECP256K1 · SHA-256
            </span>
            <span
              style={{
                fontSize: 16,
                color: "#e4e4e7",
                marginTop: 4,
                fontFamily: "ui-monospace, Menlo, monospace",
              }}
            >
              {hash}…
            </span>
          </div>
        </div>
      </div>
    ),
    { width: 1200, height: 630 },
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
    <div style={{ display: "flex", flexDirection: "column" }}>
      <span style={{ fontSize: 13, color: "#6b7280", letterSpacing: 1.5 }}>
        {label}
      </span>
      <span
        style={{
          fontSize: 26,
          color: accent ? "#00ff88" : "#e4e4e7",
          marginTop: 4,
          fontWeight: 600,
        }}
      >
        {value}
      </span>
    </div>
  );
}
