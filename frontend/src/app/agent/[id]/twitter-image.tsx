import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "GARL Trust Score";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({ params }: { params: { id: string } }) {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

  let agent: any = null;
  try {
    const res = await fetch(`${apiBase}/agents/${params.id}`, { next: { revalidate: 300 } });
    if (res.ok) agent = await res.json();
  } catch {}

  const name = agent?.name || "Unknown Agent";
  const score = agent?.trust_score != null ? parseFloat(agent.trust_score).toFixed(1) : "—";
  const tier = agent?.certification_tier || "bronze";
  const traces = agent?.total_traces || 0;
  const successRate = agent?.success_rate != null ? `${parseFloat(agent.success_rate).toFixed(1)}%` : "—";

  const scoreColor = parseFloat(score) >= 70 ? "#00ff88" : parseFloat(score) >= 40 ? "#ffaa00" : "#ff4444";

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0a0a1a",
          fontFamily: "monospace",
          padding: "60px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px", marginBottom: "20px" }}>
          <div style={{ fontSize: "24px", color: "#8b8ba7", letterSpacing: "0.1em" }}>GARL PROTOCOL</div>
        </div>
        <div style={{ fontSize: "48px", fontWeight: "bold", color: "#e0e0ff", marginBottom: "16px" }}>{name}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: "12px", marginBottom: "32px" }}>
          <div style={{ fontSize: "80px", fontWeight: "bold", color: scoreColor }}>{score}</div>
          <div style={{ fontSize: "24px", color: "#8b8ba7" }}>/100</div>
        </div>
        <div style={{ display: "flex", gap: "40px", fontSize: "18px", color: "#8b8ba7" }}>
          <div>Tier: <span style={{ color: "#e0e0ff", textTransform: "uppercase" }}>{tier}</span></div>
          <div>Traces: <span style={{ color: "#e0e0ff" }}>{traces}</span></div>
          <div>Success: <span style={{ color: "#e0e0ff" }}>{successRate}</span></div>
        </div>
        <div style={{ marginTop: "40px", fontSize: "16px", color: "#4a4a6a" }}>garl.ai/agent/{params.id.slice(0, 8)}...</div>
      </div>
    ),
    { ...size }
  );
}
