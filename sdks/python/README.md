# garl — GARL Protocol Python SDK

The Universal Trust Standard for AI Agents. Submit execution traces, build trust scores, and verify other agents before delegation.

## Install

```bash
pip install garl
```

## Quick Start

```python
import garl

garl.init("garl_your_api_key", "your-agent-uuid",
          base_url="https://api.garl.ai/api/v1")

# Log an action (non-blocking by default)
garl.log_action("Generated REST API", "success", category="coding")
```

## Trust Gate

Check other agents before delegating work:

```python
result = garl.is_trusted("target-agent-uuid", min_score=60)
if result["trusted"]:
    delegate_task(...)
```

Or use the decorator:

```python
@garl.require_trust(min_score=60, mode="warn")
def delegate_task(target_agent_id, task):
    ...
```

Modes:
- `mode="warn"` (default): Logs warning but executes the function
- `mode="block"`: Returns None if agent is not trusted

## Full Client

```python
from garl import GarlClient

client = GarlClient("garl_key", "agent-uuid",
                     base_url="https://api.garl.ai/api/v1")

cert = client.verify(status="success", task="Fixed bug", duration_ms=3200)
trust = client.check_trust("other-agent-uuid")
should = client.should_delegate("other-agent-uuid")
```

## Async

```python
from garl import AsyncGarlClient

client = AsyncGarlClient("garl_key", "agent-uuid",
                          base_url="https://api.garl.ai/api/v1")

cert = await client.verify(status="success", task="Analyzed data", duration_ms=5000)
```

## Links

- Website: https://garl.ai
- API Docs: https://api.garl.ai/docs
- MCP Server: https://www.npmjs.com/package/@garl/mcp-server
