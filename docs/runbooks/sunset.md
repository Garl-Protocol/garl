# Sunset (2026-09-24)

GARL was archived on 2026-09-24. This page records what changed and how to bring it back.

## What runs now

| Surface | State |
|---|---|
| garl.ai | Railway `frontend` service built from `frontend/Dockerfile.sunset`: static page (`frontend/sunset/site`), `/anchors`, `llms.txt`, `security.txt`. Every other path returns the sunset page with HTTP 410. |
| api.garl.ai | Railway `backend` service built from `backend/Dockerfile.sunset`: read-only snapshot of `/.well-known/garl-keys.json`, `/api/v1/keys`, `/api/v1/anchors`, and `/api/v1/receipts/{receipt_id or output_hash}/proof` + `/cert.json` for all 12 anchored receipts. `/health` returns 200. Everything else returns JSON 410. |
| MerkleAnchor on Base | Unchanged: `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, 5 batches (`nextBatchId` = 6). `verifyProof` works without any GARL service. |
| Scheduled workflows | `anchor.yml`, `lighthouse.yml`, `session-scan.yml` and `garl-receipt.yml` disabled before archiving. |
| Supabase | Project deleted on 2026-09-24 after a full export of all 12 public tables (row counts verified against the server). The export is kept offline by the maintainer. |
| Clerk | Production application deleted on 2026-09-24. |
| Signing key | `SIGNING_PRIVATE_KEY_HEX` removed from Railway and destroyed. Key `8c6e8f25ef3bf704` can no longer sign; its public half stays published so existing receipts remain verifiable. |
| Packages | npm `@garl-protocol/mcp-server` and `@garl-protocol/sdk` deprecated; PyPI `garl-protocol` archived; MCP registry `io.github.Garl-Protocol/agent-trust` deprecated; `garl-receipt-action` removed from GitHub Marketplace. |

The snapshot under `backend/sunset/site` was taken from the live API on 2026-09-24. Every proof was re-checked against the contract with `cast call ... verifyProof` before shutdown.

## Revival

1. Unarchive `Garl-Protocol/garl` (and `garl-receipt-action`, `garl-receipt-demo` if needed).
2. Create a new Supabase project, apply `backend/migrations` in order, then import the offline export.
3. Generate a new signing key and publish it next to `8c6e8f25ef3bf704` in the key registry (keep the old public key so existing receipts still verify). Create a new Clerk application.
4. Set the Railway variables again: backend `SIGNING_PRIVATE_KEY_HEX`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` (plus `GITHUB_APP_*` for the PR bot); frontend `CLERK_SECRET_KEY`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`.
5. In `frontend/railway.toml` and `backend/railway.toml` set `dockerfilePath = "Dockerfile"` and push to `main`. Railway rebuilds the application images.
6. Re-enable workflows: `gh workflow enable anchor.yml` (and the others as needed).
7. Undo deprecations: `npm deprecate @garl-protocol/mcp-server ""`, `npm deprecate @garl-protocol/sdk ""`, `mcp-publisher status --status active` for `io.github.Garl-Protocol/agent-trust`, unarchive on PyPI, and re-tick "Publish to Marketplace" on the action's latest release.
