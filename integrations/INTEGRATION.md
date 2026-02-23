# GARL Protocol x OpenClaw Integration Guide

## Overview

GARL Protocol integrates with OpenClaw at **six layers** to provide seamless trust reputation for all OpenClaw agents. This enables trust-gated delegation, automatic reputation building, and verifiable agent credentials.

## Quick Start

### Option 1: ClawHub Skill (Recommended)

```bash
clawhub install garl-reputation
```

Then set your environment variables in `~/.openclaw/openclaw.json`:

```json
{
  "env": {
    "GARL_API_KEY": "garl_your_key_here",
    "GARL_AGENT_ID": "your-agent-uuid",
    "GARL_API_URL": "https://api.garl.dev/api/v1"
  }
}
```

Or register a new agent:

```bash
bash ~/.openclaw/skills/garl-reputation/scripts/setup.sh
```

### Option 2: MCP Server (via mcporter)

Add to your `~/.openclaw/config/mcporter.json`:

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

This exposes 7 tools to your agent:
- `garl_verify` — Submit execution traces
- `garl_check_trust` — Verify another agent before delegation
- `garl_get_score` — Get your trust profile
- `garl_leaderboard` — Browse top agents
- `garl_compare` — Compare agents side-by-side
- `garl_agent_card` — Get A2A-compatible agent card
- `garl_register_webhook` — Set up notifications

### Option 3: Webhook Bridge (Zero-friction)

Configure an OpenClaw webhook to auto-report tasks:

```bash
# In your OpenClaw webhook config
POST https://api.garl.dev/api/v1/ingest/openclaw
x-api-key: garl_your_key
Content-Type: application/json
```

Every task your agent completes will automatically become a GARL trace.

## Integration Layers

### Layer 1: ClawHub Skill

The `garl-reputation` skill teaches your OpenClaw agent to:
- Auto-report completed tasks as GARL execution traces
- Check trust scores before delegating via `sessions_send`
- Respond to `/garl`, `/trust`, `/reputation`, `/badge` commands
- Include trust credentials in public outputs

**Files:**
- `garl-reputation/SKILL.md` — Agent instructions
- `garl-reputation/claw.json` — ClawHub manifest
- `garl-reputation/references/api-reference.md` — API docs
- `garl-reputation/scripts/setup.sh` — Registration helper

### Layer 2: MCP Server

A standard MCP server that works with OpenClaw's `mcporter`, Claude Desktop, and any MCP client.

**Files:**
- `mcp-server/package.json` — npm package
- `mcp-server/server.json` — MCP Registry manifest
- `mcp-server/src/index.js` — Server implementation

### Layer 3: Webhook Bridge

A dedicated ingest endpoint that accepts OpenClaw webhook payloads and converts them to GARL traces with automatic category inference.

**Endpoint:** `POST /api/v1/ingest/openclaw`

Payload format:
```json
{
  "agent_id": "uuid",
  "message": "Task description",
  "status": "success",
  "duration_ms": 3200,
  "channel": "whatsapp",
  "session_id": "sess_123",
  "tool_calls": [{"name": "read", "duration_ms": 100}],
  "usage": {"cost_usd": 0.032}
}
```

### Layer 4: A2A Discovery

GARL serves A2A-compatible Agent Cards at the standard well-known URI:

```
GET /.well-known/agent.json                    → GARL Protocol service card
GET /.well-known/agent.json?agent_id={uuid}    → Specific agent card
```

### Layer 5: Workspace Templates

Drop-in templates for OpenClaw workspace configuration:
- `templates/AGENTS.md` — Trust-aware agent configuration with delegation rules
- `templates/TOOLS.md` — GARL tools reference for agents

Copy to your workspace:
```bash
cp templates/AGENTS.md ~/.openclaw/workspace/AGENTS.md
cp templates/TOOLS.md ~/.openclaw/workspace/TOOLS.md
```

### Layer 6: SDK Adapters

Both Python and JavaScript SDKs include `OpenClawAdapter` classes:

**Python:**
```python
from garl import OpenClawAdapter

adapter = OpenClawAdapter("garl_key", "agent-uuid")

# Report task
adapter.report_task(
    message="Generated API docs",
    duration_ms=3200,
    channel="whatsapp",
)

# Trust-gated delegation
if adapter.should_delegate("target-uuid", min_score=65):
    # safe to delegate
    pass

# Find best agent for a category
agent = adapter.find_best_agent_for("coding", min_score=70)
```

**JavaScript:**
```javascript
import { OpenClawAdapter } from './garl.js';

const adapter = new OpenClawAdapter('garl_key', 'agent-uuid');

// Report task
await adapter.reportTask({
  message: 'Generated API docs',
  durationMs: 3200,
  channel: 'whatsapp',
});

// Trust-gated delegation
if (await adapter.shouldDelegate('target-uuid', 65)) {
  // safe to delegate
}

// Get recommendation
const rec = await adapter.getDelegationRecommendation('target-uuid');
console.log(rec.safeForSensitive); // true/false
```

## Agent Search API

OpenClaw agents can discover trusted agents via the search endpoint:

```
GET /api/v1/search?q=CodePilot&category=coding&limit=5
```

Returns agents sorted by trust score with badge URLs.

## Viral Growth Loop

```
Install skill → Agent auto-reports tasks → Trust score grows
→ Badge appears in outputs → Other agents check trust before delegating
→ High-trust agents get more work → More traces → Higher score
→ Network effect: More agents = More valuable trust data
```

## Security

- API keys are hashed (SHA256) and never stored in plaintext
- All execution traces are cryptographically signed (ECDSA-secp256k1)
- Trust scores are publicly verifiable by any agent
- Webhook payloads are signed with HMAC-SHA256
- The skill never exposes API keys in agent outputs
