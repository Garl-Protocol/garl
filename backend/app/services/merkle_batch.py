"""
Merkle batch builder.

Periodically rolls up the receipts that haven't been on-chain anchored yet,
computes a Merkle root over their `output_hash` values, and stores the
batch row + back-references. The actual on-chain transaction (Base L2,
`MerkleAnchor.sol`) is outside this module — broadcasting needs a wallet
key and a CLI/Foundry script that the operator runs.

Design:
  - Stable ordering: receipts sorted by (created_at ASC, receipt_id ASC).
  - Leaf  = SHA-256(0x00 || output_hash bytes); node = SHA-256(0x01 || L || R).
    The 0x00/0x01 domain separation is the RFC-6962 idea and is what prevents
    second-preimage / type-confusion: an internal node value (0x01-prefixed)
    can never be re-presented as a leaf (0x00-prefixed). This must stay
    byte-identical to MerkleAnchor.verifyProof on-chain.
  - Odd nodes are promoted unchanged (NOT duplicated), which avoids the
    duplicated-last-leaf ambiguity (Bitcoin CVE-2012-2459).
  - Caveat: we do NOT bind the tree size into the hashing, so unlike full
    RFC 6962 the root is not a unique commitment to the tree *shape* — e.g. a
    3-leaf tree and a 2-node tree whose first node already equals H(0x01||a||b)
    can share a root. This is not exploitable to forge a receipt's inclusion
    (leaves are domain-separated, so a prover cannot substitute an internal
    node for a leaf), but the root should not be relied on as a commitment to
    the exact leaf count.
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


_LEAF_PREFIX = b"\x00"   # RFC 6962 domain separation: leaf  = H(0x00 || data)
_NODE_PREFIX = b"\x01"   #                              node  = H(0x01 || left || right)


def _hash_node(left: bytes, right: bytes) -> str:
    """Internal Merkle node = SHA-256(0x01 || left || right). The 0x01 prefix
    domain-separates internal nodes from leaves so an internal node value can
    never be presented as a valid leaf (second-preimage / type-confusion)."""
    return _sha256_hex(_NODE_PREFIX + left + right)


def _leaf(output_hash_hex: str) -> str:
    """Leaf = SHA-256(0x00 || output_hash bytes). The 0x00 prefix domain-
    separates leaves from internal nodes (RFC 6962). MUST stay byte-identical
    to the on-chain MerkleAnchor.verifyProof hashing."""
    return _sha256_hex(_LEAF_PREFIX + bytes.fromhex(output_hash_hex))


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
            next_layer.append(_hash_node(bytes.fromhex(layer[i]), bytes.fromhex(layer[i + 1])))
            i += 2
        if i < len(layer):
            # Odd node: promote unchanged (duplicating the last leaf instead
            # would reintroduce the Bitcoin CVE-2012-2459 ambiguity). Note this
            # does not bind tree size into the root — see the module docstring.
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
            next_layer.append(_hash_node(bytes.fromhex(layer[i]), bytes.fromhex(layer[i + 1])))
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
            cursor = _hash_node(bytes.fromhex(cursor), bytes.fromhex(sibling))
        else:
            cursor = _hash_node(bytes.fromhex(sibling), bytes.fromhex(cursor))
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
    onchain_batch_id: int | None = None,
) -> dict:
    """Operator-driven: once the Base tx confirms, mark the batch anchored.
    The receipts in the batch flip their anchored_at via a follow-up update.

    `onchain_batch_id` is the batchId the contract assigned to anchor() — it
    is what verifyProof expects. Persist it rather than assuming it equals the
    DB batch_id (which only holds if every batch anchors in order)."""
    sb = _get_supabase()
    now_iso = _now_iso()
    update = {
        "anchored_at": now_iso,
        "chain_id": chain_id,
        "tx_hash": tx_hash,
        "contract_address": contract_address,
    }
    if onchain_batch_id is not None:
        update["onchain_batch_id"] = onchain_batch_id
    sb.table("merkle_batches").update(update).eq("batch_id", batch_id).execute()

    sb.table("receipts").update({"anchored_at": now_iso}).eq("merkle_batch_id", batch_id).execute()
    try:
        from app.core.analytics import capture as _ph
        _ph("onchain_anchor_recorded", None, {"chain_id": chain_id, "batch_id": batch_id})
    except Exception:
        pass

    res = sb.table("merkle_batches").select("*").eq("batch_id", batch_id).limit(1).execute()
    return res.data[0] if res.data else {}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _batch_ordered_members(sb, batch_id: int) -> list[dict]:
    """Receipts in a batch in the SAME order build_pending_batch used to build
    the tree (created_at ASC, receipt_id ASC). Single source of truth for the
    leaf ordering so the proof builder can never drift from the builder."""
    return (
        sb.table("receipts")
        .select("receipt_id, output_hash, created_at")
        .eq("merkle_batch_id", batch_id)
        .order("created_at")
        .order("receipt_id")
        .execute()
        .data
        or []
    )


def build_inclusion_proof(receipt_id_or_hash: str) -> dict | None:
    """Build an on-chain-verifiable Merkle inclusion proof for a receipt.

    Returns None if the receipt is unknown, not yet batched, or its batch is
    not yet anchored on-chain. The returned dict carries everything needed to
    call MerkleAnchor.verifyProof(batchId, leaf, proofSiblings, proofPositions)
    on Base, plus a human-readable proof form. The proof is re-verified
    locally before return.
    """
    sb = _get_supabase()
    rid = (receipt_id_or_hash or "").strip()
    col = (
        "output_hash"
        if len(rid) == 64 and all(c in "0123456789abcdef" for c in rid.lower())
        else "receipt_id"
    )
    val = rid.lower() if col == "output_hash" else rid

    rec = (
        sb.table("receipts")
        .select("receipt_id, output_hash, merkle_batch_id, anchored_at")
        .eq(col, val)
        .limit(1)
        .execute()
        .data
    )
    if not rec:
        return None
    rec = rec[0]
    batch_id = rec.get("merkle_batch_id")
    if batch_id is None:
        return None  # pending — not yet batched

    batch = (
        sb.table("merkle_batches")
        .select("batch_id, onchain_batch_id, root, chain_id, tx_hash, contract_address, anchored_at, receipt_count")
        .eq("batch_id", batch_id)
        .limit(1)
        .execute()
        .data
    )
    if not batch or not batch[0].get("tx_hash") or not batch[0].get("anchored_at"):
        return None  # not anchored on-chain yet
    batch = batch[0]

    members = _batch_ordered_members(sb, batch_id)
    leaves = [_leaf(r["output_hash"]) for r in members]
    target_receipt_id = rec["receipt_id"]
    try:
        target_index = next(i for i, r in enumerate(members) if r["receipt_id"] == target_receipt_id)
    except StopIteration:
        return None

    leaf = leaves[target_index]
    proof = merkle_proof(leaves, target_index)
    if not verify_merkle_proof(leaf, proof, batch["root"]):
        # The off-chain proof must reconstruct the anchored root; if not, the
        # leaf ordering drifted — refuse to serve a proof that would fail
        # on-chain rather than emit a wrong one.
        return None

    # The batchId verifyProof expects: the on-chain id if recorded, else the
    # DB id (genesis: 1 == 1, verified on Base).
    onchain_batch_id = batch.get("onchain_batch_id") or batch["batch_id"]
    siblings = ["0x" + step["sibling"] for step in proof]
    positions = [step["position"] == "right" for step in proof]  # right->true (MerkleAnchor.sol)

    return {
        "anchored": True,
        "chain": "base-mainnet" if batch.get("chain_id") == 8453 else f"chain-{batch.get('chain_id')}",
        "chain_id": batch.get("chain_id"),
        "contract_address": batch.get("contract_address"),
        "tx_hash": batch.get("tx_hash"),
        "anchored_at": batch.get("anchored_at"),
        "merkle_root": batch["root"],
        "receipt_count": batch.get("receipt_count"),
        "leaf": leaf,
        "leaf_index": target_index,
        "proof": proof,  # [{"sibling","position"}] — human/debug form
        "verify_proof_args": {  # ready-to-use on-chain calldata
            "batchId": onchain_batch_id,
            "leaf": "0x" + leaf,
            "proofSiblings": siblings,
            "proofPositions": positions,
        },
    }
