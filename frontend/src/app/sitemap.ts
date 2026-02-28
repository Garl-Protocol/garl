import { MetadataRoute } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = "https://garl.ai";
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: now, changeFrequency: "daily", priority: 1.0 },
    { url: `${baseUrl}/leaderboard`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/dashboard`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/docs`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${baseUrl}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${baseUrl}/compliance`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
  ];

  let agentPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${API_BASE}/leaderboard?limit=200`, { next: { revalidate: 3600 } });
    if (res.ok) {
      const agents = await res.json();
      agentPages = agents.map((a: { id: string }) => ({
        url: `${baseUrl}/agent/${a.id}`,
        lastModified: now,
        changeFrequency: "daily" as const,
        priority: 0.7,
      }));
    }
  } catch {
    /* API unavailable — static pages only */
  }

  return [...staticPages, ...agentPages];
}
