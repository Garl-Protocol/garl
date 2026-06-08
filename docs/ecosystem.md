# Ecosystem positioning

GARL Protocol is intentionally **next door** to the supply-chain attestation ecosystem, not a competitor to it. This document explains how GARL lines up with Sigstore, SLSA, in-toto, C2PA, W3C Verifiable Credentials, and ERC-8004 — and how to use GARL receipts inside those workflows.

## At a glance

| Neighbour | GARL's relationship |
|---|---|
| **Sigstore / Cosign** | Complementary. GARL issues its own ECDSA-secp256k1 signature against the canonical key registry. Verifiers who want a second anchor can re-wrap a GARL in-toto statement and sign with Cosign. |
| **SLSA v1.1** | First-class. `/agents/{id}/audit?format=slsa-v1.1` emits in-toto Statements with SLSA Provenance predicates, ready to feed into downstream SLSA tooling. |
| **in-toto attestations** | First-class. The new `garl/ai-authorship-v1` predicate (schema in [`integrations/in-toto-predicate/`](../integrations/in-toto-predicate/garl-ai-authorship-v1/)) is emitted via `?format=in-toto` as DSSE envelopes. |
| **GitHub Artifact Attestations** | Sibling. A future `attest-ai-authorship` GitHub Action can run beside `attest-build-provenance` — same repository, different subject (commit authorship vs. build artifact). |
| **OpenSSF Scorecard** | We plan to propose a `uses-ai-authorship-attestation` check. |
| **C2PA Content Credentials** | GARL is "C2PA for code" — similar mental model (generate-time signing), different medium. A `?format=c2pa` export is live on `GET /agents/{id}/audit`. |
| **W3C Verifiable Credentials 2.0** | GARL receipts can be wrapped into a VC when the downstream enterprise IAM stack expects that shape. Roadmap item. |
| **On-chain anchoring** | Live. Receipt-batch Merkle roots are anchored on Base mainnet (`MerkleAnchor` `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, chain 8453); inclusion is provable via `verifyProof`. Mirroring receipts into an ERC-8004 Reputation Registry entry remains a separate, optional integration. |

## What to reach for, when

| If you are… | Reach for… |
|---|---|
| A policy team asking "did an AI write this code?" | A GARL receipt URL (`garl.ai/r/{short_hash}`) with `signing_epoch: original`. |
| A supply-chain engineer running Sigstore / Cosign already | Export `?format=in-toto` or `?format=slsa-v1.1` and re-wrap with Cosign. |
| A compliance team preparing EU AI Act / CA SB 942 / ISO 42001 evidence | Export `?format=jsonld` (or `?format=csv` for auditors). Regulation-specific shapes — `ca-sb942`, `iso42001-annexb`, `in-toto`, `slsa-v1.1`, `c2pa` — are live on `GET /agents/{id}/audit`. |
| An agent-trust use case (delegation, reputation) | The classic agent reputation endpoints remain at `/api/v1/trust/*`, `/api/v1/agents/*`. |
| An on-chain agent ecosystem (ERC-8004) | Feed the GARL public key + receipt hash into your Reputation Registry entry. The cryptographic curve matches (secp256k1). |

## Predicate identifiers (canonical)

- `https://garl.ai/ai-authorship/v1` — the in-toto predicate type
- `https://garl.io/schema/v1` — the JSON-LD context used by stored certificates
- `https://slsa.dev/provenance/v1` — used when exporting as `?format=slsa-v1.1`

## Key-registry canonical URL

All verifiers should resolve `proof.key_id` or DSSE `signatures[].keyid` against:

```
https://api.garl.ai/.well-known/garl-keys.json
```

Mirrored at:

```
https://api.garl.ai/api/v1/keys
```

See [`docs/security.md`](security.md) for the key rotation procedure.
