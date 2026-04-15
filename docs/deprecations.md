# Deprecations and sunset schedule

GARL pivoted from generic agent-reputation to AI-code provenance in April 2026. Some endpoints from the pre-pivot era remain live for existing integrations but now carry explicit deprecation metadata. This page is the canonical sunset schedule.

## Current deprecations

| Path | Since | Sunset | Successor | Notes |
|---|---|---|---|---|
| `GET /api/v1/trust/*` | 2026-04-15 | **2027-04-15** | `GET /api/v1/verify/{hash}` + `POST /api/v1/policy/check` | Agent-to-agent trust pre-pivot surface. The pivot's primary loop is single-sided receipts, so these endpoints stay but move to the back-burner. |
| `GET /api/v1/a2a/*` + `POST /a2a` | 2026-04-15 | **2027-04-15** | `GET /.well-known/agent-card.json` + standard REST endpoints | A2A JSON-RPC is hard to maintain parallel to REST. The agent card stays. |
| `GET /api/v1/erc8004*` | 2026-04-15 | **2027-04-15** | `GET /.well-known/garl-keys.json` + receipt payload | ERC-8004 off-chain format stays accessible; on-chain bridge will move to a separate integration when that lands. |
| `?fields=full` on `GET /api/v1/agents/{id}` without owner auth | 2026-04-15 | **2026-10-15** | Same endpoint with matching `x-api-key` header | Owner-auth soft-cut — unauthenticated `?fields=full` silently downgrades to slim, carrying `Deprecation:true` + this `Sunset`. |

All deprecated responses include:

```
Deprecation: true
Sunset: <GMT timestamp from the table above>
Link: <https://garl.ai/for-code>; rel="successor-version"
```

RFC 8594 (Sunset HTTP Header) and RFC 9745 (Deprecation HTTP Header) semantics. Integrators can poll for these headers in CI to catch changes before the cut.

## v14 — dropped dormant trace columns

As of migration `v14_drop_dormant_columns` (2026-04-15), the `traces` table no longer has:

- `tool_calls`
- `proof_of_result`
- `runtime_env`

These were 0% or near-zero populated across 1,505 production traces. The `TraceSubmitRequest` schema still **accepts** these fields (backward-compat for SDK callers) but now stashes any supplied value under `metadata.*` in the JSONB column. No consumer has ever read these fields from the public API, so this is a silent cleanup.

If a future feature requires one of them as a first-class column, add a new migration — don't resurrect.

## Horizontal scale / Redis rate-limit

Not a deprecation — a future integration point. The current in-memory rate limiter (`backend/app/api/routes.py`) is adequate at `numReplicas=1`. If the canonical registry scales horizontally, rewrite the `_check_rate_limit` hot path to use Upstash Redis REST (or similar) via `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` env vars — no new dependency needed (`httpx` is already in the stack).

## Sunset policy

We give integrators **minimum 12 months** from announcement to removal for any deprecated endpoint. The [`GOVERNANCE.md`](../GOVERNANCE.md) breaking-change process (14-day comment period) applies on top of that. We'd rather document a long sunset than surprise anyone.
