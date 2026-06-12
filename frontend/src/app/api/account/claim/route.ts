import { auth, clerkClient } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

// Claim an agent to the signed-in account. The agent's API key proves the
// caller controls it; the backend resolves key -> agent (GET /agents/me).
// Ownership is stored in the user's Clerk privateMetadata (no DB change needed).
export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const apiKey = typeof body?.apiKey === "string" ? body.apiKey.trim() : "";
  if (!apiKey) {
    return NextResponse.json({ error: "API key required" }, { status: 400 });
  }

  // Verify the key + resolve the agent.
  let agent: { id: string; name?: string };
  try {
    const res = await fetch(`${API}/agents/me`, {
      headers: { "x-api-key": apiKey },
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        { error: "That API key doesn't match any agent." },
        { status: 400 },
      );
    }
    agent = await res.json();
  } catch {
    return NextResponse.json(
      { error: "Couldn't reach the GARL API. Try again." },
      { status: 502 },
    );
  }

  if (!agent?.id) {
    return NextResponse.json({ error: "Unexpected agent response" }, { status: 502 });
  }

  const client = await clerkClient();
  const user = await client.users.getUser(userId);
  const existing = Array.isArray(user.privateMetadata?.claimedAgentIds)
    ? (user.privateMetadata.claimedAgentIds as string[])
    : [];

  if (!existing.includes(agent.id)) {
    await client.users.updateUserMetadata(userId, {
      privateMetadata: { claimedAgentIds: [...existing, agent.id] },
    });
  }

  return NextResponse.json({ agent: { id: agent.id, name: agent.name ?? null } });
}
