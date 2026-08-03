#!/usr/bin/env python3
"""Roll up unanchored Action Receipts into a Merkle batch and anchor its root
on Base via the MerkleAnchor contract.

Operator-/cron-driven. Reads config from env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   — DB access (build + record)
  GARL_MERKLE_ANCHOR_CONTRACT               — deployed MerkleAnchor address
  GARL_MERKLE_ANCHOR_CHAIN_ID               — 8453 (Base mainnet)
  BASE_RPC_URL                              — e.g. https://mainnet.base.org
  DEPLOYER_PRIVATE_KEY                      — contract owner key (anchor authority)

Broadcasting uses `cast` (Foundry), which must be on PATH. The key is passed to
cast via env and never printed. Exits 0 (no-op) when there is nothing to anchor.

Idempotency: build_pending_batch() only rolls up receipts with
merkle_batch_id IS NULL, so a re-run won't double-batch. If a broadcast fails
after a batch row was created, that batch stays anchored_at=NULL; re-anchoring
it is a manual step (see contracts/DEPLOYMENTS.md) — this script intentionally
does not retry partial batches to avoid double-anchoring.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

# Make the FastAPI backend importable so we reuse the exact batch logic that
# the contract's verifyProof was built against (no hashing divergence).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.services.merkle_batch import build_pending_batch, record_anchor_tx  # noqa: E402


def _require(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"Missing required env var: {name}")
    return v


def main() -> int:
    contract = _require("GARL_MERKLE_ANCHOR_CONTRACT")
    chain_id = int(_require("GARL_MERKLE_ANCHOR_CHAIN_ID"))
    rpc = _require("BASE_RPC_URL")
    key = _require("DEPLOYER_PRIVATE_KEY")
    if not key.startswith("0x"):
        key = "0x" + key

    batch = build_pending_batch()
    if not batch:
        print("Nothing to anchor — no unanchored receipts.")
        return 0

    batch_id = batch["batch_id"]
    root = batch["root"]
    count = batch["receipt_count"]
    print(f"Built batch {batch_id}: root={root} receipts={count}. Broadcasting anchor()…")

    cmd = [
        "cast", "send", contract,
        "anchor(bytes32,uint256)", "0x" + root, str(count),
        "--rpc-url", rpc, "--private-key", key, "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Never echo the command (it contains the key); surface stderr only.
        sys.exit(f"cast send failed (rc={proc.returncode}): {proc.stderr.strip()[:500]}")

    receipt = json.loads(proc.stdout)
    tx_hash = receipt.get("transactionHash")
    status = receipt.get("status")
    if status not in ("0x1", "1", 1):
        sys.exit(f"anchor tx reverted: {tx_hash} status={status}")

    # Capture the batchId the contract actually assigned, from the Anchored
    # event in THIS tx's logs — race-free by construction. (Reading
    # nextBatchId()-1 after the send, as this script originally did, can
    # return a stale value from a lagging RPC node: batch 3 was recorded as
    # onchain id 2 that way on 2026-08-03, which would have made its proofs
    # verify against the wrong root.)
    onchain_batch_id = None
    for log_entry in receipt.get("logs", []):
        topics = log_entry.get("topics") or []
        # Anchored(uint256 indexed batchId, bytes32 indexed root, ...):
        # topics[1] = batchId, topics[2] = root. Identify the right event by
        # matching our known root rather than the (keccak) event selector.
        if len(topics) >= 3 and topics[2].lower().removeprefix("0x") == root.lower():
            try:
                onchain_batch_id = int(topics[1], 16)
            except ValueError:
                onchain_batch_id = None
            break
    if onchain_batch_id is None:
        # Fallback: nextBatchId-1 via the same RPC (may lag; log loudly).
        nb = subprocess.run(
            ["cast", "call", contract, "nextBatchId()(uint256)", "--rpc-url", rpc],
            capture_output=True, text=True,
        )
        if nb.returncode == 0:
            try:
                onchain_batch_id = int(nb.stdout.strip().split()[0]) - 1
                print(f"WARNING: batchId from nextBatchId fallback ({onchain_batch_id}) — verify against the Anchored event on Basescan.")
            except (ValueError, IndexError):
                onchain_batch_id = None

    record_anchor_tx(
        batch_id=batch_id, chain_id=chain_id, tx_hash=tx_hash,
        contract_address=contract, onchain_batch_id=onchain_batch_id,
    )
    print(f"Anchored DB batch {batch_id} (on-chain {onchain_batch_id}) in tx {tx_hash} (chain {chain_id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
