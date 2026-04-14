import type { Metadata } from "next";
import "./globals.css";
import SiteNav from "@/components/SiteNav";

const description =
  "The first A2A v1.0 RC compatible trust oracle. Proof-of-Trust for the Agent Economy. Every agent execution indexed, scored, and publicly verified.";

export const metadata: Metadata = {
  title: "GARL Protocol - Global Agent Reputation Ledger",
  description,
  keywords: [
    "AI agents",
    "reputation",
    "trust score",
    "agent economy",
    "A2A protocol",
    "agent-to-agent",
    "agent trust API",
    "A2A compatible",
    "agent reputation ledger",
    "MCP server",
    "agent verification",
    "ERC-8004",
    "blockchain-ready agent trust",
    "multi-agent trust",
    "agent delegation",
    "AI agent reputation",
  ],
  metadataBase: new URL("https://garl.ai"),
  alternates: { canonical: "/" },
  openGraph: {
    title: "GARL Protocol — The Universal Trust Standard for AI Agents",
    description,
    url: "https://garl.ai",
    siteName: "GARL Protocol",
    type: "website",
    locale: "en_US",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "GARL Protocol" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "GARL Protocol — The Universal Trust Standard for AI Agents",
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
                alternateName: "Global Agent Reputation Ledger",
                url: "https://garl.ai",
                logo: "https://garl.ai/og-image.png",
                sameAs: [
                  "https://github.com/Garl-Protocol/garl",
                ],
              },
              {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                name: "GARL Protocol",
                alternateName: "Global Agent Reputation Ledger",
                applicationCategory: "DeveloperApplication",
                applicationSubCategory: "AI Agent Trust Verification",
                operatingSystem: "Any",
                url: "https://garl.ai",
                description:
                  "The first A2A v1.0 RC compatible trust oracle. Universal trust standard for AI agents with 5-dimensional scoring, ECDSA-secp256k1 signatures, agent identity system, and ERC-8004 format compatibility.",
                offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
                author: {
                  "@type": "Organization",
                  name: "GARL Protocol",
                  url: "https://garl.ai",
                },
                featureList: "5D trust scoring, ECDSA-secp256k1 signatures, agent identity system, MCP Server (20 tools), A2A v1.0 RC, ERC-8004 format compatible, Python SDK, JavaScript SDK, Smart agent routing, GitHub Action trust gate",
                softwareRequirements: "REST API, MCP client, or A2A-compatible agent",
                releaseNotes: "https://github.com/Garl-Protocol/garl",
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
                  Apache 2.0 · Built for the Agent Economy
                </div>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
