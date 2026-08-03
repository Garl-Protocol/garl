# GARL Capability Token — v0.1

**Status:** Draft (v0.1 = breaking-change allowed; v1.0 freezes wire format)
**Date:** 2026-08-03
**Editors:** GARL Protocol maintainers
**Wire identifier:** `garl-cap-v0.1`

## 1. Summary

A GARL Capability Token is a signed, attenuable, revocable credential that
records **what an agent was authorized to do**: which scope, at which
side-effect class, under which spending and merchant constraints, delegated by
whom, and until when.

Together with the Action Receipt (`action-receipt-v0.1.md`) it closes the
evidence loop for agent actions:

- the **receipt** proves what was *done*;
- the **capability token** it references proves what was *allowed*.

This is the artifact a compliance reviewer, insurer, or platform operator asks
for after the fact: not "did the agent act", but "was the agent within its
delegated authority when it acted".

The current canonical issuer is `https://api.garl.ai`. Self-hosted issuers
publish the same shape; verifiers distinguish by `iss` and by resolving the
`kid` against the matching key registry (`/.well-known/garl-keys.json`).

### 1.1 Design: Biscuit-style attenuation without the Biscuit dependency

The delegation model is deliberately Biscuit-shaped: any token holder can
request a **child** token that only *narrows* the parent's authority (scope,
side-effect class, spend limit, merchant allowlist, caveats, expiry), and the
verifier re-checks every link of the chain rather than trusting the issuer's
issue-time discipline. Unlike Biscuit, the envelope is a plain JWT-shaped
three-segment token:

- **One crypto stack.** The same ECDSA-secp256k1 / RFC 6979 / low-S signing
  path and the same key registry used for Action Receipts. One verifier
  codebase covers both artifacts.
- **One familiar envelope.** `header.payload.signature` in unpadded base64url
  (RFC 7515 conventions) is what OAuth-adjacent infrastructure already parses.
- **Chaining instead of offline attenuation.** A child token carries
  `parent` = SHA-256 of the parent's wire form. Attenuation is enforced by the
  issuer at issue time AND re-verified per link at verification time (§5, §7).
  The trade-off relative to Biscuit is that minting a child requires the
  issuer (attenuation is not holder-local), and full chain verification
  requires access to the token registry (§7.3).

## 2. Wire format

A capability token is an ASCII string of exactly three dot-separated
segments:

```
base64url(canonical_json(header)) "." base64url(canonical_json(payload)) "." base64url(signature)
```

- **base64url** is RFC 7515 §2 base64url **without padding**. Encoders MUST
  NOT emit `=` padding. The reference decoder is padding-tolerant, but
  interoperable producers MUST emit the unpadded form (the token hash and the
  signature are computed over the exact wire bytes).
- **canonical_json** is GARL Canonical JSON v0.1 (`canonical-json-v0.1.md`):
  keys sorted, no whitespace, `ensure_ascii=true`, `NaN`/`Infinity` rejected.
  The canonical form governs the bytes produced **at issue time**;
  verification reconstructs the signing input from the raw base64 segments as
  received and therefore never re-canonicalizes (§7).
- **signature** is a raw 64-byte `r || s` ECDSA-secp256k1 signature
  (32 bytes each, big-endian), RFC 6979 deterministic, normalized to
  **low-S** (`s <= n/2`, BIP-62/EIP-2 rule). Issuers MUST emit low-S; the
  reference verifier accepts high-S (signature validity is checked, not
  low-S-ness).

The signing input is:

```
SHA-256( header_b64 || "." || payload_b64 )
```

signed with ECDSA-secp256k1 over that digest. Because RFC 6979 is
deterministic and the JSON form is canonical, identical claims signed under
the same key produce a byte-identical token — issuers can de-duplicate on the
wire form.

### 2.1 Header

```json
{"alg": "ES256K", "kid": "<16-hex key fingerprint>", "typ": "garl-cap-v0.1"}
```

| Field | Value | Notes |
|---|---|---|
| `alg` | const `"ES256K"` | ECDSA-secp256k1 + SHA-256. Verifiers MUST reject any other value — no algorithm negotiation. |
| `typ` | const `"garl-cap-v0.1"` | Wire-format version. Bumped on breaking change. Verifiers MUST reject unknown values. |
| `kid` | string | First 16 hex chars of SHA-256 of the issuer's public key (64-byte uncompressed `x || y`, no `04` prefix). Resolved via the key registry (§9). Verifiers MUST reject a missing or unresolvable `kid`. |

### 2.2 Payload

Always-present claims:

```json
{
  "iss": "https://api.garl.ai",
  "sub": "did:garl:<agent uuid>",
  "iat": <unix seconds>,
  "exp": <unix seconds>,
  "scope": "<scope string, §4.1>",
  "side_effect_class": "none" | "reversible" | "irreversible",
  "caveats": [ <object>, ... ]
}
```

Optional claims (omitted entirely when not applicable — never `null`):

```json
  "spend_limit_usd": <number>,
  "merchant_allowlist": ["<merchant>", ...],
  "parent": "<64-hex sha256 of parent token wire form>",
  "delegate": "<opaque human-delegate identifier>"
```

`caveats` is always present, `[]` when empty. `merchant_allowlist` is stored
**sorted and de-duplicated** at issue time. An empty `merchant_allowlist`
input results in the claim being omitted (an omitted allowlist means
"unconstrained", see §4.4).

### 2.3 Worked example (NON-NORMATIVE)

All values below are fabricated for illustration; the signature is a
placeholder and will not verify. Header:

```json
{"alg":"ES256K","kid":"8c6e8f25ef3bf704","typ":"garl-cap-v0.1"}
```

Payload (canonical form, one line):

```json
{"caveats":[{"max_calls":5}],"delegate":"github:ardakutsal","exp":1777626000,"iat":1777622400,"iss":"https://api.garl.ai","merchant_allowlist":["stripe.com"],"scope":"payment:stripe.com","side_effect_class":"reversible","spend_limit_usd":25.0,"sub":"did:garl:3216b8ed-fa2c-452a-bda2-925cde273314"}
```

Reading: agent `3216b8ed-…`, acting for human delegate `github:ardakutsal`,
may perform reversible payment actions against `stripe.com`, spending at most
USD 25, at most 5 calls, valid 2026-05-01T08:00Z through 09:00Z.

Wire form (line-wrapped for display; the real token is one line):

```
eyJhbGciOiJFUzI1NksiLCJraWQiOiI4YzZlOGYyNWVmM2JmNzA0IiwidHlwIjoiZ2FybC1jYXAtdjAuMSJ9
.
eyJjYXZlYXRzIjpbeyJtYXhfY2FsbHMiOjV9XSwiZGVsZWdhdGUiOiJnaXRodWI6YXJkYWt1dHNhbCIsImV4cCI6MTc3NzYyNjAwMCwiaWF0IjoxNzc3NjIyNDAwLCJpc3MiOiJodHRwczovL2FwaS5nYXJsLmFpIiwibWVyY2hhbnRfYWxsb3dsaXN0IjpbInN0cmlwZS5jb20iXSwic2NvcGUiOiJwYXltZW50OnN0cmlwZS5jb20iLCJzaWRlX2VmZmVjdF9jbGFzcyI6InJldmVyc2libGUiLCJzcGVuZF9saW1pdF91c2QiOjI1LjAsInN1YiI6ImRpZDpnYXJsOjMyMTZiOGVkLWZhMmMtNDUyYS1iZGEyLTkyNWNkZTI3MzMxNCJ9
.
<base64url of 64-byte r||s signature>
```

The `token_hash` of this token is `SHA-256` of the full one-line wire form
(§8), e.g. `212a5417…` for the placeholder-signed string above.

## 3. Lifetimes

| Constant | Value |
|---|---|
| Default TTL | 3600 seconds (1 hour) |
| Maximum TTL | 604800 seconds (7 days) |

Issuers MUST reject `expires_in_seconds <= 0` and
`expires_in_seconds > 604800`. Longer-lived authority requires re-issuance
under explicit policy, not a longer token. `exp = iat + expires_in_seconds`;
both are integer Unix seconds.

## 4. Claim semantics

| Claim | Type | Semantics |
|---|---|---|
| `iss` | URI | Issuing registry. Canonical: `https://api.garl.ai`. |
| `sub` | DID | `did:garl:<agent uuid>` — the agent the authority is granted to. Matches `agent_identity` in Action Receipts. |
| `iat` | int | Issue time, Unix seconds, issuer clock. |
| `exp` | int | Expiry, Unix seconds. A token with `exp <= now` is invalid. |
| `scope` | string | What the token authorizes, colon-delimited with wildcards (§4.1). |
| `side_effect_class` | enum | Worst-case blast radius the token authorizes (§4.2). |
| `spend_limit_usd` | number, optional | Maximum spend in USD (§4.3). |
| `merchant_allowlist` | string[], optional | Closed set of permitted counterparties (§4.4). |
| `caveats` | object[] | Free-form restriction objects, monotonically accumulated down a delegation chain (§4.5). |
| `parent` | hex(64), optional | `token_hash` of the parent token this one attenuates (§5). Absent on root tokens. |
| `delegate` | string, optional | Opaque identifier of the human who delegated this authority (e.g. `github:ardakutsal`). Mirrors `human_delegate` in Action Receipts. |

### 4.1 Scope grammar

```
SCOPE   := SEGMENT (":" SEGMENT)*
SEGMENT := "*" | <any non-empty string not containing ":">
```

Typical shapes: `payment:stripe.com`, `github:issue:create`,
`code_write:*`. The Capability Gate (§6.2) defaults to
`<action_type>:<target>` or `<action_type>:*` when no scope is requested.

**Covering relation.** `covers(parent, child)` — used by attenuation — is
defined as:

1. If `parent == child`, or `parent == "*"` (the whole-scope wildcard),
   the parent covers the child.
2. Otherwise split both on `":"`. If the child has **fewer** segments than
   the parent, the parent does not cover it.
3. For each parent segment at position *i*: `"*"` matches any child segment;
   any other value must equal the child segment at *i* exactly.
4. Child segments beyond the parent's length are unconstrained — a child MAY
   be more specific by appending segments.

Consequences (normative examples):

- `payment:*` covers `payment:stripe.com` — but `payment:stripe.com` does
  **not** cover `payment:*`. Wildcards only ever widen the parent side; a
  child can never introduce a wildcard where its parent had a literal.
- `payment:*` covers `payment:stripe.com:charge` (extra child segments are
  narrowing).
- `payment:stripe.com` covers `payment:stripe.com:charge`.
- `payment` does not cover `github` (literal mismatch at segment 0).
- Matching is exact string comparison per segment; there is no partial or
  prefix matching within a segment.

### 4.2 `side_effect_class`

The enum and its meaning are shared with Action Receipt §5:

| Class | Rank | Meaning |
|---|---|---|
| `none` | 0 | Read-only; no state change. |
| `reversible` | 1 | Mutates state; one follow-up action undoes it. |
| `irreversible` | 2 | No automatic undo (live payment, sent email, destructive write). |

The rank ordering `none < reversible < irreversible` is normative: it drives
both attenuation (§5) and the Capability Gate thresholds (§6.2). Verifiers
MUST reject any value outside the enum.

### 4.3 `spend_limit_usd`

Maximum permitted spend, USD. Presence of the claim is meaningful: an absent
`spend_limit_usd` means the token expresses no spend constraint. Once a
parent sets a limit, every descendant MUST carry one at or below it (§5).
The token records the *authorized ceiling*; actual spend accounting is the
tool server's / receipt layer's job — this claim is the evidence of what
ceiling was granted.

### 4.4 `merchant_allowlist`

Closed set of permitted counterparties (free-form strings, conventionally
hostnames). Stored sorted and de-duplicated. Absent = unconstrained. Once a
parent sets a non-empty allowlist, every descendant MUST carry a non-empty
subset of it (§5).

### 4.5 `caveats`

An array of free-form JSON objects, each expressing an additional
restriction (e.g. `{"max_calls": 5}`, `{"region": "eu"}`). v0.1 does not
define a caveat vocabulary — enforcement of individual caveat semantics is
the presenting tool server's responsibility. What the protocol *does*
enforce is monotonicity: caveats only accumulate down a delegation chain
(§5). Caveat identity is decided on the **canonical JSON form** of each
object, so key order and whitespace differences do not defeat the subset
check.

## 5. Attenuation rules (normative)

A child token may only **narrow** its parent. The following rules are
enforced by `_enforce_attenuation` at **issue time** (child issuance is
refused) and re-checked for **every link of the chain at verification time**
when revocation checking is enabled (§7.2) — so the chain is a verifier-side
guarantee, not issuer goodwill.

For each rule, "parent" and "child" are the decoded payload claims of the
adjacent pair:

1. **Side-effect class.** `rank(child.side_effect_class)` MUST be `<=`
   `rank(parent.side_effect_class)`, ranks per §4.2. A missing
   `side_effect_class` on either side is treated as `irreversible` for this
   comparison. Failure: "Child side_effect_class is broader than parent's".
2. **Spend limit.** If `parent.spend_limit_usd` is present, then
   `child.spend_limit_usd` MUST be present and MUST be `<=` the parent's
   value (equality allowed). Failure: "Child spend_limit_usd must be set and
   <= parent's". If the parent has no spend limit, the child MAY set any or
   none.
3. **Merchant allowlist.** If `parent.merchant_allowlist` is present and
   non-empty, then `child.merchant_allowlist` MUST be present, non-empty,
   and a subset (as sets) of the parent's. Failure: "Child
   merchant_allowlist must be a subset of parent's". If the parent has no
   allowlist, the child MAY set any or none.
4. **Scope.** If `parent.scope` is present and non-empty,
   `covers(parent.scope, child.scope)` (§4.1) MUST hold; a missing child
   scope is compared as the empty string and fails unless covered. Failure:
   "Child scope is not within parent scope".
5. **Caveats.** The set of the parent's caveats (each in canonical JSON
   form) MUST be a subset of the set of the child's caveats — the child
   retains every parent caveat and MAY add more. Failure: "Child must retain
   all parent caveats (caveats only narrow)".
6. **Expiry.** `child.exp` MUST be `<=` `parent.exp` (a missing `exp` is
   compared as 0). Failure: "Child token cannot outlive parent (exp)".

Additionally, at issue time the parent MUST exist in the issuer's registry,
MUST NOT be revoked, and its stored wire form MUST be decodable; otherwise
child issuance is refused.

A useful corollary of rule 6: if the leaf token is unexpired, every ancestor
is also unexpired — the chain walk therefore does not need a separate
ancestor-expiry check.

## 6. Issuance

### 6.1 Direct issuance — `POST /api/v1/capability/issue`

Authenticated with the agent's API key (`X-API-Key` header). The caller MUST
prove ownership of `agent_id` — the token is minted under that agent's DID
and signed by the issuer, so unauthenticated issuance would allow
impersonating any agent.

Request body:

| Field | Required | Notes |
|---|---|---|
| `agent_id` | yes | UUID of a registered agent. |
| `scope` | yes | §4.1. Must be non-empty. |
| `side_effect_class` | yes | §4.2 enum. |
| `expires_in_seconds` | no | Default 3600; bounds per §3. |
| `spend_limit_usd` | no | §4.3. |
| `merchant_allowlist` | no | §4.4. |
| `caveats` | no | §4.5; default `[]`. |
| `parent_token_hash` | no | Mint an attenuated child of this token (§5). |
| `human_delegate` | no | Becomes the `delegate` claim. |

Response: `{"token", "token_hash", "expires_at", "claims"}` — the wire-form
token, its SHA-256 hex handle, RFC 3339 expiry, and the decoded payload.
Attenuation or bound violations return HTTP 400 with the failure reason;
missing required fields return 422. The row is persisted to the registry
**before** the token is returned (this ordering is what makes the fail-closed
revocation rule in §7.3 sound).

### 6.2 Gate issuance — `POST /api/v1/capability/evaluate`

The Capability Gate is the pre-flight path: it turns the agent's Trust
Vector (`trust-vector-v0.1.md`) plus the intended action into a decision, and
mints a token only on `allowed`. Authenticated with the agent's API key.

1. The requested `action_type` selects a Trust Vector dimension
   (`code_write`/`tool_call`/`api_call`/`browser_action`/`file_op` →
   `code_task_reliability`; `payment` → `agent_identity_assurance`; unknown
   action types and dimensions without data fall back to
   `agent_identity_assurance`).
2. The dimension score is compared to a threshold by side-effect class:
   `none` → 0.0, `reversible` → 0.40, `irreversible` → 0.70 (a per-request
   `threshold_override` MAY replace these).
3. Below threshold: decision is `requires_human` for `irreversible`
   (escalation path), `denied` otherwise; no token is minted.
4. At or above threshold: decision is `allowed` and a fresh token is issued
   with scope `requested_scope`, or `<action_type>:<target>`, or
   `<action_type>:*` when no target is given.

The gate's decision is recorded in the Action Receipt `policy_decision`
field when the action runs, so the verdict becomes part of the immutable
record.

### 6.3 Revocation — `POST /api/v1/capability/revoke`

Authenticated; only the owner of the agent the token was issued to may
revoke it. Request: `{"token_hash", "reason"?, "cascade"?}` (reason defaults
to `"manual-revoke"`, cascade defaults to `true`). Unknown `token_hash`
returns 404.

Semantics:

- **Single revocation** sets `revoked_at` (issuer clock, UTC) and
  `revocation_reason` on the token's registry row. Revocation is permanent;
  there is no un-revoke.
- **Cascade** (default): a breadth-first walk over the registry's
  `parent_token_hash` edges marks every descendant with reason
  `"cascade: <reason>"`. Revoking a root kills the entire delegation tree.
- **Idempotency:** only rows with `revoked_at IS NULL` are updated. Revoking
  an already-revoked token changes nothing (its original `revoked_at` and
  reason are preserved) and it is not counted again in the primary result.
- Response: `{"revoked": [token_hash, ...], "count": N}` — the set of
  token hashes the cascade traversed.

## 7. Verification

### 7.1 Algorithm (normative)

Given a candidate wire string, a verifier MUST perform these checks in
order, failing closed on the first violation:

1. **Structure.** The string MUST split on `.` into exactly 3 parts.
2. **Decode.** base64url-decode all three segments; parse segments 1 and 2
   as JSON. Any decode/parse failure is fatal.
3. **Type.** `header.typ` MUST equal `"garl-cap-v0.1"`.
4. **Algorithm.** `header.alg` MUST equal `"ES256K"`. No other algorithm is
   accepted; there is no negotiation and no `"none"`.
5. **Key id.** `header.kid` MUST be present and MUST resolve to a public key
   via the issuer's key registry — the active key or any retired key (§9).
   Unknown `kid` is fatal.
6. **Signature.** Compute `SHA-256(header_b64 || "." || payload_b64)` over
   the **raw base64 segments as received** (no re-canonicalization) and
   verify the 64-byte `r || s` ECDSA-secp256k1 signature against the
   resolved public key.
7. **Expiry.** `payload.exp` MUST be an integer and MUST be strictly greater
   than the verifier's current Unix time.
8. **Issue time.** If `payload.iat` is an integer, it MUST NOT exceed
   `now + 60` seconds (60 s clock-skew allowance; blatantly future-dated
   tokens are rejected).
9. **Side-effect class.** `payload.side_effect_class` MUST be one of
   `none`, `reversible`, `irreversible`.
10. **Revocation and chain** (only when revocation checking is enabled,
    §7.2):
    a. Compute `token_hash` (§8) and look it up in the registry. A revoked
       row — or a `token_hash` **unknown to the registry** — is fatal (§7.3).
    b. Walk the parent chain: starting from `payload.parent`, for each
       ancestor hash: the ancestor MUST exist in the registry, MUST NOT be
       revoked, its stored wire form MUST be decodable, and the attenuation
       rules of §5 MUST hold between it and its immediate child in the
       chain. Continue with the ancestor's own `parent` claim until a root
       (no `parent`) is reached.

On success the verifier returns the decoded payload claims.

### 7.2 Online vs. offline verification

Steps 1–9 are fully **offline**: they require only the token and a cached
copy of the key registry (`/.well-known/garl-keys.json`). A tool server can
therefore accept a token at the edge with no call to GARL.

Step 10 requires the token registry, i.e. it is **online** with respect to
the issuer. The hosted verifier exposes both modes via
`POST /api/v1/capability/verify` (public, unauthenticated), body
`{"token", "check_revocation"?}` with `check_revocation` defaulting to
`true`; response `{"valid": true, "claims": {...}}` or
`{"valid": false, "reason": "..."}` (verification failures are reported in
the body, not as HTTP errors).

**The trade-off is explicit and MUST be understood by integrators:**
disabling revocation checking (`check_revocation=false`) skips *both* the
revocation lookup *and* the parent-chain attenuation re-check — the chain
walk needs the registry because only the parent's *hash* travels in the
token, not the parent itself. A fully-offline verifier therefore gets
signature, expiry, format, and claim validity, but accepts the residual
risks that (a) the token or an ancestor has been revoked since issuance, and
(b) for chained tokens, attenuation is being trusted at issue-time
enforcement only. Short TTLs (§3) are the primary mitigation for (a);
verifiers that accept `irreversible`-class tokens SHOULD use online
verification.

### 7.3 Fail-closed unknown-hash rule

When revocation checking is enabled and the computed `token_hash` is not
present in the registry, the verifier treats the token as **revoked** and
rejects it. Rationale: legitimate issuance persists the registry row before
the token is ever returned to a caller (§6.1), so a well-formed,
correctly-signed token whose hash is unknown was never issued by the
registry's issuance path (or has been purged) — for example a token minted
offline by a party holding the signing key. Failing open here would let such
a token pass the revocation check. The corollary is the §7.2 trade-off: an
intentionally offline-minted token can only ever be verified with
`check_revocation=false`.

## 8. `token_hash` and the receipt linkage

```
token_hash := lowercase hex( SHA-256( full token wire form as ASCII ) )
```

The hash is over the complete `header.payload.signature` string — 64 hex
characters. It is the token's stable public handle: it appears in the
registry, in revocation requests, in the `parent` claim of child tokens, and
— critically — in Action Receipts.

**Receipt binding.** When an action runs under a capability token, the
Action Receipt records it in `capability_request.token_hash` (Action Receipt
§6), alongside a summary of the token's scope, limits, and expiry. This is
the authorization↔action evidence link:

- the receipt (signed, immutable, Merkle-anchored) proves what was **done**;
- the referenced token (signed, attenuation-checked, revocation-tracked)
  proves what was **allowed**;
- the hash binding means neither side can be swapped after the fact.

Per Action Receipt §6, verifiers SHOULD reject receipts whose `side_effect`
is more dangerous than the referenced token's `side_effect_class`.

Because the hash covers the signature segment and signatures are RFC 6979
deterministic with canonical JSON payloads, identical claims under the same
key always produce the same `token_hash`.

## 9. Key registry and rotation

Tokens are verified against the issuer's public key registry — the same
registry used for Action Receipts:

- `https://api.garl.ai/.well-known/garl-keys.json` (also `/api/v1/keys`).
- Each entry: `{key_id, public_key_hex, status: "active" | "retired", algorithm: "ECDSA-secp256k1"}`.
- `key_id` (= the token's `kid`) is the first 16 hex characters of
  SHA-256 over the raw 64-byte uncompressed public key (`x || y`, no `04`
  prefix). `public_key_hex` is that 64-byte key as 128 hex characters.
- Rotation: a new active key gets a new `kid`; retired keys remain in the
  registry so previously issued tokens keep verifying until they expire.
  Verifiers MUST resolve `kid` against the live registry rather than pinning
  a single key, and MUST reject tokens whose `kid` resolves to no registry
  entry.

## 10. Storage

Issued tokens are persisted in the `capability_tokens` table
(migration `20260427_v18_wave2_foundation.sql`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | Row identity. |
| `token_hash` | CHAR(64) UNIQUE NOT NULL | §8. |
| `agent_id` | UUID NOT NULL → `agents(id)` | Grantee. |
| `human_delegate` | TEXT | `delegate` claim. |
| `jwt_form` | TEXT NOT NULL | Full wire form. Sensitive — see below. |
| `caveats` | JSONB NOT NULL DEFAULT `[]` | §4.5. |
| `scope` | TEXT NOT NULL | §4.1. |
| `spend_limit_usd` | NUMERIC(12,6) | §4.3. |
| `side_effect_class` | VARCHAR(20) CHECK in enum | §4.2 (enum CHECK-enforced in the DB as well). |
| `merchant_allowlist` | TEXT[] | §4.4. |
| `parent_token_hash` | CHAR(64) | Delegation edge; indexed for cascade walks. |
| `issued_at` | TIMESTAMPTZ DEFAULT now() | |
| `expires_at` | TIMESTAMPTZ NOT NULL | |
| `revoked_at` | TIMESTAMPTZ | Null = live. |
| `revocation_reason` | TEXT | Free text; `"cascade: …"` for cascade victims. |

Row-level security: **service-role only** — there is no public read policy
on this table (unlike `receipts`). This is deliberate: `jwt_form` is the
bearer credential itself, and the registry stores it to enable the chain
walk (§7.1 step 10b) and revocation bookkeeping. Deployments MUST treat
`jwt_form` as a secret at rest and MUST NOT expose `capability_tokens` rows
through any public read path.

## 11. Security considerations

- **Bearer-ish credential.** The token names its subject (`sub`) but nothing
  in v0.1 forces the presenter to *be* that subject — possession of the wire
  form is sufficient to present it. Mitigations: short TTLs (§3), narrow
  scopes and caveats, revocation with cascade (§6.3), and the receipt
  linkage (§8), which makes use of a token attributable after the fact.
  Holder-proofing (e.g. presenter proof-of-possession) is a candidate for
  v1.0.
- **TTL bounds.** The 7-day hard cap (§3) bounds the exposure window of any
  leaked token; the fail-closed unknown-hash rule (§7.3) bounds forged ones.
- **No algorithm agility.** `alg` is pinned to ES256K and `typ` to
  `garl-cap-v0.1`; verifiers reject everything else, which forecloses
  JWT-style `alg=none` and key-confusion downgrade attacks by construction.
- **Deterministic, non-malleable signatures.** RFC 6979 removes nonce-RNG
  risk; low-S normalization means the issuer never emits a malleable twin of
  its own signature. Note that `token_hash` covers the signature bytes, so a
  high-S twin of a token would hash differently — another reason issuers
  MUST emit only low-S.
- **Clock skew.** Verifiers allow 60 s of forward skew on `iat` and none on
  `exp`. Integrators SHOULD run NTP-synced clocks.
- **Key rotation.** Handled via `kid` + the retired-keys registry (§9). A
  compromised signing key requires retiring the key *and* treating all
  unexpired tokens under that `kid` as suspect; the registry's issued-token
  table makes bulk revocation by key epoch feasible.
- **Signing-implementation side channel.** The reference issuer signs with
  python-ecdsa, which is not constant-time (Minerva, CVE-2024-23342). The
  risk assessment and rationale are documented in
  `backend/app/core/signing.py` (top-of-file note): server-side signing
  behind network jitter, deterministic nonces, low-S only; the planned
  hardening is moving the signing path to libsecp256k1. Verification is
  unaffected.
- **Registry as revocation oracle.** Online verification discloses to the
  issuer *that* a given token is being checked. Deployments for which this
  metadata is sensitive can self-host the issuer.

## 12. Interop appendix (NON-NORMATIVE)

These are mapping sketches, not shipped bridges. No conversion code exists
in the reference implementation today.

### 12.1 AP2 (Agent Payments Protocol) mandates

An AP2 **Intent Mandate** ("agent may spend up to $X on Y") maps naturally
onto a capability token: the mandate's spending ceiling becomes
`spend_limit_usd`, its merchant constraint becomes `merchant_allowlist`, the
authorizing human becomes `delegate`, and the mandate's validity window
becomes `iat`/`exp`. An AP2 **Cart Mandate** (a specific approved cart) is
the attenuated child: same chain, narrowed to the exact merchant and amount,
with cart specifics carried as `caveats`. The GARL attenuation rules (§5)
then give AP2's intent→cart narrowing an independently verifiable enforcement
mechanism, and the Action Receipt linkage (§8) supplies the post-hoc
evidence trail AP2 delegates to `agent_attestations`.

### 12.2 x402 (HTTP-native payments)

In an x402 flow, the natural join point is the payment proof: a client
paying under GARL-delegated authority would carry `token_hash` in the x402
payload's extension field, so the settlement record references the
authorization evidence. A facilitator or seller could then (online) verify
the token — scope covering the merchant, `spend_limit_usd` covering the
amount — before settling. The Action Receipt for the payment closes the
loop: `capability_request.token_hash` in the receipt equals the hash carried
in the x402 payload.

## 13. Open questions for v1.0

- Holder proof-of-possession (DPoP-style presenter binding) versus staying
  bearer-shaped with short TTLs.
- A defined caveat vocabulary (at minimum `max_calls`, rate, region) versus
  keeping caveats free-form per tool server.
- Carrying the parent chain *in* the token (Biscuit-style blocks) so
  attenuation is offline-verifiable, versus the current registry walk.
- Revocation freshness for offline verifiers (short-lived revocation lists
  or status assertions).

## 14. License

This specification is published under Apache 2.0 (see `LICENSE` at the
repository root). Reference implementation:
`backend/app/services/capability_tokens.py`,
`backend/app/services/capability_gate.py`, and
`backend/app/core/signing.py`.
