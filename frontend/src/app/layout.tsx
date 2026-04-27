import type { Metadata } from "next";
import "./globals.css";
import SiteNav from "@/components/SiteNav";

const description =
  "Cryptographic verification for AI agent actions, starting with code. Every AI-authored action — commits, tool calls, payments, browser actions — signed with ECDSA-secp256k1 (RFC 6979 deterministic), receipted in an immutable ledger, gated by capability tokens, undoable when reversible (UETA §10(b)).";

export const metadata: Metadata = {
  title: "GARL Protocol — Cryptographic verification for AI code",
  description,
  keywords: [
    "AI code provenance",
    "AI commit signing",
    "AI-generated code verification",
    "cryptographic receipt",
    "ECDSA secp256k1",
    "ai authorship attestation",
    "GitHub Action AI receipt",
    "AI code audit trail",
    "EU AI Act compliance",
    "CA SB 942 AI transparency",
    "ISO 42001 audit evidence",
    "supply chain provenance",
    "SLSA predicate",
    "in-toto attestation",
    "agent reputation",
    "MCP server",
  ],
  metadataBase: new URL("https://garl.ai"),
  alternates: { canonical: "/" },
  openGraph: {
    title: "GARL Protocol — Cryptographic verification for AI code",
    description,
    url: "https://garl.ai",
    siteName: "GARL Protocol",
    type: "website",
    locale: "en_US",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "GARL Protocol — signed receipts for AI-authored commits" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "GARL Protocol — Cryptographic verification for AI code",
    description,
    images: ["/og-image.png"],
  },
  icons: {
    icon: "/favicon.svg",
    apple: "/apple-touch-icon.png",
  },
  manifest: "/manifest.json",
  other: { "theme-color": "#00FF88" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify([
              {
                "@context": "https://schema.org",
                "@type": "WebSite",
                name: "GARL Protocol",
                url: "https://garl.ai",
                potentialAction: {
                  "@type": "SearchAction",
                  target: "https://garl.ai/leaderboard?q={search_term_string}",
                  "query-input": "required name=search_term_string",
                },
              },
              {
                "@context": "https://schema.org",
                "@type": "Organization",
                name: "GARL Protocol",
                url: "https://garl.ai",
                logo: "https://garl.ai/og-image.png",
                sameAs: [
                  "https://github.com/Garl-Protocol/garl",
                  "https://github.com/marketplace/actions/garl-receipt",
                ],
              },
              {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                name: "GARL Protocol",
                applicationCategory: "DeveloperApplication",
                applicationSubCategory: "AI Code Provenance",
                operatingSystem: "Any",
                url: "https://garl.ai",
                description:
                  "Cryptographic verification for AI-authored code. Every commit from Claude Code, Cursor, Copilot, Aider, and Codex gets an ECDSA-secp256k1 signed receipt anchored on an immutable ledger — provenance evidence for EU AI Act, California SB 942, and ISO 42001 Annex B audits.",
                offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
                author: {
                  "@type": "Organization",
                  name: "GARL Protocol",
                  url: "https://garl.ai",
                },
                featureList: "Signed AI-action receipts (Action Receipt v0.1 envelope: code_write/api_call/payment/browser_action/file_op/tool_call), GitHub Action for Claude Code/Cursor/Copilot/Aider/Codex, ECDSA-secp256k1 ledger (RFC 6979 deterministic), Trust Vector v0.1 multi-dimensional reputation, capability tokens (JWT-shaped + Biscuit-style attenuation), Capability Gate pre-flight, UETA §10(b) consumer-undo, compliance export (CSV/JSON-LD/SLSA/in-toto/C2PA), 28 named MCP tools, Python & JavaScript SDKs, public verify endpoint",
                softwareRequirements: "GitHub repository, REST API client, MCP client, or A2A-compatible agent",
                releaseNotes: "https://github.com/Garl-Protocol/garl/releases",
                license: "https://opensource.org/licenses/Apache-2.0",
              },
            ]),
          }}
        />
      </head>
      <body className="min-h-screen bg-garl-bg text-garl-text antialiased">
        <div className="flex min-h-screen flex-col">
          <SiteNav />
          <main className="flex-1">{children}</main>
          <footer className="border-t border-garl-border py-8">
            <div className="mx-auto max-w-7xl px-4">
              <div className="grid grid-cols-1 gap-6 font-mono text-xs text-garl-muted sm:grid-cols-4">
                <div className="flex items-center gap-2 sm:justify-start justify-center">
                  <div className="flex h-6 w-6 items-center justify-center rounded border border-garl-accent/30 bg-garl-accent/10">
                    <span className="text-[10px] font-bold text-garl-accent">G</span>
                  </div>
                  <span className="font-semibold text-garl-text">GARL Protocol</span>
                </div>
                <div className="flex items-center justify-center gap-4">
                  <a
                    href="https://github.com/Garl-Protocol/garl"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="transition-colors hover:text-garl-accent"
                  >
                    GitHub
                  </a>
                  <span className="text-garl-border">·</span>
                  <a
                    href="https://api.garl.ai/.well-known/agent-card.json"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="transition-colors hover:text-garl-accent"
                  >
                    A2A Agent Card
                  </a>
                  <span className="text-garl-border">·</span>
                  <a
                    href="/docs"
                    className="transition-colors hover:text-garl-accent"
                  >
                    API Docs
                  </a>
                </div>
                <div className="flex items-center justify-center">
                  <a
                    href="mailto:contact@garl.ai"
                    className="transition-colors hover:text-garl-accent"
                  >
                    contact@garl.ai
                  </a>
                </div>
                <div className="flex items-center sm:justify-end justify-center text-garl-muted/60">
                  Apache 2.0 · Provenance for AI-authored code
                </div>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
