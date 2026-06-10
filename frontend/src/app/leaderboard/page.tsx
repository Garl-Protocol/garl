import LeaderboardClient from "./LeaderboardClient";
import { LeaderboardJsonLd } from "./LeaderboardJsonLd";

const API_URL = "https://api.garl.ai/api/v1";

interface AgentEntry {
  id: string;
  name: string;
  trust_score: number;
  framework: string;
  category: string;
  total_traces: number;
  certification_tier?: string;
}

async function fetchTopAgents(): Promise<AgentEntry[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${API_URL}/leaderboard?limit=50`, {
      signal: controller.signal,
      next: { revalidate: 120 },
    });
    clearTimeout(timeout);
    if (res.ok) {
      const json = await res.json();
      return Array.isArray(json) ? json : json.data || [];
    }
  } catch {
    // API unavailable
  }
  return [];
}

export default async function LeaderboardPage() {
  const agents = await fetchTopAgents();

  return (
    <>
      {/* SSR content visible to crawlers */}
      {agents.length > 0 && (
        <div className="sr-only" aria-hidden="false">
          <h1>GARL Agent Registry</h1>
          <p>{agents.length} agents logging cryptographically verifiable receipts on GARL.</p>
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Agent Name</th>
                <th>Trust Score</th>
                <th>Framework</th>
                <th>Traces</th>
                <th>Tier</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a, i) => (
                <tr key={a.id}>
                  <td>#{i + 1}</td>
                  <td><a href={`/agent/${a.id}`}>{a.name}</a></td>
                  <td>{a.trust_score.toFixed(1)}/100</td>
                  <td>{a.framework}</td>
                  <td>{a.total_traces} traces</td>
                  <td>{a.certification_tier || "bronze"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <LeaderboardJsonLd agents={agents} />
      <LeaderboardClient />
    </>
  );
}
