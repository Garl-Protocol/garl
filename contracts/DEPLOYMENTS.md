# MerkleAnchor Deployments

`MerkleAnchor.sol` anchors the Merkle roots of batched Action Receipts on-chain,
giving each receipt batch a tamper-evident, publicly verifiable timestamp. Only
the contract owner can `anchor()`; anyone can `verifyProof()` a receipt's
inclusion against an anchored root.

| Network | Chain ID | Address | Owner |
|---|---|---|---|
| Base mainnet | 8453 | [`0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17`](https://basescan.org/address/0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17) | `0xD151d1da33D51C2BdA9525091213500d6E506891` |

**Source verified** (exact match): [Sourcify](https://repo.sourcify.dev/8453/0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17) ·
[Blockscout](https://base.blockscout.com/address/0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17). Anyone can read the deployed source and re-verify the bytecode.

## Operating the anchor

Batches are built off-chain by `backend/app/services/merkle_batch.py`
(`build_batch()` rolls up unanchored receipts into a Merkle root, stored with
`anchored_at = NULL`). To anchor a batch on-chain:

```bash
cd contracts
export PATH="$HOME/.foundry/bin:$PATH"
set -a; source ./.env.deploy; set +a   # DEPLOYER_PRIVATE_KEY (owner)

cast send 0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17 \
  "anchor(bytes32,uint256)" <merkle_root> <receipt_count> \
  --rpc-url base --private-key "$DEPLOYER_PRIVATE_KEY"
```

Then call `merkle_batch.record_anchor_tx(batch_id, tx_hash)` so the DB row and
its receipts flip to `anchored_at = <now>`.

Ownership uses a two-step transfer (`transferOwnership` → `acceptOwnership`) so
the anchor authority can be rotated to a hardware wallet without downtime.
