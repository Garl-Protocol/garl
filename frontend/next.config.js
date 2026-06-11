/** @type {import('next').NextConfig} */

// Security headers applied to every response. CSP is deliberately
// strict: first-party-only script/style/connect; no frame ancestors.
// The OG image route is exempt because social platforms fetch it as
// an image — CSP doesn't apply to image bytes.
// 'unsafe-eval' is required ONLY by Next's dev-mode HMR (react-refresh); it is
// never emitted in production, so the prod CSP stays tight.
const isDev = process.env.NODE_ENV !== "production";

const COMMON_SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      // Next inline hydration needs 'unsafe-inline'; 'unsafe-eval' is dev-only
      // (HMR). Clerk loads clerk-js from its Frontend API host
      // (*.clerk.accounts.dev for the dev instance, clerk.garl.ai in prod) and
      // uses Cloudflare Turnstile for bot protection.
      `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""} https://*.clerk.accounts.dev https://clerk.garl.ai https://challenges.cloudflare.com`,
      "style-src 'self' 'unsafe-inline'",
      // Same-origin avatars/OG/badges + Clerk user avatars (img.clerk.com).
      "img-src 'self' data: https://api.garl.ai https://img.clerk.com",
      "font-src 'self' data:",
      // Browser API calls hit api.garl.ai; Clerk Frontend API + telemetry.
      "connect-src 'self' https://api.garl.ai https://*.clerk.accounts.dev https://clerk.garl.ai https://clerk-telemetry.com",
      // Clerk uses web workers (blob:).
      "worker-src 'self' blob:",
      // Clerk's Turnstile bot-check renders in a frame.
      "frame-src 'self' https://challenges.cloudflare.com https://*.clerk.accounts.dev https://clerk.garl.ai",
      "frame-ancestors 'self'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const nextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: true,
  async redirects() {
    return [
      { source: "/for_code", destination: "/for-code", permanent: true },
      { source: "/ai-code", destination: "/for-code", permanent: true },
      { source: "/code", destination: "/for-code", permanent: true },
      // The leaderboard is reframed as an honest, early-stage agent registry.
      { source: "/leaderboard", destination: "/registry", permanent: true },
    ];
  },
  // PostHog reverse proxy: events/assets route through our own origin so ad
  // blockers don't drop them and the strict same-origin CSP keeps covering
  // analytics (no CSP loosening needed). US cloud.
  async rewrites() {
    return [
      { source: "/ingest/static/:path*", destination: "https://us-assets.i.posthog.com/static/:path*" },
      { source: "/ingest/:path*", destination: "https://us.i.posthog.com/:path*" },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: COMMON_SECURITY_HEADERS,
      },
    ];
  },
};

module.exports = nextConfig;
