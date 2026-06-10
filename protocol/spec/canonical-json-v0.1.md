# GARL Canonical JSON v0.1

Status: **frozen**. This document specifies the exact byte sequence that GARL
signs and hashes. It is normative for anyone re-implementing a GARL verifier.

## Definition

Given a JSON value `obj`, its canonical form is:

```
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
```

UTF-8 encoded. Everything GARL signs or hashes is `SHA-256(canonical_bytes(obj))`.

Concretely, the rules are:

1. **Object keys sorted** lexicographically by Unicode code point, recursively.
2. **No insignificant whitespace** — item separator `,`, key/value separator `:`.
3. **`ensure_ascii = true`** — every non-ASCII character is emitted as a
   `\uXXXX` escape (e.g. `é` → `é`, `日` → `日`). The output is pure
   ASCII.
4. **`NaN` / `Infinity` / `-Infinity` are rejected.** They are not valid JSON;
   a payload containing them is refused, never signed.
5. Numbers, strings, booleans, `null`, arrays use standard `json` serialization.

The reference implementation is `backend/app/core/canonical.py`
(`canonical_str` / `canonical_bytes`). The shipped verifier
`sdks/python/garl_verify.py` uses a byte-identical form.

## Why this and not RFC 8785 (JCS)

RFC 8785 (JSON Canonicalization Scheme) is the obvious standard, but it mandates
`ensure_ascii = false` (raw UTF-8) and ECMAScript `Number` formatting. GARL's
signing form predates that decision and uses `ensure_ascii = true`. **Switching
to JCS now would change the signed bytes and invalidate every receipt already
issued** (including the on-chain-anchored genesis receipt). Because the form is
deterministic, stable, and sufficient for verification, it is deliberately
frozen here rather than migrated.

If a future `v0.2` adopts JCS, it must be a new signature version negotiated
alongside a key/format epoch, so `v0.1` receipts keep verifying under these
rules.

## Re-implementing a verifier in another language

ASCII-escaping is the subtle part. In JavaScript, `JSON.stringify` does **not**
escape non-ASCII by default, so you must post-process to `\uXXXX`-escape every
code point ≥ 0x80, sort keys recursively, and use no whitespace. Reject inputs
that contain `NaN`/`Infinity`. Then `SHA-256` the UTF-8 (here, ASCII) bytes and
verify the secp256k1 signature against a public key resolved from the GARL key
registry — never against a key embedded in the artifact being checked.
