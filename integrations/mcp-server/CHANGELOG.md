# Changelog — @garl-protocol/mcp-server

## 1.2.0 — 2026-04-14

### Added
- **`garl_receipt` tool** — resolves any full 64-char SHA-256 or 8-63 char short hash to a public shareable Receipt URL (`https://garl.ai/r/{short}`) with agent summary and ECDSA signature. No API key required.
- `garl_verify` now includes `Receipt: https://garl.ai/r/{short}` in its success output so Claude Desktop / Cursor users can paste the URL directly.

## 1.1.3 — 2026-03-11
- Trust gate token improvements; nonce + 5-minute expiry.

## 1.1.2 — 2026-03-10
- `garl_simulate_score` tool for what-if analysis.

## 1.1.0 — 2026-03-05
- Initial public release with 17 tools.
