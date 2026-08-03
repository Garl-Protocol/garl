# Changelog

All notable changes to the GARL Protocol are documented here. The protocol
follows the Action Receipt / Trust Vector spec versions; the running service
reports its version at `GET /health` (`version`) and `GET /api/v1/public-stats`
(`protocol_version`).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed
- **Repositioned to agent authority evidence** — homepage + README now lead
  with "Prove what your AI agent was authorized to do — and what it actually
  did": capability tokens (spend limits, merchant allowlists, attenuating
  delegation) and the Capability Gate are the hero; code receipts are one
  integration among several.

### Changed (Trust Vector honesty)
- **Self-reported traces can no longer lift a score above neutral (50).**
  Above-baseline headroom now scales with *attested* evidence — traces whose
  external attestation (e.g. GitHub CI check-run) was re-verified
  server-side, plus qualified endorsements: `effective_max = 50 + 50 ×
  min(evidence / max(5, 10% of traces), 1)`. Below-baseline movement is
  never capped. Existing evidence-less agents will show ≤50 — intended.
- Endorsement anti-farming: `/endorse` moved to the write rate tier
  (20/60s), max 5 endorsements per endorser per 24h, and identity assurance
  now counts only *qualified* endorsements (bonus > 0) — spam endorsements
  no longer move any dimension. `third_party_attestation_count` now equals
  attested traces + qualified endorsements (spec §4 fix). Every agent
  profile/trust-vector/scorecard exposes an `evidence` block
  (attested vs self-reported ratio). Migration v23.

### Added
- **Evidence Pack offline verifier** — `garl-verify --evidence-pack
  pack.json [--keys keys.json] [--rpc]` (garl-protocol ≥ 1.4.0 on PyPI)
  verifies the pack + receipt signatures, Merkle inclusion, the capability
  chain, and (with `--rpc`) the anchored root on Base — one command, no
  trust in GARL, network optional.
- **Keyed content hashing (EDPB 02/2025 ¶52)** — `input_hash`/`output_hash`
  can now be HMAC-SHA-256 under a per-agent off-chain key
  (`agent_hash_keys`, v22 migration): GARL-computed hashes (trace-mirror
  receipts, PII masking) are keyed by default; caller-supplied plain
  `sha256` requires an explicit `non_personal_payload: true` declaration;
  key management at `GET|DELETE /api/v1/agents/{id}/hash-key` (+ `/rotate`)
  — **key destruction is the sanctioned erasure mechanism**. New optional
  `hash_scheme` field in the Action Receipt envelope (spec §4.2 + JSON
  schema). Paragraph-by-paragraph mapping in `docs/compliance/edpb.md`.
- **Session-level behavioral layer v0** — rules-based anomaly detection over
  per-agent receipt streams (spend velocity vs capability limit, scope-
  escalation attempts, delegation-depth spikes, novel irreversible targets,
  receipt-rate bursts). Alerts are ECDSA-signed `garl/session-alert/v0.1`
  envelopes (same pipeline as receipts), immutable in `session_alerts` (v21
  migration), delivered via the existing per-agent webhooks (`anomaly`
  event), and public at `GET /api/v1/agents/{id}/alerts` + `GET
  /api/v1/alerts`; on-demand `POST /api/v1/agents/{id}/scan`; daily cron
  (`session-scan.yml`, fails loudly). Docs: `docs/session-alerts.md`.
- **`protocol/spec/capability-token-v0.1.md`** — full wire format for
  capability tokens (previously a TODO): claim semantics + scope grammar,
  normative attenuation rules, issuance/revocation semantics (cascade,
  fail-closed unknown-hash), 10-step verification algorithm with the offline
  `check_revocation` trade-off documented, receipt linkage via
  `capability_request.token_hash`, AP2/x402 mapping sketches (non-normative).
- **Living anchor chain** — `GET /api/v1/anchors` + public `/anchors` page list
  every Merkle batch (root, receipt count, Base tx, timestamp); built-but-
  unbroadcast batches are shown as visible gaps, never hidden. The weekly
  anchor workflow now **fails loudly** (job failure + auto-filed
  `anchor-failure` issue) instead of silently no-opping when secrets are
  missing; setup + recovery runbook at `docs/runbooks/anchoring.md`.
- **Offline end-to-end anchor verification test**
  (`backend/tests/test_e2e_offline_anchor.py`) — real production fixtures;
  verifies envelope ECDSA signatures against the published key registry,
  rebuilds the batch Merkle root, parses the raw signed Base transaction
  (inline keccak-256 + RLP, zero new dependencies), and checks
  `keccak256(raw_tx) == tx_hash` and that the `anchor()` calldata commits to
  the exact root and count — no network, no trust in GARL.
- **User accounts (Clerk)** — sign up at garl.ai, "My Agents" dashboard, claim/unclaim connected agents by API key. New `GET /api/v1/agents/me` resolves the agent for a key; ownership is held in Clerk user metadata.
- **/connect onboarding** — one-page integration menu: REST, Python, JS, MCP, GitHub Action (live); LangChain / CrewAI / OpenAI / Claude via SDK; OpenClaw / Hermes on the roadmap.
- Homepage repositioned to "signed receipts for everything your AI agents do" (broadened from code-only).

## [1.4.0]

Wave 2 + Wave 3 — agent-economy primitives on top of the receipt foundation.

### On-chain (2026-06-08)
- `MerkleAnchor.sol` deployed to **Base mainnet** at
  `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2` (chain 8453). Receipt-batch
  Merkle roots are anchored on-chain; inclusion is provable via `verifyProof`.
  Weekly batch-anchor workflow added (`.github/workflows/anchor.yml`).

### Security (2026-06-08)
- Wave 2 write endpoints (`/receipts`, `/capability/{issue,evaluate,revoke}`,
  `/receipts/{id}/undo`) now verify the caller owns the agent before signing —
  previously they only rate-limited, allowing forged receipts/tokens under any
  agent's DID.
- `verify_signature` only trusts keys in the GARL registry; capability
  revocation fails closed on unknown tokens; model disclosure is bound into the
  signed trace payload; webhook delivery re-validates target + disables
  redirects; CORS credentials off; CSV-export formula-injection guard.

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
- 29 MCP tools (was 21): added Trust Vector, Action Receipt, capability
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
