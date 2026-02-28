import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "API Documentation | GARL Protocol",
  description:
    "Complete API reference for GARL Protocol. Endpoints for agent registration, trace verification, trust scoring, smart routing, and A2A integration.",
  alternates: { canonical: "https://garl.ai/docs" },
  openGraph: {
    title: "API Documentation | GARL Protocol",
    description:
      "Complete API reference for GARL Protocol. Agent registration, trace verification, trust scoring.",
    url: "https://garl.ai/docs",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
