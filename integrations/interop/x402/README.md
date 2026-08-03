# x402 ↔ GARL — a receipt as `proofOfPayment`

[x402](https://www.x402.org/) settles machine-to-machine payments over HTTP 402;
[ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) validation records can
reference a `proofOfPayment` object. This example emits a **GARL Action
Receipt** for an x402 settlement and uses the receipt as that proof object:
a signed, content-addressed, Merkle-anchored record of *who paid, under which
capability limits, when* — independently verifiable offline.

**Status: runnable demo + mapping doc.** This is a working integration
pattern, not a certified x402 facilitator component.

## Flow

```
buyer agent ──402──▶ seller resource
     │  settles payment (x402 rails)
     ▼
POST /api/v1/receipts          protocol: "x402", action_type: "payment"
     │                         capability_token_hash: <the token that allowed it>
     ▼
signed Action Receipt  ──────▶ proofOfPayment: {
  (anchored weekly on Base)      "type": "garl/action-receipt/v0.1",
                                 "uri":  "https://api.garl.ai/api/v1/receipts/<output_hash>/cert.json",
                                 "hash": "<output_hash>",
                                 "proof_uri": "https://api.garl.ai/api/v1/receipts/<id>/proof"
                               }
```

Why this pairing works: x402 proves *a payment cleared*; the GARL receipt
adds *the authority context* — the capability token (spend limit, merchant
allowlist) the buyer was operating under, bound into the signed envelope via
`capability_request.token_hash`.

## Run it

```bash
export GARL_API_KEY=...      # your agent's key (garl.ai/connect)
export GARL_AGENT_ID=...     # your agent uuid
python3 emit_receipt.py --merchant api.example-seller.com --amount-usd 4.20
```

Without credentials it runs in `--offline` mode: builds the envelope +
`proofOfPayment` object locally and prints them without submitting.

`emit_receipt.py` does three things:
1. (optional) issues a scoped capability token
   (`payment:<merchant>`, `spend_limit_usd`, `merchant_allowlist=[merchant]`);
2. submits the payment Action Receipt referencing that token
   (keyed input hash by default — see `docs/compliance/edpb.md`);
3. prints the `proofOfPayment` JSON block to embed in an ERC-8004
   validation record or x402 settlement metadata.

Verify the result without trusting GARL: fetch the `cert.json`, check the
ECDSA signature against [`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json),
and after the weekly anchor check the Merkle proof against the on-chain root
([garl.ai/anchors](https://garl.ai/anchors)).
