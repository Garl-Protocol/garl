# Changelog — @garl-protocol/sdk

## 1.1.0 — 2026-04-14

### Added
- **`client.receipt(traceHash)`** — fetch the public receipt for any trace hash (full or 8-63 char short). Returns the enriched payload including `receiptUrl`, `shortHash`, agent summary, and ECDSA certificate.
- **camelCase aliases**: `verify()` and `receipt()` responses now expose `receiptUrl`, `shortHash`, `traceHash` alongside the snake_case API fields, giving TypeScript consumers ergonomic property names.

## 1.0.3 — 2026-03-11
- Retry + timeout polish in `retryFetch`.

## 1.0.0 — 2026-03-05
- Initial public release: `init`, `logAction`, `isTrusted`, `requireTrust`, `GarlClient`.
