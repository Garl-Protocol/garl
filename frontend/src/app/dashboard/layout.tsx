import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agent Dashboard | GARL Protocol",
  description:
    "Manage and monitor your AI agent's trust profile, execution traces, and reputation history on GARL Protocol.",
  alternates: { canonical: "https://garl.ai/dashboard" },
  openGraph: {
    title: "Agent Dashboard | GARL Protocol",
    description:
      "Manage and monitor your AI agent's trust profile on GARL Protocol.",
    url: "https://garl.ai/dashboard",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
