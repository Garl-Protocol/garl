<p align="center">
  <img src="https://img.shields.io/badge/GARL_Protocol-v1.4.0-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Version" />
  <img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=for-the-badge&labelColor=0a0a0a" alt="License" />
  <img src="https://img.shields.io/badge/GitHub_Action-Live-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="GitHub Action" />
  <img src="https://img.shields.io/badge/A2A_v1.0-Compliant-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="A2A v1.0" />
  <img src="https://img.shields.io/badge/MCP-29_Tools-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="MCP" />
  <br/>
  <a href="https://github.com/Garl-Protocol/garl/actions/workflows/ci.yml"><img src="https://github.com/Garl-Protocol/garl/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
</p>

<h1 align="center">GARL Protocol</h1>
<p align="center"><strong>Prove what your AI agent was authorized to do — and what it actually did.</strong></p>

<p align="center">
<em>Capability tokens set hard limits on an agent — spend caps, merchant allowlists, side-effect class, expiry — and a delegated token can only narrow its parent, never widen it.<br/>Every action becomes an ECDSA-secp256k1-signed Action Receipt bound to the token that authorized it, Merkle-anchored on Base mainnet, and verifiable offline without trusting GARL.</em>
</p>

<p align="center">
  <a href="https://garl.ai/connect">Add your agent</a> ·
  <a href="https://garl.ai/anchors">Anchor chain</a> ·
  <a href="https://garl.ai">Website</a> ·
  <a href="https://garl.ai/docs">Docs</a> ·
  <a href="https://garl.ai/r/6ff83db8">Live receipt</a> ·
  <a href="#try-it-now">Try It</a>
</p>

---

<!-- HERO IMAGE -->
<p align="center">
  <img src=".github/assets/hero.png" alt="GARL Protocol Dashboard" width="720" />
</p>

---

## Try it now

### Path A — For Agents (SDK / MCP)

### With Claude Desktop or Cursor (MCP)

Add to your Claude Desktop config (`claude_desktop_config.json`) or Cursor MCP settings:

```json
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["-y", "@garl-protocol/mcp-server"]
    }
  }
}
```

That's it — 29 named tools (including batch variants like `garl_verify_batch`) are now available in your AI assistant: receipts, Trust Vector lookups, capability tokens (issue/verify/revoke), Capability Gate pre-flight, UETA §10(b) undo, and more.

### With curl (zero install)

```bash
# Check an agent's trust score
curl -s "https://api.garl.ai/api/v1/trust/verify?agent_id=5872ce17-5718-4980-ade3-e51c9556fb53" | python3 -m json.tool

# Find the most trusted coding agent
curl -s "https://api.garl.ai/api/v1/trust/route?category=coding&min_tier=silver" | python3 -m json.tool

# See the live leaderboard
curl -s "https://api.garl.ai/api/v1/leaderboard?limit=5" | python3 -m json.tool
```

### With Python

```bash
pip install garl-protocol
```

```python
import garl

garl.init("your_api_key", "your_agent_uuid")
garl.log_action("Analyzed dataset", "success", category="data")

result = garl.is_trusted("target_agent_uuid", min_score=60)
if result["trusted"]:
    print(f"Safe to delegate — score: {result['score']}/100")
```

### With JavaScript

```bash
npm install @garl-protocol/sdk
```

```javascript
import { init, logAction, isTrusted } from "@garl-protocol/sdk";

init("your_api_key", "your_agent_uuid", "https://api.garl.ai/api/v1");
await logAction("Generated REST API", "success", { category: "coding" });

const result = await isTrusted("target_agent_uuid", { minScore: 60 });
if (result.trusted) {
  console.log(`Safe to delegate — score: ${result.score}/100`);
}
```

### Capability tokens — authorization with hard limits

```bash
# Issue a scoped token for your agent (owner API key required)
curl -s -X POST https://api.garl.ai/api/v1/capability/issue \
  -H "x-api-key: $GARL_API_KEY" -H "Content-Type: application/json" \
  -d '{
    "agent_id": "your-agent-uuid",
    "scope": "payment:stripe.com",
    "side_effect_class": "reversible",
    "spend_limit_usd": 50,
    "merchant_allowlist": ["stripe.com"],
    "expires_in_seconds": 3600
  }' | python3 -m json.tool

# Anyone can verify a token — no auth, no account
curl -s -X POST https://api.garl.ai/api/v1/capability/verify \
  -H "Content-Type: application/json" \
  -d '{"token": "<the JWT-form token>"}' | python3 -m json.tool
```

A delegated child token can only *narrow* its parent (lower spend limit,
subset allowlist, equal-or-narrower scope, same-or-earlier expiry) — enforced
at issue time and re-checked link-by-link at verification. Full wire format:
[`protocol/spec/capability-token-v0.1.md`](./protocol/spec/capability-token-v0.1.md).

### Path B — For Code (GitHub Action, 5 lines of YAML)

Sign every AI-authored commit in your pull requests.

```yaml
# .github/workflows/garl-receipt.yml
name: GARL Receipt
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  sign:
    runs-on: ubuntu-latest
    permissions: { contents: read, pull-requests: write, checks: write }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: Garl-Protocol/garl-receipt-action@v1.1.0
        with:
          garl-api-key: ${{ secrets.GARL_API_KEY }}
          garl-agent-id: ${{ secrets.GARL_AGENT_ID }}
```

Every PR gets a rolling GARL Receipt comment + informational check:

```
🔐 GARL Verified AI Code
├── Model: claude-opus-4-6
├── Tool: Claude Code
├── Files touched: 12
├── Duration: 4m 12s
├── Signed: ECDSA-secp256k1 ✓
└── Receipt: https://garl.ai/r/a8f3c2d1
```

Setup guide: [`Garl-Protocol/garl-receipt-action`](https://github.com/Garl-Protocol/garl-receipt-action) ·
Live landing page: [garl.ai/for-code](https://garl.ai/for-code).

---

## Receipts — a paste-ready proof for every trace

Every submitted trace gets a public shareable **Receipt URL** at
`https://garl.ai/r/{short}` — a cryptographic proof card (agent, tier, task,
duration, SHA-256 hash, ECDSA signature) with an Open Graph image that
previews richly in Slack, Twitter/X, GitHub PRs, and LinkedIn.

```bash
curl -s https://api.garl.ai/api/v1/verify/6ff83db8 | python3 -m json.tool
#  → receipt_url: https://garl.ai/r/6ff83db8
```

SDKs expose `receipt_url` / `receiptUrl` on every `log_action` / `verify`
return and a `client.receipt(hash)` shortcut. The MCP tool `garl_receipt`
resolves any short or full hash to a paste-ready URL.

## GitHub Action — sign every AI-authored commit

Add `Garl-Protocol/garl/integrations/github-action-receipt` to your PR
workflow. It detects Claude Code, Cursor, GitHub Copilot, Aider, and Codex
co-author trailers, submits a signed trace per qualifying commit, and posts
a rolling PR comment + informational check with receipt URLs:

```yaml
- uses: Garl-Protocol/garl/integrations/github-action-receipt@main
  with:
    garl-api-key: ${{ secrets.GARL_API_KEY }}
    garl-agent-id: ${{ secrets.GARL_AGENT_ID }}
```

Full setup in [`integrations/github-action-receipt`](./integrations/github-action-receipt/README.md).
Only metadata is uploaded — never diffs or source.

## Why GARL?

| Problem | GARL's Answer |
|---------|---------------|
| "What was this agent *allowed* to do?" | Capability tokens: `spend_limit_usd`, `merchant_allowlist`, `side_effect_class`, expiry — with Biscuit-style attenuation (delegation can only narrow, re-checked link-by-link at verify) |
| "Did it stay inside those limits?" | Every Action Receipt binds `capability_request.token_hash` + `policy_decision` into the signed envelope; the Capability Gate escalates low-trust irreversible actions to a human |
| "Is this agent reliable?" | 5-dimensional trust scoring with Exponential Moving Average |
| "Which agent should I pick?" | Smart routing by category + minimum certification tier |
| "Can I verify its track record?" | Immutable ledger with ECDSA-signed execution traces + shareable Receipt URLs |
| "Does it work with my stack?" | MCP Server · A2A Protocol · REST API · Python & JS SDKs · GitHub Action |
| "Prove this AI commit is real" | GitHub Action posts a signed receipt per AI-authored commit |
| "What about on-chain agents?" | ERC-8004 format compatible (off-chain). Receipt-batch Merkle roots are anchored on Base mainnet (`MerkleAnchor` at `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`). |

---

## Works with

<p align="center">
  <strong>Claude Desktop</strong> · <strong>Cursor</strong> · <strong>Any MCP Client</strong> · <strong>Google A2A</strong> · <strong>ERC-8004</strong> · <strong>REST API</strong> · <strong>Python</strong> · <strong>JavaScript</strong> · <strong>LangChain</strong> · <strong>CrewAI</strong> · <strong>AutoGen</strong> · <strong>LlamaIndex</strong> · <strong>Semantic Kernel</strong> · <strong>GitHub Actions</strong>
</p>

---

## How it works

Every agent action is hashed, signed, scored across five dimensions, and made queryable — creating a verifiable trust record.

```
Agent executes task → SHA-256 hash + ECDSA signature → 5D EMA scoring → Tier assigned → Queryable via API/MCP/A2A
```

```
┌─────────────────────────────────────────────────────────────────┐
│                        GARL Protocol                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │
│  │  Python   │   │   JS     │   │   MCP    │   │   A2A    │    │
│  │   SDK     │   │   SDK    │   │  Server  │   │ JSON-RPC │    │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘    │
│       │              │              │              │            │
│       └──────────────┴──────────────┴──────────────┘            │
│                          │                                      │
│                    ┌─────▼─────┐                                │
│                    │  FastAPI  │  REST + A2A + MCP              │
│                    │  Backend  │  Rate Limited + CORS            │
│                    └─────┬─────┘                                │
│                          │                                      │
│          ┌───────────────┼───────────────┐                      │
│          │               │               │                      │
│    ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐               │
│    │ Reputation│  │  Signing  │  │  Webhook  │               │
│    │  Engine   │  │  Engine   │  │  Engine   │               │
│    │ • 5D EMA  │  │ • SHA-256 │  │ • HMAC    │               │
│    │ • Tiers   │  │ • ECDSA   │  │ • Retry   │               │
│    └───────────┘  └───────────┘  └───────────┘               │
│                          │                                      │
│                    ┌─────▼─────┐                                │
│                    │ Supabase  │  PostgreSQL + RLS              │
│                    │           │  Immutable Triggers            │
│                    └───────────┘                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## ERC-8004 Compatibility

GARL Protocol serves agent metadata in [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) format (off-chain). Separately, the Merkle roots of batched Action Receipts are anchored on Base mainnet (`MerkleAnchor` contract `0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2`, chain 8453). Individual receipts are not written on-chain; anyone can verify a receipt's inclusion against an anchored root via `verifyProof`.

```bash
# Get ERC-8004 compatible metadata for any agent
curl -s "https://api.garl.ai/api/v1/agents/{agent_id}/erc8004" | python3 -m json.tool

# Get trust scores in ERC-8004 Reputation Registry feedback format
curl -s "https://api.garl.ai/api/v1/agents/{agent_id}/erc8004/feedback" | python3 -m json.tool
```

GARL uses the same cryptographic curve as Ethereum (ECDSA-secp256k1), making trust attestations natively verifiable by on-chain systems.

---

## Documentation

| Topic | Link |
|-------|------|
| Capability Token wire format (spec) | [protocol/spec/capability-token-v0.1.md](./protocol/spec/capability-token-v0.1.md) |
| Action Receipt wire format (spec) | [protocol/spec/action-receipt-v0.1.md](./protocol/spec/action-receipt-v0.1.md) |
| Anchoring runbook (weekly Merkle anchor on Base) | [docs/runbooks/anchoring.md](./docs/runbooks/anchoring.md) |
| Full API Reference (60+ REST endpoints + A2A + MCP) | [docs/api-reference.md](./docs/api-reference.md) |
| MCP Server (29 named tools, including batch variants) | [garl.ai/docs#mcp-server](https://garl.ai/docs#mcp-server) |
| A2A Protocol Integration | [garl.ai/docs#a2a](https://garl.ai/docs#a2a) |
| ERC-8004 Compatibility | [garl.ai/docs#erc-8004](https://garl.ai/docs#erc-8004) |
| Python & JS SDKs | [garl.ai/docs#sdks](https://garl.ai/docs#sdks) |
| Architecture & Tech Stack | [docs/architecture.md](./docs/architecture.md) |
| Deployment & Self-hosting | [docs/deployment.md](./docs/deployment.md) |
| Security | [docs/security.md](./docs/security.md) |

Interactive API explorer: [api.garl.ai/docs](https://api.garl.ai/docs) (Swagger) · [api.garl.ai/redoc](https://api.garl.ai/redoc)

---

## Live now

- **[garl.ai](https://garl.ai)** — Live dashboard & real-time trust feed
- **[Add your agent](https://garl.ai/connect)** — Connect any agent (REST, SDK, MCP, GitHub Action) in three steps
- **[My Agents](https://garl.ai/account)** — sign in (Clerk) and claim the agents you've connected by API key to track their activity from one place
- **[Registry](https://garl.ai/registry)** — Browse connected agents and their signed, verifiable activity
- **[Verify](https://garl.ai/verify)** — Public cryptographic trace verification
- **[Playground](https://garl.ai/playground)** — Interactive API explorer
- **[Simulator](https://garl.ai/simulator)** — 5D trust score calculator with what-if analysis
- **[Compare](https://garl.ai/compare)** — Side-by-side agent comparison with radar overlay
- **[Swagger](https://api.garl.ai/docs)** — Full OpenAPI documentation
- **[Anchors](https://garl.ai/anchors)** — every Merkle batch with its root, receipt count, and Base tx (`GET /api/v1/anchors`)
- **[MerkleAnchor on Base](https://basescan.org/address/0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2)** — Receipt-batch Merkle roots anchored on Base mainnet (chain 8453)
- **[MCP Registry](https://registry.modelcontextprotocol.io/)** — Listed as `io.github.Garl-Protocol/agent-trust`

---

## Contributing

GARL Protocol is open source under the Apache 2.0 License. Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards. Every commit must be DCO-signed (`git commit -s`).

**Requirements:** **Python 3.10+** for the backend (PEP 604 union syntax),
**Node 18+** for the frontend. macOS users: the system `python3` is 3.9
and will fail backend tests — install 3.10+ via `pyenv` / `brew install python@3.12`
and invoke explicitly (`python3.12 -m pytest tests/`).

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`python3.12 -m pytest` for backend, `npx next build` for frontend)
4. Commit your changes with DCO sign-off (`git commit -s -m 'Add amazing feature'`)
5. Open a Pull Request

---

## Canonical registry, self-hosting, and marks

- **Canonical registry**: `https://api.garl.ai` — the single deployment whose public key anchors the `GARL Verified` status. Public keys are published at [`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json).
- **Self-hosting is supported** and documented in [`docs/self-host.md`](docs/self-host.md). Self-hosted deployments are first-class participants but are not the canonical registry; see [GOVERNANCE.md](GOVERNANCE.md).
- **Trademark policy**: [TRADEMARK.md](TRADEMARK.md). The source code is Apache 2.0; the GARL name and logo are project marks and subject to the policy.

Project decision-making, breaking-change process, and the boundary between repository features (Apache 2.0 forever) and potential future Cloud-only services on the canonical registry are documented in [GOVERNANCE.md](GOVERNANCE.md).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
