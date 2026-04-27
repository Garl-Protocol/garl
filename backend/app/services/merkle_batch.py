"""
Merkle batch builder.

Periodically rolls up the receipts that haven't been on-chain anchored yet,
computes a Merkle root over their `output_hash` values, and stores the
batch row + back-references. The actual on-chain transaction (Base L2,
`MerkleAnchor.sol`) is outside this module — broadcasting needs a wallet
key and a CLI/Foundry script that the operator runs.

Design:
  - Stable ordering: receipts sorted by (created_at ASC, receipt_id ASC).
  - Merkle leaves: SHA-256 of `output_hash` bytes (already 32 bytes, but
    we re-hash to canonicalize against future leaf encoding changes).
  - Pair hashing: parent = SHA-256(left || right). Odd nodes promoted up
    (Bitcoin-style, NOT duplicated like some implementations) to avoid
    second-preimage attacks where a duplicated leaf collides with a
    non-leaf. This matches OpenZeppelin's MerkleProof verification.
  - Empty batches are not built (the contract requires receipt_count > 0).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

EMPTY_HASH = "0" * 64


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _leaf(output_hash_hex: str) -> str:
    """Leaf = SHA-256 of the output_hash bytes. The double-hash here
    canonicalizes the leaf format so future receipt fields can join the
    leaf without breaking older proofs."""
    return _sha256_hex(bytes.fromhex(output_hash_hex))


def compute_merkle_root(leaves: list[str]) -> str:
    """Compute Merkle root of leaves (each a 64-hex string).

    Returns the root as 64-hex. Empty input → all-zeros sentinel root,
    which the contract refuses to anchor (receipt_count > 0).
    """
    if not leaves:
        return EMPTY_HASH

    layer = list(leaves)
    while len(layer) > 1:
        next_layer: list[str] = []
        i = 0
        while i + 1 < len(layer):
            left = bytes.fromhex(layer[i])
            right = bytes.fromhex(layer[i + 1])
            next_layer.append(_sha256_hex(left + right))
            i += 2
        if i < len(layer):
            # Odd node: promote unchanged. Bitcoin-style would duplicate;
            # we choose promotion to avoid the second-preimage attack class.
            next_layer.append(layer[i])
        layer = next_layer
    return layer[0]


def merkle_proof(leaves: list[str], target_index: int) -> list[dict]:
    """Inclusion proof for leaves[target_index].
    Each step is {"sibling": "<hex>", "position": "left" | "right"}."""
    if target_index < 0 or target_index >= len(leaves):
        raise IndexError("target_index out of range")
    proof: list[dict] = []
    layer = list(leaves)
    idx = target_index
    while len(layer) > 1:
        next_layer: list[str] = []
        i = 0
        while i + 1 < len(layer):
            if i == idx or i + 1 == idx:
                if i == idx:
                    proof.append({"sibling": layer[i + 1], "position": "right"})
                else:
                    proof.append({"sibling": layer[i], "position": "left"})
            next_layer.append(_sha256_hex(bytes.fromhex(layer[i]) + bytes.fromhex(layer[i + 1])))
            i += 2
        if i < len(layer):
            # Promoted odd node — no sibling at this step.
            if i == idx:
                pass
            next_layer.append(layer[i])
        idx = idx // 2
        layer = next_layer
    return proof


def verify_merkle_proof(leaf: str, proof: list[dict], root: str) -> bool:
    """Walk a Merkle proof and check the final node matches the root."""
    cursor = leaf
    for step in proof:
        sibling = step["sibling"]
        if step["position"] == "right":
            cursor = _sha256_hex(bytes.fromhex(cursor) + bytes.fromhex(sibling))
        else:
            cursor = _sha256_hex(bytes.fromhex(sibling) + bytes.fromhex(cursor))
    return cursor == root


def build_pending_batch(*, max_size: int = 1000) -> dict | None:
    """Build a Merkle batch from receipts that haven't been anchored yet.

    Returns the new merkle_batches row, or None if no pending receipts.

    Side effects:
      - Inserts a row into merkle_batches with anchored_at=NULL.
      - Updates the included receipts to point at the new batch_id (their
        anchored_at stays NULL until the on-chain tx confirms).

    The operator separately runs `forge script ... --broadcast` to anchor
    the root on Base; on-chain confirmation triggers a follow-up call to
    record_anchor_tx() which fills in tx_hash + anchored_at.
    """
    sb = _get_supabase()

    pending = (
        sb.table("receipts")
        .select("receipt_id, output_hash, created_at")
        .is_("merkle_batch_id", "null")
        .order("created_at")
        .order("receipt_id")
        .limit(max_size)
        .execute()
        .data
        or []
    )
    if not pending:
        return None

    leaves = [_leaf(r["output_hash"]) for r in pending]
    root = compute_merkle_root(leaves)

    batch_insert = (
        sb.table("merkle_batches")
        .insert({"root": root, "receipt_count": len(pending)})
        .execute()
    )
    batch_row = batch_insert.data[0] if batch_insert.data else None
    if not batch_row:
        raise RuntimeError("Failed to create merkle_batches row")
    batch_id = batch_row["batch_id"]

    receipt_ids = [r["receipt_id"] for r in pending]
    sb.table("receipts").update({"merkle_batch_id": batch_id}).in_("receipt_id", receipt_ids).execute()

    return batch_row


def record_anchor_tx(
    *,
    batch_id: int,
    chain_id: int,
    tx_hash: str,
    contract_address: str,
) -> dict:
    """Operator-driven: once the Base tx confirms, mark the batch anchored.
    The receipts in the batch flip their anchored_at via a follow-up update."""
    sb = _get_supabase()
    now_iso = _now_iso()
    sb.table("merkle_batches").update(
        {
            "anchored_at": now_iso,
            "chain_id": chain_id,
            "tx_hash": tx_hash,
            "contract_address": contract_address,
        }
    ).eq("batch_id", batch_id).execute()

    sb.table("receipts").update({"anchored_at": now_iso}).eq("merkle_batch_id", batch_id).execute()

    res = sb.table("merkle_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    return res.data[0] if res.data else {}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
