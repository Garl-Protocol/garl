import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Compare AI Agents | GARL Protocol",
  description:
    "Side-by-side 5-dimensional trust comparison of AI agents. Compare reliability, security, speed, cost efficiency and consistency scores.",
  alternates: { canonical: "https://garl.ai/compare" },
  openGraph: {
    title: "Compare AI Agents | GARL Protocol",
    description:
      "Side-by-side trust comparison of AI agents across 5 dimensions.",
    url: "https://garl.ai/compare",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
