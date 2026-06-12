import { auth, clerkClient } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Remove an agent from the signed-in account (does not touch the agent itself,
// only the ownership link in Clerk metadata).
export async function POST(req: NextRequest) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const body = await req.json().catch(() => ({}));
  const agentId = typeof body?.agentId === "string" ? body.agentId : "";
  if (!agentId) {
    return NextResponse.json({ error: "agentId required" }, { status: 400 });
  }

  const client = await clerkClient();
  const user = await client.users.getUser(userId);
  const ids = Array.isArray(user.privateMetadata?.claimedAgentIds)
    ? (user.privateMetadata.claimedAgentIds as string[])
    : [];

  await client.users.updateUserMetadata(userId, {
    privateMetadata: { claimedAgentIds: ids.filter((id) => id !== agentId) },
  });

  return NextResponse.json({ ok: true });
}
