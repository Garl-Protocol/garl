import { MetadataRoute } from "next";

export const dynamic = "force-dynamic";
export const revalidate = 3600;

const API_URL = "https://api.garl.ai/api/v1";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = "https://garl.ai";
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: now, changeFrequency: "daily", priority: 1.0 },
    { url: `${baseUrl}/leaderboard`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/dashboard`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/docs`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${baseUrl}/verify`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${baseUrl}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${baseUrl}/playground`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${baseUrl}/simulator`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${baseUrl}/compliance`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
    { url: `${baseUrl}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];

  let agentPages: MetadataRoute.Sitemap = [];
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    const res = await fetch(`${API_URL}/leaderboard?limit=200`, {
      signal: controller.signal,
      next: { revalidate: 3600 },
    });
    clearTimeout(timeout);
    if (res.ok) {
      const json = await res.json();
      const agents = Array.isArray(json) ? json : json.data || [];
      agentPages = agents
        .filter((a: { id?: string }) => a.id)
        .map((a: { id: string }) => ({
          url: `${baseUrl}/agent/${a.id}`,
          lastModified: now,
          changeFrequency: "daily" as const,
          priority: 0.7,
        }));
    }
  } catch {
    // API unavailable — return static pages only, don't crash the sitemap
  }

  return [...staticPages, ...agentPages];
}
