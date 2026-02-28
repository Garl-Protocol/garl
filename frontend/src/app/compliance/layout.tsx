import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Compliance Report | GARL Protocol",
  description:
    "CISO-ready compliance report for AI agents. Cryptographic verification, trust history, anomaly detection, and certification tier details.",
  alternates: { canonical: "https://garl.ai/compliance" },
  openGraph: {
    title: "Agent Compliance Report | GARL Protocol",
    description:
      "CISO-ready compliance report for AI agents with cryptographic verification.",
    url: "https://garl.ai/compliance",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
