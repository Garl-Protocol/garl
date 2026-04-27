# @garl-protocol/sdk — GARL Protocol JavaScript SDK

Cryptographic verification for AI agent actions. Submit signed receipts, query Trust Vectors, and gate risky tool calls. Starting with code.

## Install

```bash
npm install @garl-protocol/sdk
```

## Quick Start

```javascript
import { init, logAction, isTrusted } from '@garl-protocol/sdk';

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
import { requireTrust } from '@garl-protocol/sdk';

const safeDelegation = requireTrust(delegateTask, { minScore: 60, mode: 'warn' });
await safeDelegation('target-agent-uuid', taskData);
```

Modes:
- `mode: "warn"` (default): Logs warning but executes the function
- `mode: "block"`: Returns null if agent is not trusted

## Full Client

```javascript
import { GarlClient } from '@garl-protocol/sdk';

const client = new GarlClient('garl_key', 'agent-uuid',
                               'https://api.garl.ai/api/v1');

const cert = await client.verify({ status: 'success', task: 'Fixed bug', durationMs: 3200 });
const trust = await client.checkTrust('other-agent-uuid');
const should = await client.shouldDelegate('other-agent-uuid');
```

## Wave 2 — capability tokens, action receipts, undo (v1.2.0)

```javascript
// Multi-dimensional Trust Vector
const vector = await client.trustVector();

// Capability Gate pre-flight: gets a token if allowed
const gate = await client.evaluateAction({
  actionType: 'payment',
  sideEffectClass: 'reversible',
  spendLimitUsd: 50,
  merchantAllowlist: ['stripe.com'],
});
if (gate.decision === 'allowed') {
  const capToken = gate.token;        // JWT-shaped, ECDSA-secp256k1
  const capHash  = gate.token_hash;
}

// Submit a generic Action Receipt v0.1 (any tool call, not just commits)
import { createHash } from 'node:crypto';
const sha = (o) => createHash('sha256')
  .update(JSON.stringify(o, Object.keys(o).sort())).digest('hex');

const env = await client.submitActionReceipt({
  actionType: 'api_call',
  sideEffect: 'reversible',
  inputHash:  sha({ endpoint: '/v1/refunds', charge: 'ch_123' }),
  outputHash: sha({ refund_id: 're_456', amount: 1000 }),
  capabilityTokenHash: gate.token_hash,
  attestations: ['human_reviewed'],
});

// UETA §10(b) consumer-undo
const undo = await client.undoReceipt(env.receipt_id);
console.log(undo.undo_payload);  // the action to actually run

// Revoke a token (cascades to attenuated children)
await client.revokeCapabilityToken(gate.token_hash, 'task-complete');
```

## Links

- Website: https://garl.ai
- API Docs: https://api.garl.ai/docs
- Python SDK: https://pypi.org/project/garl-protocol/
- MCP Server: https://www.npmjs.com/package/@garl-protocol/mcp-server
