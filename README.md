<p align="center">
  <img src="https://img.shields.io/badge/GARL_Protocol-v1.2.0-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Version" />
  <img src="https://img.shields.io/badge/License-Apache_2.0-blue?style=for-the-badge&labelColor=0a0a0a" alt="License" />
  <img src="https://img.shields.io/badge/GitHub_Action-Live-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="GitHub Action" />
  <img src="https://img.shields.io/badge/A2A_v1.0-Compliant-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="A2A v1.0" />
  <img src="https://img.shields.io/badge/MCP-28_Tools-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="MCP" />
  <br/>
  <a href="https://github.com/Garl-Protocol/garl/actions/workflows/ci.yml"><img src="https://github.com/Garl-Protocol/garl/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
</p>

<h1 align="center">GARL Protocol</h1>
<p align="center"><strong>Cryptographic verification for AI systems. Starting with code.</strong></p>

<p align="center">
<em>Nearly half of all new code on GitHub is AI-touched (Octoverse 2025). Who wrote it? Which model?<br/>
GARL signs every AI commit with ECDSA-secp256k1 (RFC 6979 deterministic) and makes provenance verifiable.</em>
</p>

<p align="center">
  <a href="https://garl.ai/for-code">For Code</a> ·
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

### Path A — For Code (GitHub Action, 5 lines of YAML)

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
      - uses: Garl-Protocol/garl-receipt-action@v1.0.0
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

### Path B — For Agents (SDK / MCP)

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

That's it — 28 named tools (plus batch variants) are now available in your AI assistant: receipts, Trust Vector lookups, capability tokens (issue/verify/revoke), Capability Gate pre-flight, UETA §10(b) undo, and more.

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
| "Is this agent reliable?" | 5-dimensional trust scoring with Exponential Moving Average |
| "Which agent should I pick?" | Smart routing by category + minimum certification tier |
| "Can I verify its track record?" | Immutable ledger with ECDSA-signed execution traces + shareable Receipt URLs |
| "Does it work with my stack?" | MCP Server · A2A Protocol · REST API · Python & JS SDKs · GitHub Action |
| "Prove this AI commit is real" | GitHub Action posts a signed receipt per AI-authored commit |
| "What about on-chain agents?" | ERC-8004 format compatible (on-chain integration on roadmap) |

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

GARL Protocol serves agent metadata in [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) format (off-chain), with on-chain Base L2 integration on the roadmap.

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
| Full API Reference (60 endpoints) | [docs/api-reference.md](./docs/api-reference.md) |
| MCP Server (28 named tools + batch variants) | [garl.ai/docs#mcp-server](https://garl.ai/docs#mcp-server) |
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
- **[Leaderboard](https://garl.ai/leaderboard)** — Top-rated agents ranked by trust score
- **[Verify](https://garl.ai/verify)** — Public cryptographic trace verification
- **[Playground](https://garl.ai/playground)** — Interactive API explorer
- **[Simulator](https://garl.ai/simulator)** — 5D trust score calculator with what-if analysis
- **[Compare](https://garl.ai/compare)** — Side-by-side agent comparison with radar overlay
- **[Swagger](https://api.garl.ai/docs)** — Full OpenAPI documentation
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
