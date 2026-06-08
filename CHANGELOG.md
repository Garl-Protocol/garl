# Changelog

All notable changes to the GARL Protocol are documented here. The protocol
follows the Action Receipt / Trust Vector spec versions; the running service
reports its version at `GET /health` (`version`) and `GET /api/v1/public-stats`
(`protocol_version`).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.4.0]

Wave 2 + Wave 3 — agent-economy primitives on top of the receipt foundation.

### Added
- **Action Receipt v0.1** generic envelope: `POST /api/v1/receipts`,
  immutable `GET /api/v1/receipts/{id}/cert.json`, and UETA §10(b) undo at
  `POST /api/v1/receipts/{id}/undo`.
- **Capability tokens** (JWT-shaped, ECDSA-secp256k1, Biscuit-style
  attenuation via `parent_token_hash`): `POST /api/v1/capability/{issue,
  verify,revoke,evaluate}`.
- **Capability Gate** — pre-flight Trust Vector × side-effect → token-or-deny.
- **Reversibility** state machine: recorded → pending → succeeded | failed.
- **Merkle batch anchoring** to Base L2 (`MerkleAnchor.sol`, Foundry project,
  Apache-2.0) with off-chain batch builder and on-chain inclusion proofs.
- **Trust Vector v0.1** multi-dimensional projection: `GET /api/v1/agents/
  {id}/trust-vector`.
- Per-agent monthly receipt cap (10K/month default) as a silent abuse guard.
- Public usage stats at `GET /api/v1/public-stats` and `https://garl.ai/stats`.
- 28 MCP tools (was 21): added Trust Vector, Action Receipt, capability
  issue/verify/revoke, evaluate, and undo tools.

### Changed
- License standardized to Apache-2.0 across repo, SDKs, and packages.
- Supabase schema migrations v17 (Trust Vector), v18 (Wave 2 tables), v19
  (advisor fixes: `search_path` pin + covering indexes).

### Removed
- OpenClaw integration (EOL): adapter classes, ingest endpoint, seed agents.

## [1.1.0]

- Legacy commit-flavored trace verification (`POST /api/v1/verify`,
  `GET /api/v1/verify/{hash}`), 5-dimensional EMA reputation, A2A v1.0 and
  ERC-8004 format compatibility, GARL PR Bot (GitHub App, HMAC, rate limit).

## [1.0.2]

- Initial public protocol surface and SDK publishes.
