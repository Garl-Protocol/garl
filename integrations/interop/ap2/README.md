# AP2 ↔ GARL — Mandates as capability tokens

[AP2 (Agent Payments Protocol)](https://github.com/google-agentic-commerce/AP2)
expresses user authority through **Intent Mandates** ("buy me running shoes
under $120") and **Cart Mandates** (a specific cart the user approved). A GARL
**capability token** expresses the same thing as a signed, attenuable,
revocable credential — and every resulting action receipt links back to it.

**Status: runnable mapping demo.** This converts mandate JSON into GARL
capability-token issuance requests; it is not a shipped AP2 bridge and does
not speak the AP2 wire protocol.

## Mapping

| AP2 Mandate field | Capability token claim |
|---|---|
| Intent: natural-language intent + constraints | `caveats[]` (recorded verbatim, subset-preserved down the delegation chain) |
| Intent: price ceiling | `spend_limit_usd` |
| Intent: allowed merchants | `merchant_allowlist` |
| Intent: expiry / shopping window | `exp` (child tokens can only shorten) |
| Cart: user-approved cart for merchant M, total T | child token attenuated to `spend_limit_usd = T`, `merchant_allowlist = [M]`, `scope = payment:M` |
| Human presence / approval | `human_delegate` + Capability Gate `requires_human` escalation |

The Intent→Cart relationship maps to GARL's parent→child attenuation: the
cart token is a **child** of the intent token, so the chain proves the
narrower cart authority was derived from the broader user intent — enforced
at issue AND re-checked link-by-link at verification
(`protocol/spec/capability-token-v0.1.md` §5, §7).

## Run it

```bash
python3 mandate_to_token.py sample_intent_mandate.json          # offline: prints issuance requests
GARL_API_KEY=... GARL_AGENT_ID=... python3 mandate_to_token.py sample_intent_mandate.json --issue
```

`--issue` actually mints the intent token and the attenuated cart token via
`POST /api/v1/capability/issue` and prints both `token_hash`es; the payment
receipt then references the cart token, closing the loop:

```
user intent ──▶ intent token (limit $120, [nike.com, adidas.com], 24h)
                    └─▶ cart token (limit $89.99, [nike.com], 15m, parent=intent)
                            └─▶ payment Action Receipt (capability_request.token_hash)
```
