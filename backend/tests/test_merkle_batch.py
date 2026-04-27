"""Merkle batch builder + proof verifier tests.

Pure crypto path — no DB. The DB-backed path (build_pending_batch,
record_anchor_tx) is exercised via the route integration tests.
"""

from __future__ import annotations

import hashlib

import pytest

from app.services.merkle_batch import (
    EMPTY_HASH,
    compute_merkle_root,
    merkle_proof,
    verify_merkle_proof,
)


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _leaf(output_hash: str) -> str:
    return _h(bytes.fromhex(output_hash))


# ──────────────────────────────────────────────────────────────────────
# Root computation
# ──────────────────────────────────────────────────────────────────────

def test_empty_input_returns_sentinel_root():
    assert compute_merkle_root([]) == EMPTY_HASH


def test_single_leaf_returns_leaf_unchanged():
    leaf = _leaf("ab" * 32)
    assert compute_merkle_root([leaf]) == leaf


def test_two_leaves_pair_hash():
    a = _leaf("ab" * 32)
    b = _leaf("cd" * 32)
    expected = _h(bytes.fromhex(a) + bytes.fromhex(b))
    assert compute_merkle_root([a, b]) == expected


def test_three_leaves_promote_odd():
    """Bitcoin-style would duplicate the last leaf; we promote it untouched
    to prevent second-preimage attacks. Test asserts our non-duplicating
    semantics."""
    a, b, c = (_leaf(f"{i:064x}") for i in (1, 2, 3))
    pair_ab = _h(bytes.fromhex(a) + bytes.fromhex(b))
    # c is promoted to layer 2 unchanged
    expected = _h(bytes.fromhex(pair_ab) + bytes.fromhex(c))
    assert compute_merkle_root([a, b, c]) == expected


def test_root_changes_when_leaf_changes():
    leaves = [_leaf(f"{i:064x}") for i in range(8)]
    root1 = compute_merkle_root(leaves)
    leaves[3] = _leaf(f"{99:064x}")
    root2 = compute_merkle_root(leaves)
    assert root1 != root2


def test_root_deterministic_for_same_input():
    leaves = [_leaf(f"{i:064x}") for i in range(16)]
    a = compute_merkle_root(leaves)
    b = compute_merkle_root(leaves)
    assert a == b


def test_root_order_dependent():
    leaves = [_leaf(f"{i:064x}") for i in range(4)]
    root_a = compute_merkle_root(leaves)
    root_b = compute_merkle_root(list(reversed(leaves)))
    assert root_a != root_b  # ordering matters; caller MUST sort canonically


# ──────────────────────────────────────────────────────────────────────
# Inclusion proofs
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,target", [
    (1, 0),
    (2, 0), (2, 1),
    (4, 0), (4, 1), (4, 2), (4, 3),
    (5, 0), (5, 4),
    (7, 3), (7, 6),
    (16, 0), (16, 7), (16, 15),
])
def test_proof_verifies_for_arbitrary_size_and_index(n, target):
    leaves = [_leaf(f"{i:064x}") for i in range(n)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, target)
    assert verify_merkle_proof(leaves[target], proof, root)


def test_proof_fails_for_tampered_leaf():
    leaves = [_leaf(f"{i:064x}") for i in range(8)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, 3)
    bad_leaf = _leaf(f"{999:064x}")
    assert not verify_merkle_proof(bad_leaf, proof, root)


def test_proof_fails_for_tampered_sibling():
    leaves = [_leaf(f"{i:064x}") for i in range(8)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, 3)
    proof[0]["sibling"] = "0" * 64
    assert not verify_merkle_proof(leaves[3], proof, root)


def test_proof_fails_for_swapped_position():
    leaves = [_leaf(f"{i:064x}") for i in range(4)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, 1)
    proof[0]["position"] = "left" if proof[0]["position"] == "right" else "right"
    assert not verify_merkle_proof(leaves[1], proof, root)


def test_proof_for_index_zero_in_two_leaf_tree():
    """Edge case — left-most leaf in the smallest non-trivial tree."""
    leaves = [_leaf("ab" * 32), _leaf("cd" * 32)]
    root = compute_merkle_root(leaves)
    proof = merkle_proof(leaves, 0)
    assert len(proof) == 1
    assert proof[0]["position"] == "right"
    assert proof[0]["sibling"] == leaves[1]
    assert verify_merkle_proof(leaves[0], proof, root)


def test_out_of_range_index_raises():
    leaves = [_leaf(f"{i:064x}") for i in range(4)]
    with pytest.raises(IndexError):
        merkle_proof(leaves, 4)
    with pytest.raises(IndexError):
        merkle_proof(leaves, -1)
