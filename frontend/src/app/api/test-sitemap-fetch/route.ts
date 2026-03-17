import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const apiUrl = process.env.SITEMAP_API_URL || process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";
  const fullUrl = `${apiUrl}/leaderboard?limit=200`;

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    const res = await fetch(fullUrl, {
      signal: controller.signal,
      cache: "no-store",
      method: "GET",
      headers: {
        "Accept": "application/json",
        "User-Agent": "GARL-Sitemap-Generator/1.0",
      },
    });
    clearTimeout(timeout);

    const text = await res.text();
    let agentCount = 0;
    let agentIds: string[] = [];

    if (res.ok) {
      try {
        const json = JSON.parse(text);
        const agents = Array.isArray(json) ? json : json.data || [];
        agentCount = agents.length;
        agentIds = agents.slice(0, 3).map((a: { id: string }) => a.id);
      } catch {
        // parse error
      }
    }

    return NextResponse.json({
      url: fullUrl,
      status: res.status,
      ok: res.ok,
      bodyLength: text.length,
      agentCount,
      sampleIds: agentIds,
      bodyPreview: text.slice(0, 200),
    });
  } catch (e) {
    return NextResponse.json({
      url: fullUrl,
      error: e instanceof Error ? e.message : String(e),
    }, { status: 500 });
  }
}
