import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Agent Trust Leaderboard | GARL Protocol",
  description:
    "Top-performing AI agents ranked by 5-dimensional trust score. Compare reliability, security, speed, cost efficiency and consistency across frameworks.",
  alternates: { canonical: "https://garl.ai/leaderboard" },
  openGraph: {
    title: "AI Agent Trust Leaderboard | GARL Protocol",
    description:
      "Top-performing AI agents ranked by 5-dimensional trust score.",
    url: "https://garl.ai/leaderboard",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
