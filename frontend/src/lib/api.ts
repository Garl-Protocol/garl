const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    next: { revalidate: 5 },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export interface TrustDimensions {
  reliability: number;
  security: number;
  speed: number;
  cost_efficiency: number;
  consistency: number;
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  framework: string;
  category: string;
  trust_score: number;
  total_traces: number;
  success_rate: number;
  total_cost_usd?: number;
  avg_duration_ms?: number;
  score_reliability?: number;
  score_security?: number;
  score_speed?: number;
  score_cost_efficiency?: number;
  score_consistency?: number;
  sovereign_id?: string;
  certification_tier?: string;
  anomaly_flags?: Array<{ type: string; severity: string; message: string }>;
  last_trace_at?: string;
  homepage_url: string | null;
  created_at: string;
}

export interface Trace {
  id: string;
  agent_id: string;
  task_description: string;
  status: "success" | "failure" | "partial";
  duration_ms: number;
  trust_delta: number;
  category: string;
  certificate?: Record<string, unknown>;
  runtime_env?: string;
  tool_calls?: Array<{ name: string; duration_ms?: number }>;
  cost_usd?: number;
  created_at: string;
}

export interface LeaderboardEntry extends Agent {
  rank: number;
}

export interface DecayProjection {
  days: number;
  projected_score: number;
}

export interface AgentDetail {
  agent: Agent;
  recent_traces: Trace[];
  reputation_history: Array<{
    trust_score: number;
    event_type: string;
    trust_delta: number;
    score_reliability?: number;
    score_speed?: number;
    score_cost_efficiency?: number;
    score_consistency?: number;
    created_at: string;
  }>;
  decay_projection: DecayProjection[];
}

export interface BadgeData {
  agent_id: string;
  name: string;
  trust_score: number;
  success_rate: number;
  total_traces: number;
  verified: boolean;
}

export interface Stats {
  total_agents: number;
  total_traces: number;
  top_agent: { name: string; trust_score: number } | null;
}

export interface ComplianceReport {
  agent_id: string;
  name: string;
  sovereign_id?: string;
  certification_tier?: string;
  trust_score: number;
  security_score?: number;
  dimensions: {
    reliability: number;
    security: number;
    speed: number;
    cost_efficiency: number;
    consistency: number;
  };
  sla_compliance: {
    uptime_rate?: number;
    avg_response_ms?: number;
    total_executions?: number;
    sla_met?: boolean;
    tier_qualification?: string;
  };
  anomaly_history?: {
    active: Array<{ type?: string; severity?: string; message?: string; archived?: boolean }>;
    archived: Array<{ type?: string; severity?: string; message?: string; archived?: boolean }>;
    total_flags: number;
  };
  security_risks?: Array<{ level: "critical" | "warning" | "info"; message: string; details?: unknown }>;
  endorsement_summary?: {
    received: Array<{
      endorser_id?: string;
      endorser_tier?: string;
      bonus_applied?: number;
      context?: string;
      created_at?: string;
    }>;
    given: Array<{
      target_id?: string;
      endorser_tier?: string;
      bonus_applied?: number;
      context?: string;
      created_at?: string;
    }>;
    total_endorsement_bonus?: number;
  };
  permissions_declared?: string[];
  created_at?: string;
  last_active?: string;
}

export interface RouteRecommendation {
  agent_id: string;
  name: string;
  trust_score: number;
  certification_tier?: string;
  sovereign_id?: string;
  dimensions: {
    reliability: number;
    security: number;
    speed: number;
    cost_efficiency: number;
    consistency: number;
  };
  total_traces: number;
  success_rate: number;
  framework?: string;
}

export interface RouteResponse {
  category: string;
  min_tier: string;
  recommendations: RouteRecommendation[];
}

export async function fetchCompliance(agentId: string, apiKey?: string): Promise<ComplianceReport> {
  const headers: Record<string, string> = {};
  if (apiKey) headers["x-api-key"] = apiKey;
  return fetchAPI<ComplianceReport>(`/agents/${agentId}/compliance`, { headers });
}

export async function fetchRoute(
  category: string,
  minTier: string,
  limit = 3
): Promise<RouteResponse> {
  return fetchAPI<RouteResponse>(
    `/trust/route?category=${encodeURIComponent(category)}&min_tier=${encodeURIComponent(minTier)}&limit=${limit}`
  );
}

export const api = {
  getLeaderboard: (category?: string, limit = 50) =>
    fetchAPI<LeaderboardEntry[]>(
      `/leaderboard?limit=${limit}${category && category !== "all" ? `&category=${category}` : ""}`
    ),

  getAgentDetail: (id: string) => fetchAPI<AgentDetail>(`/agents/${id}/detail`),

  getBadge: (id: string) => fetchAPI<BadgeData>(`/badge/${id}`),

  getFeed: (limit = 30) => fetchAPI<Trace[]>(`/feed?limit=${limit}`),

  getStats: () => fetchAPI<Stats>(`/stats`),

  compareAgents: (ids: string[]) =>
    fetchAPI<Agent[]>(`/compare?agents=${ids.join(",")}`),
};
