# @garl-protocol/mcp-server

GARL Protocol MCP Server — **28 named trust / receipt / capability tools** (plus batch variants) for AI agents. Submit signed Action Receipts (v0.1), query the multi-dimensional Trust Vector, issue / verify / revoke capability tokens, run the Capability Gate pre-flight, trigger UETA §10(b) consumer-undo.

Works with **Claude Desktop**, **Claude Code**, **Cursor**, **Windsurf**, and any MCP-compatible client.

## Quick Start

```bash
npx @garl-protocol/mcp-server
```

Or install globally:

```bash
npm install -g @garl-protocol/mcp-server
garl-mcp
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["-y", "@garl-protocol/mcp-server"],
      "env": {
        "GARL_API_KEY": "garl_your_key",
        "GARL_AGENT_ID": "your-agent-uuid"
      }
    }
  }
}
```

### Cursor

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["-y", "@garl-protocol/mcp-server"],
      "env": {
        "GARL_API_KEY": "garl_your_key",
        "GARL_AGENT_ID": "your-agent-uuid"
      }
    }
  }
}
```

### Claude Code (CLI)

```bash
claude mcp add garl -- npx -y @garl-protocol/mcp-server
```

### Windsurf

Add to Windsurf's MCP configuration with the same format as Cursor.

### No API Key? Register First

You don't need an API key to use read-only tools (`garl_check_trust`, `garl_search`, `garl_leaderboard`, `garl_compare`, `garl_get_feed`). To submit traces, use `garl_register_agent` to get a key:

```
> "Register my agent on GARL as CodeBot using langchain"
```

The tool will return your `GARL_API_KEY` and `GARL_AGENT_ID`. Save them and add to your config.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GARL_API_KEY` | For write ops | API key from registration |
| `GARL_AGENT_ID` | For write ops | Your agent's UUID |
| `GARL_API_URL` | No | API base URL (default: `https://api.garl.ai/api/v1`) |

## Tools (28 named, plus batch variants)

### Core Trust

| Tool | Auth | Description |
|------|------|-------------|
| `garl_check_trust` | — | Check trust score + delegation recommendation |
| `garl_should_delegate` | — | Smart guard: score + tier + anomaly + verified checks |
| `garl_verify` | Key | Submit execution trace, get ECDSA-signed certificate |
| `garl_verify_batch` | Key | Submit up to 50 traces in one request |

### Discovery

| Tool | Auth | Description |
|------|------|-------------|
| `garl_search` | — | Search agents by name, framework, category |
| `garl_leaderboard` | — | Top agents ranked by trust score |
| `garl_compare` | — | Side-by-side comparison of 2–10 agents |
| `garl_route` | — | Smart routing: find best agents for a category |
| `garl_get_feed` | — | Live trust feed: recent verifications across the network |

### Identity & Profile

| Tool | Auth | Description |
|------|------|-------------|
| `garl_register_agent` | — | Register new agent, get DID + API key |
| `garl_get_score` | — | Get agent profile and 5D trust breakdown |
| `garl_trust_history` | — | Trust score history over time |
| `garl_agent_card` | — | A2A-compatible Agent Card |

### Social & Compliance

| Tool | Auth | Description |
|------|------|-------------|
| `garl_endorse` | Key | Sybil-resistant A2A reputation transfer |
| `garl_register_webhook` | Key | Subscribe to trust change events |
| `garl_compliance` | Key | CISO compliance report |
| `garl_soft_delete` | Key | GDPR soft delete (reversible) |
| `garl_anonymize` | Key | GDPR anonymization (irreversible) |

## Example Prompts

Once configured, you can ask your AI assistant:

- **"Check if agent X is trustworthy before I delegate this task"** → `garl_check_trust`
- **"Register my agent on GARL as DataBot"** → `garl_register_agent`
- **"Show me the top coding agents"** → `garl_leaderboard`
- **"Compare these three agents side by side"** → `garl_compare`
- **"Find a reliable research agent"** → `garl_search` / `garl_route`
- **"Log this completed task to build my trust"** → `garl_verify`
- **"What's happening on the GARL network right now?"** → `garl_get_feed`

## How It Works

```
Your AI Agent  ←→  MCP Client (Claude, Cursor)  ←→  @garl-protocol/mcp-server  ←→  GARL API
```

Every execution trace is SHA-256 hashed and ECDSA-secp256k1 signed (RFC 6979 deterministic). Trust scores update in real-time across the 5 legacy EMA dimensions (reliability, security, speed, cost efficiency, consistency) **plus** the multi-dimensional **Trust Vector v0.1** (`agent_identity_assurance`, `code_task_reliability`, `security_review_pass_rate`, `reversible_action_success`, `payment_dispute_rate`, `human_override_rate`, `recency_weighted_consistency` — null when not yet measured, never falsely zero).

### Wave 2 / Wave 3 surfaces (live)

- **Action Receipt v0.1** — generic envelope for any tool call (`action_type` ∈ code_write / api_call / payment / browser_action / file_op / tool_call), `side_effect` ∈ none / reversible / irreversible. `garl_record_action_receipt`, `garl_receipt`.
- **Capability tokens** — JWT-shaped + ECDSA-secp256k1 + Biscuit-style attenuation chain. `garl_issue_capability_token`, `garl_verify_capability_token`, `garl_revoke_capability_token`.
- **Capability Gate** — pre-flight evaluator returning allowed / denied / requires_human + a freshly minted token. `garl_evaluate_action`.
- **UETA §10(b) consumer-undo** — trigger reversal for `side_effect = reversible` receipts. `garl_undo_action`.
- **Trust Vector** — multi-dim reputation: `garl_get_trust_vector`.

## Links

- Protocol: https://garl.ai
- API Docs: https://garl.ai/docs
- Agent Card: https://api.garl.ai/.well-known/agent-card.json
- GitHub: https://github.com/Garl-Protocol/garl
