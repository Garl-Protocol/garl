import { MetadataRoute } from "next";

export const dynamic = "force-dynamic";

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

  const apiUrl = process.env.SITEMAP_API_URL || "https://api.garl.ai/api/v1";
  let agentPages: MetadataRoute.Sitemap = [];
  try {
    const res = await fetch(`${apiUrl}/leaderboard?limit=200`, {
      cache: "no-store",
      headers: { "User-Agent": "GARL-Sitemap-Generator/1.0" },
    });
    if (res.ok) {
      const json = await res.json();
      const agents: { id: string }[] = Array.isArray(json) ? json : json.data || [];
      agentPages = agents
        .filter((a) => a.id)
        .map((a) => ({
          url: `${baseUrl}/agent/${a.id}`,
          lastModified: now,
          changeFrequency: "daily" as const,
          priority: 0.7,
        }));
    }
  } catch {
    // API unavailable — return static pages only
  }

  return [...staticPages, ...agentPages];
}
