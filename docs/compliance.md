# Compliance evidence — what GARL actually delivers

GARL's audit exports map directly to three pieces of regulation that are either live today or land in 2026. This page is what to cite when your legal team asks "what does GARL cover?"

## Triple compliance pitch

| Regulation | Status | Effective | GARL coverage |
|---|---|---|---|
| **California SB 942 — AI Transparency Act** | Live | 1 Jan 2026 | Full per-record evidence via `?format=ca-sb942` — AI system name, generation timestamp, content identifier, machine-detectable provenance pointer (receipt URL + signature). |
| **EU AI Act Code of Practice on AI-generated content** | Draft → final | Aug 2026 | `?format=jsonld` and `?format=in-toto` provide the machine-readable disclosure shape that the Code of Practice asks for. Note: the Act's Article 50 itself targets deepfake / public-interest text; Code of Practice guidance is where code-specific obligations are most likely to be articulated. |
| **ISO/IEC 42001:2023 Annex B** | Live (certification active) | — | `?format=iso42001-annexb` emits evidence records mapped to controls A.6.2, A.6.2.5, A.7.2, A.8.3 (AI system lifecycle, verification, data quality, information for interested parties). |
| **C2PA Content Credentials (adjacent)** | Industry standard | — | `?format=c2pa` emits C2PA-adjacent Content Credentials manifests for source code. Not a strict C2PA 2.x JUMBF manifest — vocabulary matches so familiar tooling can consume it. |

## Export formats — one endpoint, seven shapes

```
GET /api/v1/agents/{agent_id}/audit?days={1..365}&format={...}&limit={1..10000}
```

| `format=` | Media type | Shape | Best for |
|---|---|---|---|
| `csv` | `text/csv` | Reviewer-friendly flat table | Auditor spreadsheets |
| `jsonld` | `application/json` | `CertifiedExecutionTrace` envelopes | Generic machine-readable export |
| `in-toto` | `application/json` | DSSE envelopes with `https://garl.ai/ai-authorship/v1` predicate | Supply-chain / Sigstore / Rekor pipelines |
| `slsa-v1.1` | `application/json` | in-toto v1 Statements with SLSA v1.1 Provenance predicate | SLSA-aware build systems |
| `ca-sb942` | `application/json` | California SB 942 record shape | California AI Transparency Act evidence |
| `iso42001-annexb` | `application/json` | ISO 42001 Annex B control-mapped records | AI management system certification |
| `c2pa` | `application/json` | C2PA-adjacent Content Credentials manifests | Content-provenance tooling |

## What makes these records **evidence** rather than just records

Each export format carries:

- The **content hash** (SHA-256 of the canonical trace payload)
- The **ECDSA-secp256k1 signature** issued by the canonical registry at sign time
- The **`key_id`** — a 16-hex fingerprint resolving to the entry in [`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json)
- The **`signing_epoch`** — `"original"` or `"pre-v0.3-unsigned-legacy"`. Only `"original"` implies unbroken chain-of-custody from the moment of trace submission.

Any verifier can independently validate a record by:
1. Fetching the public key from the registry.
2. Reconstructing the canonical JSON of the underlying statement / certificate.
3. Running ECDSA verification against the signature.

GARL publishes the exact canonicalization rules in [`docs/security.md`](security.md).

## Limitations, stated up-front

- **Article 50 is not literally about code.** The Act's current Article 50 text targets deepfakes and public-interest text. The Code of Practice (final expected June 2026) is where code-specific transparency obligations are most likely to land. GARL's evidence shape is designed to align with the Code, not to assert that Article 50 itself regulates code.
- **C2PA export is adjacent, not strict.** A strict C2PA 2.x manifest requires JUMBF binary packaging. GARL's `?format=c2pa` matches the **vocabulary** of Content Credentials so tooling that understands C2PA semantics can consume it, but is not a wire-compatible JUMBF manifest.
- **Canonical registry is the anchor.** All signatures are produced by the canonical registry. Self-hosted deployments produce their own signatures against their own key registry. See [GOVERNANCE.md](../GOVERNANCE.md) and [`docs/self-host.md`](self-host.md).

## See also

- Ecosystem positioning — [`docs/ecosystem.md`](ecosystem.md)
- Security + key rotation — [`docs/security.md`](security.md)
- Predicate schema — [`integrations/in-toto-predicate/garl-ai-authorship-v1/`](../integrations/in-toto-predicate/garl-ai-authorship-v1/)
