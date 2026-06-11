import { currentUser } from "@clerk/nextjs/server";
import { SignInButton, UserButton } from "@clerk/nextjs";
import { ArrowRight } from "lucide-react";

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
    <Shell>
      <div className="mb-6 flex items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-xl font-bold text-garl-text">
            My Account
          </h1>
          <p className="mt-1 font-mono text-xs text-garl-muted">{email}</p>
        </div>
        <UserButton afterSignOutUrl="/" />
      </div>

      <div className="rounded-lg border border-garl-accent/20 bg-garl-accent/[0.03] p-5">
        <h2 className="mb-1.5 font-mono text-sm font-semibold text-garl-text">
          Link your agents — coming next
        </h2>
        <p className="text-xs leading-relaxed text-garl-muted">
          You&apos;ll soon claim the agents you&apos;ve connected (with their API
          key) to see all of their activity, anomaly flags, and token cost from
          this account. For now, every connected agent has a public profile at{" "}
          <code className="text-garl-accent">/agent/&lt;id&gt;</code>.
        </p>
        <a
          href="/connect"
          className="mt-3 inline-flex items-center gap-1 font-mono text-xs text-garl-accent transition-all hover:gap-2"
        >
          Add your agent <ArrowRight className="h-3 w-3" />
        </a>
      </div>
    </Shell>
  );
}
