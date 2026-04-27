# garl — GARL Protocol Python SDK

Cryptographic verification for AI agent actions. Submit signed receipts, query Trust Vectors, and gate risky tool calls. Starting with code.

## Install

```bash
pip install garl-protocol
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

## Wave 2 — capability tokens, action receipts, undo (v1.3.0)

```python
# Multi-dimensional Trust Vector (replaces single trust_score for
# cross-domain decisions; null dimensions = "not yet measured")
vector = client.trust_vector()

# Capability Gate pre-flight: gets a token if allowed
gate = client.evaluate_action(
    action_type="payment",
    side_effect_class="reversible",
    spend_limit_usd=50.0,
    merchant_allowlist=["stripe.com"],
)
if gate["decision"] == "allowed":
    cap_token = gate["token"]   # JWT-shaped, ECDSA-secp256k1
    cap_hash  = gate["token_hash"]

# Submit a generic Action Receipt v0.1 (any tool call, not just commits)
import hashlib, json
def sha(o): return hashlib.sha256(
    json.dumps(o, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()

env = client.submit_action_receipt(
    action_type="api_call",
    side_effect="reversible",
    input_hash=sha({"endpoint": "/v1/refunds", "charge": "ch_123"}),
    output_hash=sha({"refund_id": "re_456", "amount": 1000}),
    capability_token_hash=cap_hash,
    attestations=["human_reviewed"],
)

# UETA §10(b) consumer-undo
undo = client.undo_receipt(env["receipt_id"])
print(undo["undo_payload"])  # the action to actually run

# Revoke a token (cascades to attenuated children)
client.revoke_capability_token(cap_hash, reason="task-complete")
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
- MCP Server: https://www.npmjs.com/package/@garl-protocol/mcp-server
