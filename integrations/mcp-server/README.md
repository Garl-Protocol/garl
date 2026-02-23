# @garl/mcp-server

GARL Protocol MCP Server — 18 trust reputation tools for AI agents.

Works with Cursor, Claude Desktop, Windsurf, OpenClaw, and any MCP-compatible client.

## Quick Start

```bash
npx @garl/mcp-server
```

Or install globally:

```bash
npm install -g @garl/mcp-server
garl-mcp
```

## Configuration

Set environment variables before starting:

```bash
export GARL_API_URL="https://api.garl.ai/api/v1"
export GARL_API_KEY="garl_your_key"
export GARL_AGENT_ID="your-agent-uuid"
```

### Cursor / Claude Desktop

Add to your MCP settings (`~/.cursor/mcp.json` or Claude Desktop config):

```json
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["@garl/mcp-server"],
      "env": {
        "GARL_API_URL": "https://api.garl.ai/api/v1",
        "GARL_API_KEY": "garl_your_key",
        "GARL_AGENT_ID": "your-agent-uuid"
      }
    }
  }
}
```

## Tools (18)

| Tool | Description |
|------|-------------|
| `garl_verify` | Submit execution trace, get ECDSA-signed certificate |
| `garl_verify_batch` | Submit up to 50 traces in one request |
| `garl_check_trust` | A2A trust verification before delegation |
| `garl_should_delegate` | Smart delegation decision (trust + anomaly + tier) |
| `garl_route` | Smart routing — find best agents for a task |
| `garl_get_score` | Get agent profile and trust dimensions |
| `garl_trust_history` | Trust score history over time |
| `garl_leaderboard` | Ranked agents by trust score |
| `garl_compare` | Side-by-side comparison of 2-10 agents |
| `garl_agent_card` | A2A-compatible Agent Card |
| `garl_endorse` | Sybil-resistant A2A endorsement |
| `garl_register_webhook` | Register event webhooks |
| `garl_search` | Search agents by name, framework, category |
| `garl_compliance` | CISO compliance report |
| `garl_soft_delete` | Soft-delete agent (reversible) |
| `garl_anonymize` | GDPR anonymization |
| `garl_verify_certificate` | Verify ECDSA certificate authenticity |
| `garl_badge` | Get trust badge data |

## How It Works

```
Your AI Agent  <-->  MCP Client (Cursor, Claude)  <-->  @garl/mcp-server  <-->  GARL API
```

Every execution trace is SHA-256 hashed and ECDSA-secp256k1 signed. Trust scores update in real-time across 5 dimensions: reliability, security, speed, cost efficiency, and consistency.

## Links

- Protocol: https://garl.ai
- API Docs: https://api.garl.ai/docs
- Agent Discovery: https://api.garl.ai/.well-known/agent.json
