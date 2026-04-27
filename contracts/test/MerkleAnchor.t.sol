// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/MerkleAnchor.sol";

contract MerkleAnchorTest is Test {
    MerkleAnchor anchor;
    address owner = address(0xA11CE);
    address user = address(0xB0B);

    function setUp() public {
        vm.prank(owner);
        anchor = new MerkleAnchor();
    }

    // ─────────────────────────────────────────────
    // Constructor
    // ─────────────────────────────────────────────

    function test_constructor_sets_owner() public {
        assertEq(anchor.owner(), owner);
        assertEq(anchor.nextBatchId(), 1);
        assertEq(anchor.pendingOwner(), address(0));
    }

    // ─────────────────────────────────────────────
    // anchor()
    // ─────────────────────────────────────────────

    function test_owner_can_anchor() public {
        bytes32 root = keccak256("batch-1");
        vm.expectEmit(true, true, false, true);
        emit MerkleAnchor.Anchored(1, root, 42, block.timestamp);

        vm.prank(owner);
        uint256 batchId = anchor.anchor(root, 42);
        assertEq(batchId, 1);
        assertEq(anchor.roots(1), root);
        assertEq(anchor.receiptCounts(1), 42);
        assertEq(anchor.nextBatchId(), 2);
    }

    function test_non_owner_anchor_reverts() public {
        vm.prank(user);
        vm.expectRevert(MerkleAnchor.NotOwner.selector);
        anchor.anchor(keccak256("x"), 1);
    }

    function test_anchor_zero_root_reverts() public {
        vm.prank(owner);
        vm.expectRevert(MerkleAnchor.EmptyRoot.selector);
        anchor.anchor(bytes32(0), 1);
    }

    function test_anchor_zero_receipts_reverts() public {
        vm.prank(owner);
        vm.expectRevert(MerkleAnchor.ZeroReceipts.selector);
        anchor.anchor(keccak256("x"), 0);
    }

    function test_batch_ids_are_sequential() public {
        vm.startPrank(owner);
        uint256 id1 = anchor.anchor(keccak256("a"), 1);
        uint256 id2 = anchor.anchor(keccak256("b"), 1);
        uint256 id3 = anchor.anchor(keccak256("c"), 1);
        vm.stopPrank();
        assertEq(id1, 1);
        assertEq(id2, 2);
        assertEq(id3, 3);
    }

    // ─────────────────────────────────────────────
    // verifyProof()
    // ─────────────────────────────────────────────

    function test_verify_two_leaf_tree() public {
        // Build a 2-leaf SHA-256 Merkle tree off-chain and verify on-chain.
        bytes32 leafA = sha256(abi.encodePacked(bytes32(uint256(1))));
        bytes32 leafB = sha256(abi.encodePacked(bytes32(uint256(2))));
        bytes32 root = sha256(abi.encodePacked(leafA, leafB));

        vm.prank(owner);
        uint256 batchId = anchor.anchor(root, 2);

        // Proof for leafA: sibling is leafB, position right
        bytes32[] memory siblings = new bytes32[](1);
        bool[] memory positions = new bool[](1);
        siblings[0] = leafB;
        positions[0] = true;
        assertTrue(anchor.verifyProof(batchId, leafA, siblings, positions));

        // Proof for leafB: sibling is leafA, position left
        siblings[0] = leafA;
        positions[0] = false;
        assertTrue(anchor.verifyProof(batchId, leafB, siblings, positions));
    }

    function test_verify_rejects_tampered_leaf() public {
        bytes32 leafA = sha256(abi.encodePacked(bytes32(uint256(1))));
        bytes32 leafB = sha256(abi.encodePacked(bytes32(uint256(2))));
        bytes32 root = sha256(abi.encodePacked(leafA, leafB));
        vm.prank(owner);
        uint256 batchId = anchor.anchor(root, 2);

        bytes32[] memory siblings = new bytes32[](1);
        bool[] memory positions = new bool[](1);
        siblings[0] = leafB;
        positions[0] = true;
        bytes32 fakeLeaf = keccak256("forged");
        assertFalse(anchor.verifyProof(batchId, fakeLeaf, siblings, positions));
    }

    function test_verify_rejects_unknown_batch() public {
        bytes32[] memory siblings = new bytes32[](0);
        bool[] memory positions = new bool[](0);
        assertFalse(anchor.verifyProof(99, keccak256("x"), siblings, positions));
    }

    function test_verify_rejects_mismatched_array_lengths() public {
        bytes32 leaf = sha256(abi.encodePacked(bytes32(uint256(1))));
        vm.prank(owner);
        uint256 batchId = anchor.anchor(leaf, 1);
        bytes32[] memory siblings = new bytes32[](2);
        bool[] memory positions = new bool[](1);
        assertFalse(anchor.verifyProof(batchId, leaf, siblings, positions));
    }

    // ─────────────────────────────────────────────
    // Ownership
    // ─────────────────────────────────────────────

    function test_transfer_ownership_two_step() public {
        vm.prank(owner);
        anchor.transferOwnership(user);
        assertEq(anchor.pendingOwner(), user);
        assertEq(anchor.owner(), owner); // not yet transferred

        vm.prank(user);
        anchor.acceptOwnership();
        assertEq(anchor.owner(), user);
        assertEq(anchor.pendingOwner(), address(0));
    }

    function test_only_pending_can_accept() public {
        vm.prank(owner);
        anchor.transferOwnership(user);

        address other = address(0xCAFE);
        vm.prank(other);
        vm.expectRevert(MerkleAnchor.NotPendingOwner.selector);
        anchor.acceptOwnership();
    }

    function test_only_owner_can_initiate_transfer() public {
        vm.prank(user);
        vm.expectRevert(MerkleAnchor.NotOwner.selector);
        anchor.transferOwnership(user);
    }
}
