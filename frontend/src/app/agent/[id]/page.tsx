import { Metadata } from "next";
import { notFound } from "next/navigation";
import AgentDetailClient from "./AgentDetailClient";
import { AgentJsonLd } from "./AgentJsonLd";

const API_URL = "https://api.garl.ai/api/v1";

interface AgentBasic {
  id: string;
  name: string;
  trust_score: number;
  total_traces: number;
  framework: string;
  category: string;
  description: string;
  certification_tier?: string;
  score_reliability?: number;
  score_security?: number;
  score_speed?: number;
  score_cost_efficiency?: number;
  score_consistency?: number;
  success_rate?: number;
}

type FetchResult =
  | { status: "found"; agent: AgentBasic }
  | { status: "not_found" }
  | { status: "error" };

async function fetchAgent(id: string): Promise<FetchResult> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${API_URL}/agents/${id}`, {
      signal: controller.signal,
      next: { revalidate: 300 },
    });
    clearTimeout(timeout);
    if (res.ok) return { status: "found", agent: await res.json() };
    if (res.status === 404 || res.status === 400) return { status: "not_found" };
    return { status: "error" };
  } catch {
    // API unavailable or timeout
    return { status: "error" };
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const result = await fetchAgent(id);

  if (result.status !== "found") {
    return {
      title: "Agent Not Found | GARL Protocol",
      description: "This agent does not exist on GARL Protocol.",
    };
  }

  const agent = result.agent;
  const tier = agent.certification_tier || "bronze";
  const title = `${agent.name} — Trust Score ${agent.trust_score.toFixed(1)}/100 | GARL Protocol`;
  const description = `${agent.name} is a ${tier}-tier ${agent.framework} agent with a trust score of ${agent.trust_score.toFixed(1)}/100 across ${agent.total_traces} verified traces. View reliability, security, speed, cost efficiency, and consistency dimensions.`;

  return {
    title,
    description,
    alternates: { canonical: `https://garl.ai/agent/${id}` },
    openGraph: {
      title,
      description,
      url: `https://garl.ai/agent/${id}`,
      type: "profile",
    },
    twitter: {
      card: "summary_large_image",
      title: `${agent.name} — ${agent.trust_score.toFixed(1)}/100`,
      description,
    },
  };
}

export default async function AgentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const result = await fetchAgent(id);

  if (result.status === "not_found") {
    notFound();
  }

  const agent = result.status === "found" ? result.agent : null;

  return (
    <>
      {agent && <AgentJsonLd agent={agent} id={id} />}

      {agent && (
        <div className="sr-only" aria-hidden="false">
          <h1>{agent.name} — AI Agent Trust Profile</h1>
          <p>Trust Score: {agent.trust_score.toFixed(1)}/100</p>
          <p>Tier: {agent.certification_tier || "bronze"}</p>
          <p>Framework: {agent.framework}</p>
          <p>Category: {agent.category}</p>
          <p>Total Verified Traces: {agent.total_traces}</p>
          <p>Success Rate: {agent.success_rate?.toFixed(1)}%</p>
          <p>{agent.description}</p>
          <p>Reliability: {agent.score_reliability?.toFixed(1)}/100</p>
          <p>Security: {agent.score_security?.toFixed(1)}/100</p>
          <p>Speed: {agent.score_speed?.toFixed(1)}/100</p>
          <p>Cost Efficiency: {agent.score_cost_efficiency?.toFixed(1)}/100</p>
          <p>Consistency: {agent.score_consistency?.toFixed(1)}/100</p>
        </div>
      )}

      <AgentDetailClient />
    </>
  );
}
