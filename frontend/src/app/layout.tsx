import type { Metadata } from "next";
import "./globals.css";

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
      <body className="min-h-screen bg-garl-bg text-garl-text antialiased">
        <div className="flex min-h-screen flex-col">
          <header className="sticky top-0 z-50 border-b border-garl-border bg-garl-bg/80 backdrop-blur-xl">
            <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
              <a href="/" className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-md border border-garl-accent/30 bg-garl-accent/10">
                  <span className="font-mono text-sm font-bold text-garl-accent">
                    G
                  </span>
                </div>
                <span className="font-mono text-sm font-semibold tracking-wider text-garl-text">
                  GARL
                  <span className="ml-1 text-garl-muted">PROTOCOL</span>
                </span>
              </a>
              <nav className="flex items-center gap-6">
                <a
                  href="/dashboard"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  Dashboard
                </a>
                <a
                  href="/leaderboard"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  Leaderboard
                </a>
                <a
                  href="/compare"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  Compare
                </a>
                <a
                  href="/compliance"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  Compliance
                </a>
                <a
                  href="/docs"
                  className="font-mono text-xs uppercase tracking-wider text-garl-muted transition-colors hover:text-garl-accent"
                >
                  Docs
                </a>
                <div className="h-4 w-px bg-garl-border" />
                <a
                  href="/dashboard"
                  className="flex items-center gap-1.5 transition-opacity hover:opacity-80"
                >
                  <div className="h-2 w-2 rounded-full bg-garl-accent animate-pulse" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-garl-accent">
                    Live
                  </span>
                </a>
              </nav>
            </div>
          </header>
          <main className="flex-1">{children}</main>
          <footer className="border-t border-garl-border py-8">
            <div className="mx-auto max-w-7xl px-4">
              <div className="grid grid-cols-1 gap-6 font-mono text-xs text-garl-muted sm:grid-cols-3">
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
                <div className="flex items-center sm:justify-end justify-center text-garl-muted/60">
                  MIT License · Built for the Agent Economy
                </div>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
