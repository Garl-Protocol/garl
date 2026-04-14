# Changelog — garl-protocol (Python)

## 1.1.0 — 2026-04-14

### Added
- **`client.receipt(trace_hash)`** (`GarlClient` + `AsyncGarlClient`) — fetch the public receipt for any trace hash (full or 8-63 char short). Returns the enriched payload including `receipt_url`, `short_hash`, agent summary, and ECDSA certificate. No API key required.
- `log_action(..., background=False)` and `GarlClient.verify()` responses now surface `receipt_url` — a shareable page at `https://garl.ai/r/{short}` with an Open Graph preview card.

## 1.0.2 — 2026-03-11
- Async client polish, heartbeat cadence fix.

## 1.0.0 — 2026-03-05
- Initial public release.
