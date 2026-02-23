import type { Metadata } from "next";
import "./globals.css";

const description =
  "Proof-of-Trust for the Agent Economy. Every agent execution indexed, scored, and publicly verified.";

export const metadata: Metadata = {
  title: "GARL Protocol - Global Agent Reputation Ledger",
  description,
  keywords: ["AI agents", "reputation", "trust score", "agent economy"],
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
          <footer className="border-t border-garl-border py-6">
            <div className="mx-auto max-w-7xl px-4 text-center font-mono text-xs text-garl-muted">
              GARL Protocol v1.0.2 — Viral Trust Network
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
