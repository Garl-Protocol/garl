import { auth, clerkClient } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

// List the agents claimed by the signed-in account, with their public profile
// data fetched fresh from the GARL API.
export async function GET() {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const client = await clerkClient();
  const user = await client.users.getUser(userId);
  const ids = Array.isArray(user.privateMetadata?.claimedAgentIds)
    ? (user.privateMetadata.claimedAgentIds as string[])
    : [];

  const agents = await Promise.all(
    ids.map(async (id) => {
      try {
        const r = await fetch(`${API}/agents/${id}`, { cache: "no-store" });
        if (!r.ok) return null;
        return await r.json();
      } catch {
        return null;
      }
    }),
  );

  return NextResponse.json({ agents: agents.filter(Boolean) });
}
