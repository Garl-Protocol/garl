import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const results: Record<string, string> = {};
  const urls = [
    process.env.SITEMAP_API_URL,
    process.env.NEXT_PUBLIC_API_URL,
    "https://api.garl.ai/api/v1",
    "https://backend-production-f4838.up.railway.app/api/v1",
  ].filter(Boolean) as string[];

  for (const url of urls) {
    try {
      const res = await fetch(`${url}/leaderboard?limit=3`, {
        cache: "no-store",
        headers: { "Accept": "application/json" },
      });
      const text = await res.text();
      results[url] = `status=${res.status} length=${text.length} preview=${text.slice(0, 100)}`;
    } catch (e) {
      results[url] = `ERROR: ${e instanceof Error ? e.message : String(e)}`;
    }
  }

  return NextResponse.json({
    env_sitemap_api_url: process.env.SITEMAP_API_URL || "(not set)",
    env_next_public_api_url: process.env.NEXT_PUBLIC_API_URL || "(not set)",
    results,
  });
}
