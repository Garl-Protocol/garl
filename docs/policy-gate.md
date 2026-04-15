# Policy gate — declarative CI/CD checks for AI-authored commits

`POST /api/v1/policy/check` is a stateless endpoint that answers one question: **"Given these receipts and this policy, should my PR merge?"** It's designed to be called once from a CI job — no client-side policy logic to reimplement.

## Endpoint

```
POST /api/v1/policy/check
Content-Type: application/json

{
  "policy": { ... },
  "receipts": ["<trace_hash or short_hash>", ...]
}
```

Max 100 receipts per call. Short hashes (≥ 8 hex chars) and full 64-hex hashes both work.

## Policy fields (all optional, conjunctive)

| Field | Type | Behaviour |
|---|---|---|
| `min_score` | number (0-100) | Agent trust score must be ≥ this |
| `min_tier` | `"bronze" \| "silver" \| "gold" \| "enterprise"` | Tier must be ≥ this |
| `require_model_disclosure` | bool | Each receipt must carry `metadata.models` (non-empty) |
| `allowed_models` | list of model names | At least one must appear per receipt |
| `forbidden_models` | list of model names | None may appear in any receipt |
| `require_signing_epoch` | `"original"` | Pre-v0.3 unsigned-legacy receipts fail |

## Response

```json
{
  "pass": true | false,
  "policy": { ... },
  "evaluation_count": N,
  "evaluations": [
    {
      "receipt": "6ff83db8",
      "trace_hash": "6ff83db8...",
      "agent_id": "...",
      "agent_name": "...",
      "score": 79.53,
      "tier": "gold",
      "models": ["claude-opus-4-6", "copilot"],
      "pass": true,
      "reasons": []
    }
  ]
}
```

`pass: false` with a `reasons` array captures every failed constraint — score, tier, model disclosure, allowed/forbidden models, signing epoch.

## Using from GitHub Actions

```yaml
- name: GARL Policy Gate
  run: |
    RESP=$(curl -sf -X POST https://api.garl.ai/api/v1/policy/check \
      -H "Content-Type: application/json" \
      -d '{
        "policy": {
          "min_score": 60,
          "min_tier": "silver",
          "require_model_disclosure": true,
          "forbidden_models": ["gpt-4o-preview"]
        },
        "receipts": ["'"${{ steps.garl.outputs.receipt_short }}"'"]
      }')
    PASS=$(echo "$RESP" | jq -r '.pass')
    if [ "$PASS" != "true" ]; then
      echo "::error::GARL policy gate failed: $(echo "$RESP" | jq -r '.evaluations[0].reasons | join(", ")')"
      exit 1
    fi
```

## Multi-model attestation (companion feature)

The `models` field in a policy evaluation comes from the trace's `metadata.models`, which the SDK / GitHub Action populates at trace submission time:

```python
import garl

garl.log_action(
    task="Implement checkout flow",
    status="success",
    models=[
        {"name": "claude-opus-4-6", "version": "1m", "role": "primary-author", "detection_confidence": 0.95},
        {"name": "copilot", "role": "reviewer"},
    ],
)
```

One receipt, multiple co-authoring models — the policy gate can then allow / forbid specific combinations.

## See also

- Schema — `ModelAttestation` in [`backend/app/models/schemas.py`](../backend/app/models/schemas.py)
- Predicate types — [`docs/ecosystem.md`](ecosystem.md)
- Compliance formats — [`docs/compliance.md`](compliance.md)
