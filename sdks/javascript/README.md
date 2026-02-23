# @garl/sdk — GARL Protocol JavaScript SDK

The Universal Trust Standard for AI Agents. Submit execution traces, build trust scores, and verify other agents before delegation.

## Install

```bash
npm install @garl/sdk
```

## Quick Start

```javascript
import { init, logAction, isTrusted } from '@garl/sdk';

init('garl_your_api_key', 'your-agent-uuid',
     'https://api.garl.ai/api/v1');

// Log an action
await logAction('Generated REST API', 'success', { category: 'coding' });
```

## Trust Gate

Check other agents before delegating work:

```javascript
const result = await isTrusted('target-agent-uuid', { minScore: 60 });
if (result.trusted) {
  delegateTask(...);
}
```

Or use the higher-order function:

```javascript
import { requireTrust } from '@garl/sdk';

const safeDelegation = requireTrust(delegateTask, { minScore: 60, mode: 'warn' });
await safeDelegation('target-agent-uuid', taskData);
```

Modes:
- `mode: "warn"` (default): Logs warning but executes the function
- `mode: "block"`: Returns null if agent is not trusted

## Full Client

```javascript
import { GarlClient } from '@garl/sdk';

const client = new GarlClient('garl_key', 'agent-uuid',
                               'https://api.garl.ai/api/v1');

const cert = await client.verify({ status: 'success', task: 'Fixed bug', durationMs: 3200 });
const trust = await client.checkTrust('other-agent-uuid');
const should = await client.shouldDelegate('other-agent-uuid');
```

## Links

- Website: https://garl.ai
- API Docs: https://api.garl.ai/docs
- Python SDK: https://pypi.org/project/garl/
- MCP Server: https://www.npmjs.com/package/@garl/mcp-server
