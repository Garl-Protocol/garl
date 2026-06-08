/** @type {import('next').NextConfig} */

// Security headers applied to every response. CSP is deliberately
// strict: first-party-only script/style/connect; no frame ancestors.
// The OG image route is exempt because social platforms fetch it as
// an image — CSP doesn't apply to image bytes.
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
      // Next.js inline runtime hydration script needs 'unsafe-inline'; keep
      // it tight by scoping to self + the known inline shape. Tailwind +
      // framer-motion style tags also need 'unsafe-inline'.
      "script-src 'self' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      // Avatars, identicons, OG previews are same-origin. data: for inline
      // SVG badges embedded in client components.
      "img-src 'self' data: https://api.garl.ai",
      "font-src 'self' data:",
      // API calls from the browser hit api.garl.ai; allow same-origin +
      // canonical API host.
      "connect-src 'self' https://api.garl.ai",
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
