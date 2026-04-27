# GARL Action Receipt — v0.1

**Status:** Draft (v0.1 = breaking-change allowed; v1.0 freezes wire format)
**Date:** 2026-04-27
**Editors:** GARL Protocol maintainers

## 1. Summary

A GARL Action Receipt is a signed, content-addressable record that an
**agent** performed a specific **action** on a specific **target**, with a
specific **outcome**, at a specific **time**, under a specific **authority**.

The current canonical issuer is `https://api.garl.ai`. Self-hosted issuers
publish the same shape; verifiers distinguish by `issuer` and the matching
public key in `/.well-known/garl-keys.json`.

## 2. What this is, and is not

A receipt **proves**: identity, authority, action shape, outcome shape,
side-effect class, time, and (when present) the prior step in a chain.

A receipt **does not prove**: that the agent produced a *correct* answer.
Receipts are evidence; correctness is judged by attestations layered on top
(`attestations[]`) — tests passed, human review, third-party verifiers.

> Observability tells you what happened. GARL proves what happened.

## 3. Required envelope

Every receipt MUST contain:

| Field | Type | Notes |
|---|---|---|
| `receipt_id` | UUID v4 | Issuer-assigned. Unique. |
| `version` | const `"garl/action-receipt/v0.1"` | Wire shape. Bumped on breaking change. |
| `issuer` | URI | Canonical: `https://api.garl.ai`. Self-hosted issuers use their own origin. |
| `agent_identity` | DID | `did:garl:<uuid>` for now; other DID methods reserved. |
| `human_delegate` | string \| null | `null` = no human in the chain. Otherwise stable opaque ID. |
| `runtime` | enum | `claude-code`, `cursor`, `copilot`, `aider`, `codex`, `mcp-client`, `langchain`, `crewai`, `llamaindex`, `semantic-kernel`, `custom`. |
| `protocol` | enum | `github`, `mcp`, `a2a`, `acp`, `ap2`, `x402`, `raw-http`. |
| `action_type` | enum | `code_write`, `api_call`, `payment`, `browser_action`, `file_op`, `tool_call`. |
| `tool_server` | URI \| null | The endpoint the action targeted, if applicable. |
| `input_hash` | hex(64) | SHA-256 of the canonical JSON of the input payload. |
| `output_hash` | hex(64) | SHA-256 of the canonical JSON of the output payload. |
| `side_effect` | enum | `none`, `reversible`, `irreversible`. |
| `timestamp` | RFC 3339 | UTC. Issuer's clock at signing time. |
| `signature` | hex | RFC 6979 deterministic ECDSA-secp256k1 over the canonical receipt minus the `signature` and `verification_key_id` fields. |
| `verification_key_id` | string | First 16 hex of SHA-256 of the public key. Looked up in `/.well-known/garl-keys.json`. |

## 4. Optional fields

| Field | Type | Notes |
|---|---|---|
| `capability_request` | object | The capability token (or its hash + metadata) under whose authority this action ran. See §6. |
| `policy_decision` | enum | `allowed`, `denied`, `requires_human`. Set when the issuer evaluated a policy at action time. |
| `cost` | object | `{usd: number, tokens_in: int, tokens_out: int, duration_ms: int}` — partial OK; consumers tolerate missing keys. |
| `previous_receipt_hash` | hex(64) \| null | The `output_hash` of the receipt this action followed. Builds a chain; sets up Merkle batching. |
| `attestations` | string[] | Human-readable claims that have been independently verified, e.g. `tests_passed`, `human_reviewed`, `static_analysis_clean`, `coverage_threshold_met`. |
| `redaction_policy` | object | `{public_fields: [...], redacted_fields: [...]}` — which fields are exposed in the public receipt URL vs. only available to the agent's owner with API key. |

## 5. Side-effect classification

The `side_effect` field is the load-bearing primitive that makes receipts
useful for **reversibility** (e.g., UETA §10(b) consumer-undo claims) and
for **policy gating** (don't let an untrusted agent perform irreversible
actions).

- `none` — Read-only. No state changes, no money moves, no messages sent.
  Examples: `garl_get_trust_vector`, `garl_verify`, web search, file read.
- `reversible` — Mutates state, but a single follow-up action cancels it.
  Examples: Calendly event cancel, Notion page restore, Stripe-test refund,
  GitHub issue comment delete, draft email save.
- `irreversible` — No automatic undo. Examples: Stripe live payment,
  customer-facing email sent, branch force-pushed, file deleted from
  immutable store.

Issuers MUST classify conservatively: when in doubt, `irreversible`.
Capability-token policies MAY refuse `irreversible` for agents below a
configured Trust Vector threshold.

## 6. Capability request linkage

When an action ran under a GARL-issued capability token, the receipt
records:

```json
"capability_request": {
  "token_hash": "<sha256 of the issued token>",
  "scope": "...",
  "issued_at": "2026-04-27T10:00:00Z",
  "expires_at": "2026-04-27T11:00:00Z",
  "spend_limit_usd": 50.0,
  "merchant_allowlist": ["stripe.com", "calendly.com"],
  "side_effect_class": "reversible"
}
```

Verifiers SHOULD reject receipts whose `side_effect` is more dangerous than
the token's `side_effect_class` (e.g. token says `reversible` but receipt
records `irreversible`).

## 7. Canonical JSON for hashing and signing

To compute `input_hash`, `output_hash`, and the receipt signature, the
canonical JSON form is:

1. Sort all object keys lexicographically at every depth.
2. No whitespace between tokens (RFC 7159 minimal form).
3. Numbers in shortest round-trippable form.
4. UTF-8 byte sequence.

The signature is computed over the canonical form of the receipt with
`signature` and `verification_key_id` **removed**, then those two fields
are appended.

This matches the existing GARL trace signing routine
(`backend/app/core/signing.py`), so existing receipts are forward-compatible
once their fields are mapped into the v0.1 envelope.

## 8. Verification flow

1. Fetch `verification_key_id` → look up the public key in
   `https://api.garl.ai/.well-known/garl-keys.json` (or the self-hosted
   issuer's equivalent).
2. Re-canonicalize the receipt with `signature` and `verification_key_id`
   removed.
3. Recompute SHA-256 of the canonical bytes.
4. Verify the ECDSA-secp256k1 signature against the public key.
5. If `previous_receipt_hash` is non-null, optionally fetch and verify the
   prior receipt; chain integrity is the consumer's responsibility.

The `garl-verify` CLI implements this offline (no network call to GARL)
once the key registry has been cached.

## 9. Example

```json
{
  "receipt_id": "5e8a7b3c-8e2f-4f1d-9a6b-1c2d3e4f5a6b",
  "version": "garl/action-receipt/v0.1",
  "issuer": "https://api.garl.ai",
  "agent_identity": "did:garl:3216b8ed-fa2c-452a-bda2-925cde273314",
  "human_delegate": "github:ardakutsal",
  "runtime": "claude-code",
  "protocol": "mcp",
  "action_type": "tool_call",
  "tool_server": "https://api.example.com/v1/calendly",
  "capability_request": {
    "token_hash": "8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b",
    "scope": "calendly:reschedule:self",
    "expires_at": "2026-04-27T11:00:00Z",
    "side_effect_class": "reversible"
  },
  "policy_decision": "allowed",
  "input_hash":  "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
  "output_hash": "9f8e7d6c5b4a3210ffeeddccbbaa99887766554433221100ffeeddccbbaa9988",
  "side_effect": "reversible",
  "cost": {"usd": 0.0008, "tokens_in": 1240, "tokens_out": 87, "duration_ms": 642},
  "timestamp": "2026-04-27T10:30:42Z",
  "previous_receipt_hash": "deadbeefcafebabe0123456789abcdef0123456789abcdef0123456789abcdef",
  "attestations": ["human_reviewed"],
  "redaction_policy": {"public_fields": ["agent_identity","action_type","side_effect","timestamp"]},
  "signature": "<hex ECDSA-secp256k1 signature>",
  "verification_key_id": "8c6e8f25ef3bf704"
}
```

## 10. Migration from legacy `traces` shape

The existing GARL `traces` record (commit-flavored) maps cleanly onto v0.1:

| Legacy field | v0.1 field |
|---|---|
| `trace_hash` | becomes `output_hash` |
| `trust_delta` | not represented (Trust Vector dimension instead) |
| `task_description` | hashed into `input_hash` (the public receipt page may surface a redacted summary) |
| `signing_epoch` | retired; key rotation is captured by `verification_key_id` |
| `proof.signature` | becomes `signature` |
| `proof.verification.public_key_hex` | replaced by `verification_key_id` lookup |

Legacy traces remain valid under their original shape. New surfaces emit
v0.1; consumers MAY accept either, SHOULD prefer v0.1.

## 11. Open questions for v1.0

- Do we standardize a `redaction_policy` predicate language, or leave it
  free-form per issuer?
- Does `attestations` become a structured `{type, issuer, evidence_uri}`
  list rather than free strings?
- Is `previous_receipt_hash` enough, or do we want a `Merkle inclusion
  proof` field for batched on-chain anchoring?
- How does `capability_request` interop with x402 `extra` field, ACP
  `metadata`, and AP2 `agent_attestations`?

These get answered once two receipt issuers and three verifiers ship in
production. v0.1 is deliberately under-specified in those corners to leave
room for empirical convergence.

## 12. License

This specification is published under Apache 2.0 (see `LICENSE` at the
repository root). Reference implementation lives in
`backend/app/core/signing.py` and `backend/app/services/`.
