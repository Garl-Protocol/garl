"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import { Shield } from "lucide-react";
import { formatScore } from "@/lib/utils";
import type { BadgeData } from "@/lib/api";

export default function BadgePage() {
  const params = useParams();
  const agentId = params.id as string;
  const [badge, setBadge] = useState<BadgeData | null>(null);

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchBadge = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/badge/${agentId}`);
      if (res.ok) setBadge(await res.json());
    } catch {
      // noop
    }
  }, [apiBase, agentId]);

  useEffect(() => {
    fetchBadge();
  }, [fetchBadge]);

  if (!badge) {
    return (
      <div
        style={{
          width: 280,
          height: 80,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#12121a",
          color: "#6b7280",
          fontFamily: "monospace",
          fontSize: 12,
          borderRadius: 8,
          border: "1px solid #1e1e2e",
        }}
      >
        Loading...
      </div>
    );
  }

  const scoreColor =
    badge.trust_score >= 80
      ? "#00ff88"
      : badge.trust_score >= 60
      ? "#4ade80"
      : badge.trust_score >= 40
      ? "#ffaa00"
      : "#ff4444";

  return (
    <div
      style={{
        width: 280,
        height: 80,
        background: "#12121a",
        borderRadius: 10,
        border: "1px solid #1e1e2e",
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontFamily: "'JetBrains Mono', monospace",
        color: "#e4e4e7",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 8,
          background: "rgba(0,255,136,0.08)",
          border: "1px solid rgba(0,255,136,0.2)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Shield style={{ width: 20, height: 20, color: "#00ff88" }} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 12,
            fontWeight: 600,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {badge.name}
        </div>
        <div
          style={{
            fontSize: 10,
            color: "#6b7280",
            marginTop: 2,
            display: "flex",
            gap: 8,
            alignItems: "center",
          }}
        >
          <span style={{ color: scoreColor, fontWeight: 700 }}>
            {formatScore(badge.trust_score)}
          </span>
          <span>•</span>
          <span>{badge.success_rate.toFixed(0)}% success</span>
          <span>•</span>
          <span>{badge.total_traces} traces</span>
        </div>
      </div>

      <div
        style={{
          fontSize: 9,
          color: "#00ff88",
          textAlign: "right",
          flexShrink: 0,
        }}
      >
        <div>GARL</div>
        <div>{badge.verified ? "✓ VERIFIED" : "PENDING"}</div>
      </div>
    </div>
  );
}
