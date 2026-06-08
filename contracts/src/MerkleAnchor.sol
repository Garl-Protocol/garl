// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/**
 * @title MerkleAnchor
 * @notice Periodic on-chain commitment of GARL receipt batches.
 *
 * The canonical GARL registry rolls up unanchored receipts into Merkle
 * batches off-chain (see `backend/app/services/merkle_batch.py`). Once a
 * batch is built, the operator broadcasts a single `anchor()` tx that
 * commits the root + its monotonically-increasing batch_id. Anyone with
 * a receipt can later present a Merkle proof to verify inclusion against
 * the on-chain root — without trusting the registry.
 *
 * Cost: ~22k gas per anchor on Base L2. With weekly anchoring that's
 * ~$1-3/year at typical Base fees.
 *
 * Trust model:
 *   - The contract is single-owner (the GARL canonical registry's
 *     deployer). Self-hosted GARL instances deploy their own copy.
 *   - The owner can transfer the role; ownership is never mutable in any
 *     way that lets a third party append batches under another
 *     deployment's brand.
 *
 * Verification:
 *   - Off-chain: hand the receipt's Merkle proof to anyone with this
 *     contract's address; they call `verifyProof(batchId, leaf, proof)`
 *     view to confirm.
 */
contract MerkleAnchor {
    // ─────────────────────────────────────────────
    // Events
    // ─────────────────────────────────────────────

    /// @notice Emitted on every successful batch anchor.
    /// @param batchId   Sequential id assigned by the contract.
    /// @param root      Merkle root over receipt leaves (32 bytes).
    /// @param receiptCount Number of receipts in this batch.
    /// @param timestamp Block timestamp at anchor.
    event Anchored(
        uint256 indexed batchId,
        bytes32 indexed root,
        uint256 receiptCount,
        uint256 timestamp
    );

    event OwnerTransferStarted(address indexed previousOwner, address indexed pendingOwner);
    event OwnerTransferCompleted(address indexed previousOwner, address indexed newOwner);

    // ─────────────────────────────────────────────
    // State
    // ─────────────────────────────────────────────

    address public owner;
    address public pendingOwner;

    /// @notice batchId => Merkle root. Roots are append-only; once written
    /// they cannot be cleared or overwritten.
    mapping(uint256 => bytes32) public roots;

    /// @notice batchId => receiptCount. Useful for proof verifiers that
    /// want to bound the maximum proof depth (log2(receiptCount)).
    mapping(uint256 => uint256) public receiptCounts;

    /// @notice Next batchId to be assigned. Increments by 1 on each anchor.
    uint256 public nextBatchId = 1;

    // ─────────────────────────────────────────────
    // Errors
    // ─────────────────────────────────────────────

    error NotOwner();
    error NotPendingOwner();
    error EmptyRoot();
    error ZeroReceipts();
    error AlreadyAnchored();

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    constructor() {
        owner = msg.sender;
    }

    // ─────────────────────────────────────────────
    // Owner-only: anchor a batch
    // ─────────────────────────────────────────────

    /// @notice Anchor a new batch root on chain.
    /// @param root Merkle root over the receipt leaves.
    /// @param receiptCount Number of receipts in the batch (must be > 0).
    /// @return batchId The freshly-assigned batch id.
    function anchor(bytes32 root, uint256 receiptCount) external returns (uint256) {
        if (msg.sender != owner) revert NotOwner();
        if (root == bytes32(0)) revert EmptyRoot();
        if (receiptCount == 0) revert ZeroReceipts();

        uint256 batchId = nextBatchId;
        if (roots[batchId] != bytes32(0)) revert AlreadyAnchored(); // defensive

        roots[batchId] = root;
        receiptCounts[batchId] = receiptCount;
        nextBatchId = batchId + 1;

        emit Anchored(batchId, root, receiptCount, block.timestamp);
        return batchId;
    }

    // ─────────────────────────────────────────────
    // View: verify Merkle proof against an anchored root
    // ─────────────────────────────────────────────

    /// @notice Verify that `leaf` is included in batch `batchId`.
    /// @dev Hash function: SHA-256 (matches the off-chain builder).
    /// @param batchId The batch to verify against.
    /// @param leaf The Merkle leaf — sha256(receipt.output_hash bytes).
    /// @param proofSiblings Inclusion path sibling hashes, leaf→root order.
    /// @param proofPositions Per-level sibling position: false = sibling on
    ///              the left (parent = sha256(sibling || node)), true =
    ///              sibling on the right (parent = sha256(node || sibling)).
    ///              Must be the same length as `proofSiblings`.
    function verifyProof(
        uint256 batchId,
        bytes32 leaf,
        bytes32[] calldata proofSiblings,
        bool[] calldata proofPositions
    ) external view returns (bool) {
        bytes32 root = roots[batchId];
        if (root == bytes32(0)) return false;
        if (proofSiblings.length != proofPositions.length) return false;

        bytes32 cursor = leaf;
        for (uint256 i = 0; i < proofSiblings.length; i++) {
            if (proofPositions[i]) {
                // sibling on the right
                cursor = sha256(abi.encodePacked(cursor, proofSiblings[i]));
            } else {
                // sibling on the left
                cursor = sha256(abi.encodePacked(proofSiblings[i], cursor));
            }
        }
        return cursor == root;
    }

    // ─────────────────────────────────────────────
    // Two-step ownership transfer (safer than push-only)
    // ─────────────────────────────────────────────

    function transferOwnership(address newOwner) external {
        if (msg.sender != owner) revert NotOwner();
        pendingOwner = newOwner;
        emit OwnerTransferStarted(owner, newOwner);
    }

    function acceptOwnership() external {
        if (msg.sender != pendingOwner) revert NotPendingOwner();
        address prev = owner;
        owner = pendingOwner;
        pendingOwner = address(0);
        emit OwnerTransferCompleted(prev, owner);
    }
}
