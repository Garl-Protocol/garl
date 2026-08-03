# GARL × EDPB Guidelines 02/2025 on Blockchain

**Reference:** EDPB Guidelines 02/2025 on the processing of personal data
through blockchain technologies, **version 2.0, adopted 7 July 2026** (after
public consultation). Paragraph numbers below follow that version.

**Scope of this document:** how GARL's architecture maps to ¶48–¶56 (the
storage-technique hierarchy), what GARL puts on-chain, and how erasure works.
This is an engineering-accuracy document, not legal advice.

## The one-line summary

GARL puts **nothing on-chain except Merkle roots** of receipt batches
(32-byte digests of digests). Personal-data payloads are hashed with a
**keyed hash function (HMAC-SHA-256)** under a per-agent key stored
off-chain, and **destroying that key is the erasure mechanism** the
guidelines themselves sanction.

## What is stored where

| Layer | What | Personal data? |
|---|---|---|
| Base mainnet (`MerkleAnchor`, chain 8453) | 32-byte Merkle roots + receipt counts + timestamps | No — roots of domain-separated hash trees, two hash layers away from any payload |
| GARL Postgres (off-chain, EU-erasable) | Receipt envelopes: metadata + `input_hash`/`output_hash` (keyed by default), signatures | Field-dependent; erasure supported (below) |
| Agent operator (off-chain) | The actual payloads. GARL never receives them — only hashes cross the API boundary | Operator's controllership |
| `agent_hash_keys` (off-chain, service-role-only RLS) | Per-agent HMAC keys | The unlinkability anchor; destroyable |

Independently checkable: the contract's storage layout is
`roots[batchId] → bytes32` only (source-verified on
[Sourcify](https://repo.sourcify.dev/8453/0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2));
every anchored batch and its transaction is listed at
[garl.ai/anchors](https://garl.ai/anchors).

## Paragraph-by-paragraph mapping (¶48–¶56)

**¶48 — prefer storing personal data off-chain.**
GARL's design rule from day one: payloads never reach GARL, let alone the
chain. The API accepts only 64-hex digests (`input_hash`, `output_hash`);
the receipt envelope is off-chain Postgres; the chain sees weekly Merkle
roots. Confirmed by the contract source and the wire schemas
(`protocol/schema/action-receipt-v0.1.json`).

**¶49–¶51 — if on-chain storage is unavoidable, minimise; plain hashes and
even encrypted data remain personal data when re-linkable.**
Not applicable in the strong sense (no per-receipt data is on-chain), but
GARL applies the same logic one layer down: the off-chain ledger is public,
so the hashes *in it* are treated under ¶52 rather than assumed anonymous.

**¶52 — an unsalted/unkeyed hash of personal data is personal data**, because
whoever can enumerate candidate inputs can confirm them by re-hashing.
GARL's response, shipped in the API:

- `input_hash`/`output_hash` computed by GARL itself are **HMAC-SHA-256 under
  a per-agent 256-bit key** (`backend/app/core/keyed_hash.py`), declared in
  the signed envelope's `hash_scheme` field.
- Caller-computed hashes: plain `sha256` is **rejected** unless the caller
  explicitly declares `non_personal_payload: true`; the documented default is
  keyed hashing with the key from `GET /api/v1/agents/{id}/hash-key`.
- PII masking of trace summaries (`pii_mask: true`) emits
  `hmac-sha256:<key_id>:<digest>` instead of the previous `sha256:<digest>`.

**¶53 — assess identifiability from the hash plus auxiliary data.**
For keyed hashes, confirmation requires the HMAC key, which never leaves the
`agent_hash_keys` table (service-role-only row-level security; no public
read policy; secrets are 256-bit random, not derived). Without the key,
a hash cannot be tested against candidate inputs even by GARL's public-DB
readers.

**¶54 — "a pointer, a cryptographic commitment or a hash generated from a
keyed hash function" on-chain, verification data off-chain.**
This paragraph describes GARL's construction almost verbatim:
on-chain = Merkle root (a commitment); off-chain = envelope + keyed hash +
Merkle path (`GET /api/v1/receipts/{id}/proof`). Verification is a
*capability* granted by whoever holds the payload and (for keyed hashes) the
key — not an ambient property of the public record.

**¶55 — deletion/rectification must remain effectively possible.**
Off-chain: receipt rows live in Postgres. The ledger is
append-only by design (that is the evidentiary product), so GARL's erasure
path is **key destruction**, per the mechanism ¶52/¶56 contemplate:
`DELETE /api/v1/agents/{id}/hash-key` nulls every key secret for the agent
(irreversibly — a DB trigger blocks resurrection). Every keyed hash the
agent ever published degrades to an unlinkable random-looking commitment.
Agent-level identity erasure additionally exists
(`POST /api/v1/agents/{id}/anonymize`, soft-delete — see `docs/security.md`).

**¶56 — anonymisation by deleting the off-chain verification data / key.**
Exactly the shipped mechanism. Sequence: destroy hash keys (severs content
linkage) → anonymize agent (severs identity linkage) → what remains in the
immutable ledger and under the on-chain roots is a set of signed statements
about an unlinkable pseudonym with unlinkable content commitments.

## Honest limitations

- **Legacy trace hashes are plain SHA-256.** The `trace_hash` of the legacy
  ledger hashes the full trace record (which may include a free-text
  `task_description`). Changing it would break every issued receipt URL and
  signature, so it stays — the mitigation is (a) keyed PII masking for the
  summary fields, (b) the 1 000-char cap and documented guidance to keep
  payloads out of `task_description`, (c) key-destruction + anonymisation
  covering the identity side. New-rail receipts (`POST /api/v1/receipts`)
  are where the keyed default fully applies.
- **`hash_scheme` is a declaration for caller-computed hashes.** GARL cannot
  cryptographically distinguish a caller's HMAC from a caller's plain hash;
  it can only refuse undeclared plain mode and record the declaration inside
  the signed envelope (which makes a false declaration a signed false
  statement by the submitting operator).
- **Receipts issued before 2026-08 have no `hash_scheme` field.** Verifiers
  must treat absence as *unspecified*, not as plain.

## Pointers

- Implementation: `backend/app/core/keyed_hash.py`,
  `supabase/migrations/20260803_v22_agent_hash_keys.sql`
- Wire format: `protocol/spec/action-receipt-v0.1.md` §4.2
- Key endpoints: `GET|DELETE /api/v1/agents/{id}/hash-key`,
  `POST /api/v1/agents/{id}/hash-key/rotate`
- EU AI Act Art. 12/19 mapping: `docs/compliance/eu-ai-act.md`
