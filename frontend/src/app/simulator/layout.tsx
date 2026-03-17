import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trust Score Simulator — What-If Analysis | GARL Protocol",
  description:
    "Interactive 5-dimensional trust score calculator. Adjust reliability, security, speed, cost efficiency and consistency to simulate agent certification tiers.",
  alternates: { canonical: "https://garl.ai/simulator" },
  openGraph: {
    title: "Trust Score Simulator | GARL Protocol",
    description:
      "Interactive 5D trust score simulator with what-if analysis for AI agents.",
    url: "https://garl.ai/simulator",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
