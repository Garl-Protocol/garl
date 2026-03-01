# @garl/mcp-server

GARL Protocol MCP Server — 18 trust reputation tools for AI agents.

Works with **Claude Desktop**, **Claude Code**, **Cursor**, **Windsurf**, and any MCP-compatible client.

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

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "garl": {
      "command": "npx",
      "args": ["-y", "@garl/mcp-server"],
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
      "args": ["-y", "@garl/mcp-server"],
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
claude mcp add garl -- npx -y @garl/mcp-server
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

## Tools (18)

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
Your AI Agent  ←→  MCP Client (Claude, Cursor)  ←→  @garl/mcp-server  ←→  GARL API
```

Every execution trace is SHA-256 hashed and ECDSA-secp256k1 signed. Trust scores update in real-time across 5 dimensions: reliability, security, speed, cost efficiency, and consistency.

## Links

- Protocol: https://garl.ai
- API Docs: https://garl.ai/docs
- Agent Card: https://api.garl.ai/.well-known/agent-card.json
- GitHub: https://github.com/Garl-Protocol/garl
