# Runbook — Weekly Merkle Anchoring

The [Weekly Merkle Anchor workflow](../../.github/workflows/anchor.yml) rolls all
Action Receipts with `merkle_batch_id IS NULL` into one Merkle batch and anchors
the root on Base mainnet via the MerkleAnchor contract
(`0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, chain 8453). It runs every Monday
03:17 UTC and can be triggered manually (`workflow_dispatch` or
`gh workflow run anchor.yml -R Garl-Protocol/garl`).

Every anchored batch is public at [garl.ai/anchors](https://garl.ai/anchors) and
`GET /api/v1/anchors`.

## Required repository secrets

Settings → Secrets and variables → Actions on `Garl-Protocol/garl`:

| Secret | What | Where the value lives |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | `backend/.env` (local), Supabase dashboard → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (reads receipts, writes batches) | same |
| `DEPLOYER_PRIVATE_KEY` | MerkleAnchor **owner** key — only this key can call `anchor()` | `contracts/.env.deploy` (local only, never committed) |
| `BASE_RPC_URL` | optional; defaults to `https://mainnet.base.org` | — |

Set via CLI without echoing values:

```bash
gh secret set SUPABASE_URL -R Garl-Protocol/garl -b"$(grep '^SUPABASE_URL=' backend/.env | cut -d= -f2-)"
gh secret set SUPABASE_SERVICE_ROLE_KEY -R Garl-Protocol/garl -b"$(grep '^SUPABASE_SERVICE_ROLE_KEY=' backend/.env | cut -d= -f2-)"
gh secret set DEPLOYER_PRIVATE_KEY -R Garl-Protocol/garl -b"$(grep '^DEPLOYER_PRIVATE_KEY=' contracts/.env.deploy | cut -d= -f2-)"
```

The deployer wallet needs a small ETH balance on Base; each `anchor()` costs
~$0.01. Top it up when the failure issue (below) reports insufficient funds.

## Failure alerting

The job **fails loudly** — there is no silent skip:

- Missing secrets → the job exits 1 with an `::error::` annotation.
- Any failure (missing secrets, DB error, reverted tx) → the `Alert on failure`
  step opens a GitHub issue titled **"Weekly Merkle anchor FAILED"** labeled
  `anchor-failure`, or comments on the existing open one. Scheduled-workflow
  failures also email the repo watchers.

An open `anchor-failure` issue means the public anchor chain has a growing gap.
Treat it as a P1: the product claim "living anchor chain" is only true while
this cron is green.

## Manual anchor (local)

```bash
cd /path/to/garl
set -a; source backend/.env; source contracts/.env.deploy; set +a
export GARL_MERKLE_ANCHOR_CONTRACT=0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2
export GARL_MERKLE_ANCHOR_CHAIN_ID=8453
export BASE_RPC_URL=${BASE_RPC_URL:-https://mainnet.base.org}
python3 scripts/anchor_batch.py
```

Requires Foundry's `cast` on PATH and Python 3.11 with `backend/requirements.txt`
installed. The script is idempotent: it only batches receipts with
`merkle_batch_id IS NULL` and exits 0 when there is nothing to anchor.

## Partial-failure recovery

If `cast send` fails **after** a batch row was created, the batch stays
`anchored_at = NULL` and the script will not retry it (double-anchor guard).
Recovery is manual — see `contracts/DEPLOYMENTS.md`: re-broadcast
`anchor(root, count)` with the recorded root, then backfill the tx hash with
`record_anchor_tx()`.

## Verifying an anchor

Each batch on [garl.ai/anchors](https://garl.ai/anchors) links its Base
transaction. Independent check: the `Anchored(batchId, root, receiptCount)`
event on the contract must match the batch's `merkle_root` and
`receipt_count`, and every receipt's proof from
`GET /api/v1/receipts/{id}/proof` must recompute to that root.
