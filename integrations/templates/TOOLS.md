# GARL Protocol Tools Reference

## Available Tools

### garl_verify
Submit an execution trace after completing a task.
- **When**: After every substantive task completion
- **Required fields**: task_description, status (success/failure/partial), duration_ms
- **Optional fields**: category, tool_calls, cost_usd, input_summary, output_summary
- **Returns**: Cryptographic certificate with trust_delta

### garl_check_trust
Check another agent's trustworthiness before delegation.
- **When**: Before any `sessions_send` or work delegation
- **Required fields**: agent_id (UUID of target agent)
- **Returns**: trust_score, risk_level, recommendation, dimensions, anomalies

### garl_get_score
Retrieve your own (or another agent's) trust profile.
- **When**: When asked about capabilities, or via `/garl status`
- **Optional fields**: agent_id (defaults to self)
- **Returns**: Complete trust profile with all dimensions

### garl_leaderboard
List top-rated agents, optionally filtered by category.
- **When**: Finding trusted agents for delegation, or via `/reputation`
- **Optional fields**: category, limit
- **Returns**: Ranked agent list

### garl_compare
Compare multiple agents across all trust dimensions.
- **When**: Choosing between agents for delegation, or via `/garl compare`
- **Required fields**: agent_ids (array of 2-10 UUIDs)
- **Returns**: Side-by-side dimension comparison

### garl_agent_card
Get a Google A2A-compatible Agent Card.
- **When**: Agent discovery, sharing capabilities
- **Optional fields**: agent_id (defaults to self)
- **Returns**: Standardized agent card with trust extensions

### garl_register_webhook
Register for real-time notifications.
- **When**: Setting up monitoring, or via `/garl webhook`
- **Required fields**: url
- **Optional fields**: events (trace_recorded, milestone, anomaly, score_change)
- **Returns**: Webhook ID and signing secret

## Category Guidelines

Choose the correct category for accurate scoring benchmarks:

| Category | Use For | Speed Benchmark | Cost Benchmark |
|----------|---------|-----------------|----------------|
| coding | Code generation, debugging, refactoring | 10s | $0.05 |
| research | Analysis, search, investigation | 15s | $0.08 |
| sales | Outreach, proposals, CRM tasks | 5s | $0.03 |
| data | Data processing, ETL, queries | 12s | $0.06 |
| automation | Workflows, scripts, scheduling | 8s | $0.04 |
| other | Everything else | 10s | $0.05 |

## Error Handling

- If GARL API is unreachable: silently skip, do not interrupt the user's task
- If credentials missing: prompt user to run `/garl setup`
- If trust check fails: default to `caution`, inform user
- Never expose `GARL_API_KEY` in any output
