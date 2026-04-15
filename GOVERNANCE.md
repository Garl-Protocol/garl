# GARL Protocol Governance

_Last updated: 2026-04-15_

GARL is an open protocol with a **canonical registry** operated at `https://api.garl.ai`. This document explains who makes decisions, how contributions are accepted, and what the word "canonical" means in this project.

## 1. Canonical registry vs self-host

GARL has always been designed so anyone can clone the repository and run their own copy. Receipts issued by any deployment using the `garl-protocol/*` software can carry a valid ECDSA-secp256k1 signature that verifies against that deployment's own public key.

**Self-hosting is explicitly supported and encouraged** for internal audit trails, regulated-industry deployments, and research. See [`docs/self-host.md`](docs/self-host.md).

The **canonical registry** is the single deployment at `https://api.garl.ai` whose public key is published at `https://api.garl.ai/.well-known/garl-keys.json`. The "GARL Verified" badge, the public leaderboard at `garl.ai/leaderboard`, and the `/for-code` pitch refer to the canonical registry only. Self-hosted deployments are legitimate participants but are not the canonical registry, and therefore should not describe themselves as such (see [TRADEMARK.md](TRADEMARK.md)).

Why does a "canonical" registry exist? Compliance evidence and cross-organization trust need a stable, addressable ledger. A federation of mutually-distrustful self-hosts doesn't provide that on its own. The canonical registry is the anchor; forks and self-hosts are peers.

## 2. Decisions

The project is currently maintained by a small team. Decisions fall into three buckets:

| Bucket | Who decides | How |
|---|---|---|
| **Routine code changes** (bug fixes, docs, refactors) | Maintainers | Pull request → review → merge |
| **Protocol additions** (new endpoints, receipt fields, scoring tweaks) | Maintainers, after public discussion | GitHub issue → comment period (≥ 7 days) → pull request |
| **Breaking changes or canonical registry policy** | Maintainers, after consultation | GitHub issue → comment period (≥ 14 days) → pull request → announcement on the canonical registry docs |

Maintainers will document every breaking change in the release notes and preserve backwards-compatible endpoints where feasible, including via `Deprecation:` and `Sunset:` HTTP headers.

## 3. Contributions

All contributions flow through pull requests. We use the **Developer Certificate of Origin** (DCO) — every commit must be signed off with `git commit -s`. Details in [CONTRIBUTING.md](CONTRIBUTING.md).

Contributors retain copyright; the DCO affirms that the contribution is yours to offer under the project's Apache 2.0 license.

## 4. Core vs. future Cloud-only features

The contents of this repository are, and will remain, **Apache 2.0 licensed**. That covers the signing layer, the scoring engine, the FastAPI backend, the Next.js frontend, the SDKs, the MCP server, and the GitHub Action.

Some future features that only make sense as hosted services (for example: multi-region high availability, optional on-chain attestations via ERC-8004, SOC 2 / ISO 27001 compliance packages, fleet-wide analytics) may be offered as **Cloud-only services** on the canonical registry without being added to this repository. The decision for each future feature will be documented when it is introduced.

The practical rule: **any feature that a self-hosted deployment needs to stay functional remains in this repository under Apache 2.0**. Value-added services layered on top may be Cloud-only.

## 5. Security issues

Please report vulnerabilities to `security@garl.ai` per the process in [SECURITY.md](SECURITY.md) / [`.well-known/security.txt`](https://garl.ai/.well-known/security.txt). Do not open public issues for unpatched vulnerabilities.

## 6. Amendments

This document may change. Substantive changes follow the "breaking changes" process above (14-day comment period).
