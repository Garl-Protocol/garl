import { currentUser } from "@clerk/nextjs/server";
import { SignInButton, UserButton } from "@clerk/nextjs";
import { ArrowRight } from "lucide-react";
import MyAgentsDashboard from "./MyAgentsDashboard";

// Must render per-request: it reads the Clerk session (currentUser) and a
// runtime-only secret (CLERK_SECRET_KEY isn't a build-time value on Railway),
// so it must never be statically prerendered with a stale build-time gate.
export const dynamic = "force-dynamic";

// Gated: only touch Clerk when configured. Without keys this renders a neutral
// placeholder and never calls Clerk, so the route is safe on a keyless deploy.
const clerkConfigured =
  !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
  !!process.env.CLERK_SECRET_KEY;

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-2xl px-4 py-20">
      <div className="rounded-xl border border-garl-border bg-garl-surface p-8">
        {children}
      </div>
    </div>
  );
}

export default async function AccountPage() {
  if (!clerkConfigured) {
    return (
      <Shell>
        <h1 className="mb-2 font-mono text-xl font-bold text-garl-text">
          Accounts
        </h1>
        <p className="text-sm leading-relaxed text-garl-muted">
          Sign-in isn&apos;t enabled on this deployment yet. Every agent you
          connect already has a public profile and verifiable receipts — see{" "}
          <a href="/connect" className="text-garl-accent hover:underline">
            Add your agent
          </a>
          .
        </p>
      </Shell>
    );
  }

  const user = await currentUser();

  if (!user) {
    return (
      <Shell>
        <h1 className="mb-2 font-mono text-xl font-bold text-garl-text">
          Your agents, in one place
        </h1>
        <p className="mb-5 text-sm leading-relaxed text-garl-muted">
          Sign in to link the agents you&apos;ve connected to GARL and track
          their activity, anomalies, and cost from one account.
        </p>
        <SignInButton mode="modal">
          <button className="inline-flex items-center gap-2 rounded-lg bg-garl-accent px-5 py-2.5 font-mono text-sm font-semibold text-garl-bg transition-all hover:glow-green-strong">
            Sign in <ArrowRight className="h-4 w-4" />
          </button>
        </SignInButton>
      </Shell>
    );
  }

  const email =
    user.primaryEmailAddress?.emailAddress ?? user.username ?? "your account";

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-garl-text">
            My Agents
          </h1>
          <p className="mt-1 font-mono text-xs text-garl-muted">{email}</p>
        </div>
        <UserButton afterSignOutUrl="/" />
      </div>
      <MyAgentsDashboard />
    </div>
  );
}
