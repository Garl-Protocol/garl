# ERC-8004 ↔ GARL — registry format compatibility, demonstrated

[ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) defines Identity,
Reputation, and Validation registries for on-chain agents. GARL serves agent
metadata and feedback in ERC-8004's off-chain formats. This demo makes the
"format-compatible" claim runnable instead of rhetorical.

**Status: read/write format demo against the live API.** Off-chain formats
only — GARL does not write to ERC-8004 on-chain registries (that bridge is a
separate future integration; the current endpoints are deprecated in favor
of it with a 2027-04-15 removal date, see `docs/deprecations.md`).

## Read side

```bash
python3 compat_demo.py <agent-uuid>          # any agent from garl.ai/registry
```

The script:
1. `GET /api/v1/agents/{id}/erc8004` — AgentURI-style metadata (identity
   registry shape): DID, endpoints, `supportedTrust`, dimensions. Validates
   required keys.
2. `GET /api/v1/agents/{id}/erc8004/feedback` — Reputation-registry feedback
   (`format: erc8004-reputation-v1`): score entries with task refs.
   Validates shape.
3. Prints both, then constructs the **write-side** payloads:
   - an Identity-registry `AgentURI` registration tuple
     (`agentId`, `agentURI` → the GARL passport endpoint),
   - a Reputation-registry `giveFeedback`-shaped entry derived from the
     GARL trust score, with the feedback's evidence URI pointing at a
     signed GARL receipt instead of an unverifiable score claim.

## Why receipts matter here

ERC-8004's reputation registry has a documented farming problem (one client
generated 65.8 % of all feedback in its early registry). GARL's answer is to
make the *evidence* the unit of exchange: a feedback entry that references a
signed, capability-linked, Merkle-anchored Action Receipt
(`.../receipts/{hash}/cert.json` + `/proof`) can be independently
re-verified; a bare score cannot. Same curve (secp256k1), so GARL signatures
are natively verifiable by on-chain systems.
