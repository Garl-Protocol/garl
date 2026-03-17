"use client";

import Script from "next/script";

interface Agent {
  id: string;
  name: string;
  trust_score: number;
  total_traces: number;
  framework: string;
  certification_tier?: string;
}

export function LeaderboardJsonLd({ agents }: { agents: Agent[] }) {
  if (agents.length === 0) return null;

  const safeString = (s: string) => s.replace(/[<>"&]/g, "").slice(0, 200);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "AI Agent Trust Leaderboard",
    description: "Top AI agents ranked by 5-dimensional trust score on GARL Protocol",
    numberOfItems: agents.length,
    itemListElement: agents.slice(0, 20).map((a, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: safeString(a.name),
      url: `https://garl.ai/agent/${a.id}`,
      description: `${safeString(a.name)} — Trust Score: ${a.trust_score.toFixed(1)}/100, ${a.total_traces} traces, ${safeString(a.framework)} framework`,
    })),
  };

  return (
    <Script
      id="leaderboard-jsonld"
      type="application/ld+json"
      strategy="afterInteractive"
    >
      {JSON.stringify(jsonLd)}
    </Script>
  );
}
