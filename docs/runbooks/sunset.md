# Sunset (2026-09-24)

GARL was archived on 2026-09-24. This page records what changed and how to bring it back.

## What runs now

| Surface | State |
|---|---|
| garl.ai | Railway `frontend` service built from `frontend/Dockerfile.sunset`: static page (`frontend/sunset/site`), `/anchors`, `llms.txt`, `security.txt`. Every other path returns the sunset page with HTTP 410. |
| api.garl.ai | Railway `backend` service built from `backend/Dockerfile.sunset`: read-only snapshot of `/.well-known/garl-keys.json`, `/api/v1/keys`, `/api/v1/anchors`, and `/api/v1/receipts/{receipt_id or output_hash}/proof` + `/cert.json` for all 12 anchored receipts. `/health` returns 200. Everything else returns JSON 410. |
| MerkleAnchor on Base | Unchanged: `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, 5 batches (`nextBatchId` = 6). `verifyProof` works without any GARL service. |
| Scheduled workflows | `anchor.yml`, `lighthouse.yml`, `session-scan.yml` and `garl-receipt.yml` disabled before archiving. |
| Supabase / Clerk | Untouched by this step; the application no longer runs, so nothing reads or writes them. |

The snapshot under `backend/sunset/site` was taken from the live API on 2026-09-24. Every proof was re-checked against the contract with `cast call ... verifyProof` before shutdown.

## Revival

1. Unarchive `Garl-Protocol/garl` (and `garl-receipt-action`, `garl-receipt-demo` if needed).
2. In `frontend/railway.toml` and `backend/railway.toml` set `dockerfilePath = "Dockerfile"` and push to `main`. Railway rebuilds the application images. Environment variables were left in place.
3. Re-enable workflows: `gh workflow enable anchor.yml` (and the others as needed).
4. Undo deprecations: `npm deprecate @garl-protocol/mcp-server ""`, `npm deprecate @garl-protocol/sdk ""`, and `mcp-publisher status --status active` for `io.github.Garl-Protocol/agent-trust`.
5. If the Supabase project was paused, restore it before step 2.
