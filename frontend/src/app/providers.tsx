"use client";

import posthog from "posthog-js";
import { PostHogProvider as PHProvider } from "posthog-js/react";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";

// Public, build-time-inlined. Empty → analytics is a no-op (safe to ship).
const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;

if (typeof window !== "undefined" && KEY) {
  posthog.init(KEY, {
    // Reverse-proxied through /ingest (see next.config.js) so ad blockers
    // don't drop events and the strict same-origin CSP keeps covering it.
    api_host: "/ingest",
    ui_host: "https://us.posthog.com",
    capture_pageview: false, // captured manually on route change (App Router)
    capture_pageleave: true,
    autocapture: true, // clicks on links/buttons (GitHub, Verify, etc.)
    person_profiles: "identified_only", // privacy: no anon person profiles
    respect_dnt: true,
  });
}

function PageviewTracker() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useEffect(() => {
    if (!KEY || typeof window === "undefined") return;
    let url = window.location.origin + pathname;
    const qs = searchParams?.toString();
    if (qs) url += `?${qs}`;
    posthog.capture("$pageview", { $current_url: url });
  }, [pathname, searchParams]);
  return null;
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  if (!KEY) return <>{children}</>;
  return (
    <PHProvider client={posthog}>
      <Suspense fallback={null}>
        <PageviewTracker />
      </Suspense>
      {children}
    </PHProvider>
  );
}
