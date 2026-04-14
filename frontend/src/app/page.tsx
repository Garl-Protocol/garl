import HomePage from "./HomePage";

type LiveStats = {
  total_agents: number;
  total_traces: number;
  top_agent: { name: string; trust_score: number } | null;
};

const API_BASE =
  process.env.GARL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://api.garl.ai/api/v1";

async function fetchInitialStats(): Promise<LiveStats | null> {
  try {
    const res = await fetch(`${API_BASE}/stats`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return (await res.json()) as LiveStats;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialStats = await fetchInitialStats();
  return <HomePage initialStats={initialStats} />;
}
