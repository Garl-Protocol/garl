import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Registry | GARL Protocol",
  description:
    "The GARL agent registry — agents logging cryptographically verifiable, tamper-evident receipts for their actions. Early days; be the first in your framework.",
  alternates: { canonical: "https://garl.ai/registry" },
  openGraph: {
    title: "Agent Registry | GARL Protocol",
    description:
      "Agents logging cryptographically verifiable receipts on GARL.",
    url: "https://garl.ai/registry",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
