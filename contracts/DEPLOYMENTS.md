# MerkleAnchor Deployments

`MerkleAnchor.sol` anchors the Merkle roots of batched Action Receipts on-chain,
giving each receipt batch a tamper-evident, publicly verifiable timestamp. Only
the contract owner can `anchor()`; anyone can `verifyProof()` a receipt's
inclusion against an anchored root.

| Network | Chain ID | Address | Owner |
|---|---|---|---|
| Base mainnet | 8453 | [`0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`](https://basescan.org/address/0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2) | `0xD151d1da33D51C2BdA9525091213500d6E506891` |

**Source verified** (exact match): [Sourcify](https://repo.sourcify.dev/8453/0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2) ·
[Blockscout](https://base.blockscout.com/address/0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2). Anyone can read the deployed source and re-verify the bytecode.

## Operating the anchor

Anchoring normally runs unattended: the **Weekly Merkle Anchor** workflow
(`.github/workflows/anchor.yml`, Mondays 03:17 UTC) runs
`scripts/anchor_batch.py` end-to-end and fails loudly (auto-filed
`anchor-failure` issue) if anything breaks. Full runbook:
`docs/runbooks/anchoring.md`. Every batch is public at
[garl.ai/anchors](https://garl.ai/anchors) / `GET /api/v1/anchors`.

Manual recovery path — batches are built off-chain by
`backend/app/services/merkle_batch.py` (`build_pending_batch()` rolls up
unanchored receipts into a Merkle root, stored with `anchored_at = NULL`).
To anchor a batch on-chain by hand:

```bash
cd contracts
export PATH="$HOME/.foundry/bin:$PATH"
set -a; source ./.env.deploy; set +a   # DEPLOYER_PRIVATE_KEY (owner)

cast send 0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2 \
  "anchor(bytes32,uint256)" <merkle_root> <receipt_count> \
  --rpc-url base --private-key "$DEPLOYER_PRIVATE_KEY"
```

Then call `merkle_batch.record_anchor_tx(batch_id=..., chain_id=8453,
tx_hash=..., contract_address=..., onchain_batch_id=...)` so the DB row and
its receipts flip to `anchored_at = <now>`.

Ownership uses a two-step transfer (`transferOwnership` → `acceptOwnership`) so
the anchor authority can be rotated to a hardware wallet without downtime.
