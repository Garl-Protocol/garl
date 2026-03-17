"use client";

import Script from "next/script";

interface AgentJsonLdProps {
  agent: {
    name: string;
    description: string;
    trust_score: number;
    total_traces: number;
    framework: string;
    category: string;
    certification_tier?: string;
  };
  id: string;
}

export function AgentJsonLd({ agent, id }: AgentJsonLdProps) {
  const safeString = (s: string) => s.replace(/[<>"&]/g, "").slice(0, 200);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: safeString(agent.name),
    description: safeString(agent.description),
    applicationCategory: "AI Agent",
    url: `https://garl.ai/agent/${id}`,
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: Number(agent.trust_score.toFixed(1)),
      bestRating: 100,
      worstRating: 0,
      ratingCount: Number(agent.total_traces),
    },
    additionalProperty: [
      { "@type": "PropertyValue", name: "Framework", value: safeString(agent.framework) },
      { "@type": "PropertyValue", name: "Category", value: safeString(agent.category) },
      { "@type": "PropertyValue", name: "Certification Tier", value: safeString(agent.certification_tier || "bronze") },
    ],
  };

  return (
    <Script
      id={`agent-jsonld-${id}`}
      type="application/ld+json"
      strategy="afterInteractive"
    >
      {JSON.stringify(jsonLd)}
    </Script>
  );
}
