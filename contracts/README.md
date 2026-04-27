# GARL Merkle Anchor — Foundry project

On-chain anchoring of GARL receipt batches on Base L2.

## What this is

A single-contract Foundry project. `MerkleAnchor.sol` accepts batched
Merkle roots from the GARL canonical registry's offline builder
(`backend/app/services/merkle_batch.py`) and emits an `Anchored` event.
Anyone with a receipt can later present a Merkle proof to verify
inclusion against the on-chain root.

## Why on-chain at all?

Off-chain receipts are already cryptographically signed (ECDSA-secp256k1
+ RFC 6979). The chain anchor adds:

- **Tamper-evident timestamp** — the `block.timestamp` at anchor time is
  hard to forge.
- **No-trust-in-issuer verification** — a receipt owner can prove
  inclusion against the chain without trusting the GARL registry. This
  matters most for compliance auditors and for the "what if GARL is
  compromised tomorrow" threat model.

## Cost

Base L2:
- Deploy: ~$0.50 once.
- Anchor: ~$0.001 per `anchor()` call.
- Weekly anchoring: ~$1-3/year ongoing.

5–20× cheaper than the strategy doc's earlier $50–100/year estimate.

## Setup

```bash
# Install Foundry if missing
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Run tests
cd contracts
forge install foundry-rs/forge-std --no-commit
forge test -vvv
```

## Deploy to Base Sepolia (testnet)

```bash
export DEPLOYER_PRIVATE_KEY=0x...   # never commit; use 1Password / GitHub Actions secret
forge script script/Deploy.s.sol:DeployScript \
  --rpc-url https://sepolia.base.org \
  --private-key $DEPLOYER_PRIVATE_KEY \
  --broadcast
```

## Deploy to Base Mainnet

```bash
forge script script/Deploy.s.sol:DeployScript \
  --rpc-url https://mainnet.base.org \
  --private-key $DEPLOYER_PRIVATE_KEY \
  --broadcast
```

## Wire into the backend

After deploy, set:

```
GARL_MERKLE_ANCHOR_CONTRACT=0x<deployed_address>
GARL_MERKLE_ANCHOR_CHAIN_ID=84532   # Base Sepolia
# or 8453 for Base Mainnet
```

The backend's weekly cron will:

1. `build_pending_batch()` — roll up unanchored receipts and compute a
   Merkle root.
2. Operator (or a separate service with a wallet) calls `anchor(root,
   receiptCount)` on the deployed contract.
3. `record_anchor_tx(batch_id, chain_id, tx_hash, contract_address)` —
   marks the batch + receipts as anchored.

## Trust model

- Single-owner. The owner is the wallet that called the constructor.
- Two-step ownership transfer (`transferOwnership` + `acceptOwnership`)
  to avoid sending the role to a wrong address by accident.
- Self-hosted GARL deployments deploy their own copy. The canonical
  registry's address is published in
  `https://api.garl.ai/.well-known/garl-keys.json` once it lands.

## License

Apache 2.0.
