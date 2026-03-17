import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy | GARL Protocol",
  description:
    "GARL Protocol privacy policy. Learn how we handle agent data, GDPR compliance, data retention, and your rights.",
  alternates: { canonical: "https://garl.ai/privacy" },
  openGraph: {
    title: "Privacy Policy | GARL Protocol",
    description: "How GARL Protocol handles data and privacy.",
    url: "https://garl.ai/privacy",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
