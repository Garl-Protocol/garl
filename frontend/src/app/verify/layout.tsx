import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verify Trace — Cryptographic Proof Verification | GARL Protocol",
  description:
    "Don't trust, verify. Paste any SHA-256 trace hash to independently verify an AI agent's execution with ECDSA-secp256k1 cryptographic proof.",
  alternates: { canonical: "https://garl.ai/verify" },
  openGraph: {
    title: "Verify Trace — Cryptographic Proof Verification | GARL Protocol",
    description:
      "Independently verify any AI agent's execution trace with cryptographic proof.",
    url: "https://garl.ai/verify",
  },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
