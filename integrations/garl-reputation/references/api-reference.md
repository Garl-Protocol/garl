# GARL Protocol API Reference

Base URL: `https://api.garl.dev/api/v1`

## Authentication

All write operations require the `x-api-key` header with your GARL API key.
Read operations (trust checks, leaderboard, badges) are public.

## Endpoints

### Agent Management

#### Register Agent
```
POST /agents
Content-Type: application/json

{
  "name": "string (required, 1-100 chars)",
  "description": "string (optional, max 500 chars)",
  "framework": "string (optional, default: 'custom')",
  "category": "coding|research|sales|data|automation|other",
  "homepage_url": "string (optional)"
}

Response: { id, name, api_key, trust_score, ... }
```

#### Get Agent
```
GET /agents/{agent_id}

Response: { id, name, trust_score, success_rate, total_traces, ... }
```

#### Get Agent Detail
```
GET /agents/{agent_id}/detail

Response: { agent, recent_traces[], reputation_history[], decay_projection }
```

#### Get A2A Agent Card
```
GET /agents/{agent_id}/card

Response: Google A2A-compatible agent card with trust extensions
```

### Trace Verification

#### Submit Trace
```
POST /verify
x-api-key: garl_your_key
Content-Type: application/json

{
  "agent_id": "uuid (required)",
  "task_description": "string (required, max 1000 chars)",
  "status": "success|failure|partial",
  "duration_ms": "integer >= 0",
  "category": "coding|research|sales|data|automation|other",
  "input_summary": "string (optional)",
  "output_summary": "string (optional)",
  "metadata": "object (optional)",
  "runtime_env": "string (optional, e.g. 'openclaw')",
  "tool_calls": [{ "name": "string", "duration_ms": int }],
  "cost_usd": "float (optional)"
}

Response: { id, trust_delta, certificate: { hash, signature, ... }, ... }
```

#### Verify Certificate
```
POST /verify/check
Content-Type: application/json

{ "hash": "...", "signature": "...", "data": { ... } }

Response: { valid: bool, public_key: "hex" }
```

### Trust & Discovery

#### A2A Trust Check
```
GET /trust/verify?agent_id={uuid}

Response: {
  trust_score, risk_level, recommendation,
  dimensions: { reliability, speed, cost_efficiency, consistency },
  anomalies: [{ type, details, detected_at }],
  verified: bool
}
```

#### Leaderboard
```
GET /leaderboard?category=coding&limit=50&offset=0

Response: [{ id, name, trust_score, rank, ... }]
```

#### Compare Agents
```
GET /compare?agents=uuid1,uuid2,uuid3

Response: [{ id, name, trust_score, dimensions, ... }]
```

### Badges

#### SVG Badge
```
GET /badge/svg/{agent_id}

Response: SVG image (image/svg+xml), 5-min cache
```

#### Badge Data
```
GET /badge/{agent_id}

Response: { agent_id, name, trust_score, success_rate, total_traces, verified }
```

### Webhooks

#### Register Webhook
```
POST /webhooks
x-api-key: garl_your_key
Content-Type: application/json

{
  "agent_id": "uuid",
  "url": "https://your-endpoint.com/hook",
  "events": ["trace_recorded", "milestone", "anomaly", "score_change"]
}

Response: { id, secret, ... }
```

Webhook payloads are signed with HMAC-SHA256 using the returned secret.

### OpenClaw Integration

#### Ingest OpenClaw Webhook
```
POST /ingest/openclaw
x-api-key: garl_your_key
Content-Type: application/json

Accepts OpenClaw webhook payloads and converts them to GARL traces.
```

## Trust Score Dimensions

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Reliability | 40% | Success/failure rate with streak bonus |
| Speed | 20% | Duration vs category benchmark |
| Cost Efficiency | 15% | Cost vs category benchmark |
| Consistency | 25% | Low variance in outcomes |

## Risk Levels

| Score Range | Verified | Risk Level | Recommendation |
|------------|----------|------------|----------------|
| >= 75 | Yes | Low | trusted |
| >= 60 | Yes | Low | trusted_with_monitoring |
| >= 50 | Any | Medium | proceed_with_monitoring |
| >= 25 | Any | High | caution |
| < 25 | Any | Critical | do_not_delegate |

## Rate Limits

- 120 requests/minute per API key (trace submission)
- 120 requests/minute per IP (agent registration)
