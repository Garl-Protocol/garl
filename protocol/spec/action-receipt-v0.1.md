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

A receipt is a signature over what the **agent reported**. Precisely, it
**proves**:

- that this exact content (the `input_hash`/`output_hash` and envelope fields
  the agent submitted) was received by the issuer and bound under its key;
- that it is **tamper-evident** from that moment on — the stored record is
  immutable and, via Merkle anchoring, carries a publicly verifiable timestamp;
- the declared identity, authority, action/outcome *shape*, side-effect class,
  time, and the prior step in a chain (when present).

A receipt **does not prove**, on its own:

- that the agent produced a *correct* answer;
- that the reported metrics (duration, cost, success, the pre-image behind a
  hash) are *truthful* — the issuer signs the agent's claims; it does not
  independently re-execute or witness them.

Both are established by **attestations layered on top** (`attestations[]`):
tests passed (CI), human review, or a third party that *observed* the action
(a GitHub check-run, a tool-server co-signature). Treat a bare receipt as a
tamper-evident, time-stamped *notarization of a report*; treat its attestations
as the independent corroboration.

> Observability tells you what an agent says happened. GARL makes that report
> signed, immutable, and anchored — so it cannot be altered after the fact.

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
| `input_hash` | hex(64) | Hash of the canonical JSON of the input payload — HMAC-SHA-256 under a per-agent key (default; see §4.2) or plain SHA-256 for declared-non-personal payloads. |
| `output_hash` | hex(64) | Hash of the canonical JSON of the output payload — same scheme rules as `input_hash`. |
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
| `attestations` | (string \| object)[] | Independent corroboration of the action — see §4.1. A bare string is a human-readable claim (`tests_passed`, `human_reviewed`); a structured object points at a re-verifiable external fact. |
| `redaction_policy` | object | `{public_fields: [...], redacted_fields: [...]}` — which fields are exposed in the public receipt URL vs. only available to the agent's owner with API key. |
| `hash_scheme` | object | `{input, output, input_key_id?, output_key_id?}` with values `hmac-sha256` \| `sha256` — how the content hashes were produced. See §4.2. |

### 4.1 Structured attestations (the corroboration layer)

A receipt is a signature over what the agent *reported* (§2). A structured
attestation upgrades it by pointing at a **public fact anyone can re-check**, so
it is no longer a self-report. The first defined type:

```json
{
  "type": "github-check-run",
  "repo": "owner/name",
  "commit_sha": "<7-64 hex>",
  "conclusion": "success | failure | neutral | cancelled | timed_out | action_required | pending | none",
  "url": "https://github.com/owner/name/commit/<sha>",
  "witnessed": true,                 // OPTIONAL — set by an issuer that re-verified
  "actual_conclusion": "success",    // OPTIONAL — present iff the issuer re-checked
  "witness_reason": "conclusion-mismatch"  // OPTIONAL — present on a failed witness
}
```

Trust model, by field:
- `repo` + `commit_sha` + `conclusion` are **independently re-verifiable**: any
  consumer can call the GitHub API and confirm the commit's real CI conclusion.
  The issuer does not have to be trusted.
- `witnessed` is set **only by an issuer that re-verified** the attestation
  against the source (GitHub) at receipt time. `witnessed: true` means the
  claimed `conclusion` matched the source; `false` (+ `witness_reason`) means it
  did not, or the commit did not exist. Absence means "not issuer-verified —
  re-check it yourself." Issuers MUST fail open (omit `witnessed`) rather than
  block issuance when the source is unavailable.

The GARL canonical issuer re-verifies when `ENABLE_GITHUB_ATTESTATION_CHECK` is
configured, excluding its own check-run so it reads the repo's real CI. The
GARL Receipt GitHub Action populates this attestation from the commit's actual
check-runs (not a hardcoded status).

### 4.2 Keyed content hashing (`hash_scheme`)

EDPB Guidelines 02/2025 (adopted 7 July 2026) ¶52 holds that an **unsalted
hash of personal data is itself personal data** — the hashing party can
re-link it by re-hashing candidate inputs. ¶54 endorses putting "a pointer, a
cryptographic commitment or a hash generated from a keyed hash function"
on-chain, with verification data held off-chain.

GARL's rules:

- **`hmac-sha256` (default).** `input_hash`/`output_hash` = HMAC-SHA-256 of
  `canonical_bytes(payload)` under a **per-agent key** held off-chain by the
  issuer (`agent_hash_keys`). The key never appears in the envelope; the
  `*_key_id` fields name which key generation was used. Destroying the key
  (`DELETE /api/v1/agents/{id}/hash-key`) irreversibly severs the
  hash↔content link — the ¶52-sanctioned erasure mechanism. The hash remains
  in the immutable ledger and in Merkle batches as an opaque commitment.
- **`sha256` (declared non-personal only).** Plain SHA-256 is accepted only
  when the submitter also sends `non_personal_payload: true`. The issuer MUST
  reject `sha256` without that declaration.
- **Absent `hash_scheme`** means *unspecified* (receipts issued before this
  field existed). Verifiers MUST NOT interpret absence as plain SHA-256.

The keyed hash has the same 64-lowercase-hex shape as plain SHA-256, so
Merkle leaves, inclusion proofs, and every downstream surface are unchanged.
Content verification (`recomputed hash == envelope hash`) requires the key
holder's cooperation for keyed hashes — that is the point: verification is a
capability the data subject's processor can revoke, not an ambient property
of the public record. Full mapping: `docs/compliance/edpb.md`.

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
