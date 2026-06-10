# Security Policy

GARL is a cryptographic provenance protocol, so we take security reports
seriously and aim to make responsible disclosure easy.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use either channel:

1. **GitHub Private Vulnerability Reporting** (preferred) —
   [report a vulnerability](https://github.com/Garl-Protocol/garl/security/advisories/new).
   This is private to the maintainers and requires no email setup.
2. **Email** — `security@garl.ai`.

Please include: a description, affected endpoint/file/version, reproduction
steps or a proof-of-concept, and the impact you believe it has. If you have a
suggested fix, even better.

### What to expect

| Stage | Target |
|---|---|
| Acknowledgement of your report | within 3 business days |
| Initial assessment + severity | within 7 business days |
| Fix or mitigation for High/Critical | as fast as practical; coordinated with you |
| Public disclosure | after a fix ships, crediting you unless you prefer otherwise |

We do not currently run a paid bug-bounty, but we credit reporters in the
release notes and the advisory.

## Scope

**In scope**

- The API at `https://api.garl.ai` and the site at `https://garl.ai`.
- This repository (`Garl-Protocol/garl`) and `Garl-Protocol/garl-receipt-action`.
- The published packages: `@garl-protocol/mcp-server`, `@garl-protocol/sdk`
  (npm), `garl-protocol` (PyPI).
- The on-chain `MerkleAnchor` contract on Base mainnet
  (`0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`).

**Out of scope**

- Findings that require a compromised operator machine or stolen operator
  credentials.
- Volumetric DDoS, rate-limit exhaustion without a concrete impact, and
  best-practice nits without a demonstrable exploit.
- Reports that the trust score reflects agent-self-reported telemetry — this is
  a known, documented property of the protocol, not a vulnerability. GARL signs
  and makes tamper-evident *what an agent reported*; it does not claim to
  independently witness every reported field. See `docs/security.md`.

## Cryptographic key compromise

Receipts are signed with an ECDSA-secp256k1 key whose public half is published
in the key registry at
[`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json).
If you believe the signing key is compromised, report it via the channels above
and **do not** rely on receipts issued after the suspected compromise until a
rotation is published.

Key rotation is supported and documented (see the "Key Rotation Procedure" in
[`docs/security.md`](docs/security.md)): a new key is activated and the previous
public key is moved to the retired set, so receipts issued before the rotation
remain verifiable against their `key_id`.

## Supported versions

GARL is pre-1.0 and ships from `main`; only the latest published version of each
package and the currently deployed API are supported. Please verify a finding
against the latest version before reporting.
