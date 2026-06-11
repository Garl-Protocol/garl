import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

// Gated, exactly like the PostHog provider's "no-op if unset" pattern.
// Clerk only engages when BOTH keys are present (set in Railway). Before the
// keys exist, this is a pure passthrough so the public site is 100% unaffected
// — no forced sign-in, no broken requests, no behavior change at all.
//
// clerkMiddleware() establishes auth context but does NOT protect any route by
// default (route protection is opt-in via auth.protect()), so even when engaged
// every page stays public — consistent with GARL's public-by-default model.
const clerkConfigured =
  !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
  !!process.env.CLERK_SECRET_KEY;

export default clerkConfigured
  ? clerkMiddleware()
  : function passthrough() {
      return NextResponse.next();
    };

export const config = {
  matcher: [
    // Skip Next internals, the /ingest PostHog proxy, and static files;
    // run on everything else + API routes.
    "/((?!_next|ingest|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
