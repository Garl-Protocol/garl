import { MetadataRoute } from "next";

export const dynamic = "force-dynamic";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const baseUrl = "https://garl.ai";
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    { url: baseUrl, lastModified: now, changeFrequency: "daily", priority: 1.0 },
    { url: `${baseUrl}/for-code`, lastModified: now, changeFrequency: "daily", priority: 0.95 },
    { url: `${baseUrl}/connect`, lastModified: now, changeFrequency: "weekly", priority: 0.95 },
    { url: `${baseUrl}/registry`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/dashboard`, lastModified: now, changeFrequency: "hourly", priority: 0.9 },
    { url: `${baseUrl}/docs`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${baseUrl}/compliance`, lastModified: now, changeFrequency: "weekly", priority: 0.8 },
    { url: `${baseUrl}/verify`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${baseUrl}/anchors`, lastModified: now, changeFrequency: "weekly", priority: 0.7 },
    { url: `${baseUrl}/compare`, lastModified: now, changeFrequency: "weekly", priority: 0.6 },
    { url: `${baseUrl}/playground`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${baseUrl}/simulator`, lastModified: now, changeFrequency: "monthly", priority: 0.5 },
    { url: `${baseUrl}/stats`, lastModified: now, changeFrequency: "hourly", priority: 0.7 },
    { url: `${baseUrl}/privacy`, lastModified: now, changeFrequency: "yearly", priority: 0.3 },
  ];

  const apiUrl = process.env.SITEMAP_API_URL || process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";
  const allAgents: { id: string }[] = [];

  try {
    let offset = 0;
    const limit = 100;
    let hasMore = true;

    while (hasMore && offset < 1000) {
      const res = await fetch(`${apiUrl}/leaderboard?limit=${limit}&offset=${offset}`, {
        cache: "no-store",
        headers: { "Accept": "application/json" },
      });
      if (!res.ok) break;
      const json = await res.json();
      const agents: { id: string }[] = Array.isArray(json) ? json : json.data || [];
      allAgents.push(...agents.filter((a) => a.id));
      hasMore = json.has_more === true && agents.length === limit;
      offset += limit;
    }
  } catch (e) {
    console.error("[Sitemap] Failed to fetch agents:", e instanceof Error ? e.message : e);
  }

  const agentPages: MetadataRoute.Sitemap = allAgents.map((a) => ({
    url: `${baseUrl}/agent/${a.id}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  const recentReceipts: { short_hash: string; created_at: string }[] = [];
  try {
    const res = await fetch(`${apiUrl}/feed?limit=100`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (res.ok) {
      const json = await res.json();
      const items: Array<Record<string, unknown>> = Array.isArray(json) ? json : (json.data as Array<Record<string, unknown>>) || [];
      for (const item of items) {
        const short = (item.short_hash as string) || ((item.trace_hash as string)?.slice(0, 8));
        if (short) {
          recentReceipts.push({
            short_hash: short,
            created_at: (item.created_at as string) || now.toISOString(),
          });
        }
      }
    }
  } catch (e) {
    console.error("[Sitemap] Failed to fetch receipts:", e instanceof Error ? e.message : e);
  }

  const receiptPages: MetadataRoute.Sitemap = recentReceipts.map((r) => ({
    url: `${baseUrl}/r/${r.short_hash}`,
    lastModified: new Date(r.created_at),
    changeFrequency: "yearly" as const,
    priority: 0.5,
  }));

  return [...staticPages, ...agentPages, ...receiptPages];
}
