import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Compliance evidence export | GARL Protocol",
  description:
    "Signed-receipt evidence for EU AI Act (Code of Practice, Aug 2026), California SB 942 (active since 1 Jan 2026), and ISO/IEC 42001 Annex B. Export as CSV, JSON-LD, in-toto, SLSA v1.1, ca-sb942, iso42001-annexb, or c2pa.",
  alternates: { canonical: "https://garl.ai/compliance" },
  openGraph: {
    title: "Compliance evidence for AI-authored code | GARL Protocol",
    description:
      "EU AI Act + CA SB 942 + ISO 42001 Annex B evidence bundles, signed with ECDSA-secp256k1.",
    url: "https://garl.ai/compliance",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
