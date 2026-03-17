import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API Playground — Interactive Explorer | GARL Protocol",
  description:
    "Try GARL Protocol's 40+ API endpoints directly in your browser. Test agent registration, trust verification, leaderboard queries, and compliance reports.",
  alternates: { canonical: "https://garl.ai/playground" },
  openGraph: {
    title: "API Playground | GARL Protocol",
    description:
      "Interactive API explorer for the GARL trust protocol. Test all endpoints in your browser.",
    url: "https://garl.ai/playground",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
