# Interop proofs

Runnable demonstrations of GARL's compatibility claims — each one a small
stdlib-only script plus a mapping doc. If a claim can't be run, it isn't
made.

| Dir | Claim demonstrated | Run |
|---|---|---|
| [`x402/`](./x402/) | A GARL Action Receipt works as the `proofOfPayment` object for x402/ERC-8004 payment flows | `python3 x402/emit_receipt.py --merchant m --amount-usd 4.2 --offline` |
| [`erc8004/`](./erc8004/) | GARL serves ERC-8004 Identity/Reputation formats (read) and produces registry-shaped write payloads | `python3 erc8004/compat_demo.py <agent-uuid>` |
| [`ap2/`](./ap2/) | AP2 Intent/Cart Mandates map onto a capability-token attenuation chain (intent = parent, cart = narrowed child) | `python3 ap2/mandate_to_token.py ap2/sample_intent_mandate.json` |

All three run offline (build-and-print) without credentials; with
`GARL_API_KEY`/`GARL_AGENT_ID` set, the x402 and AP2 demos mint real tokens
and receipts against the live API.

Honest scope: these are integration patterns and format demos, not shipped
bridges — no on-chain ERC-8004 writes, no AP2 wire-protocol endpoint, no
x402 facilitator role. Specs: `protocol/spec/capability-token-v0.1.md` §12,
`protocol/spec/action-receipt-v0.1.md`.
