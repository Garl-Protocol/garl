# GARL Trust Gate — GitHub Action

> **Note:** This Action is the **legacy reputation-tier gate**. For
> AI-code provenance receipts (the primary GARL for Code surface),
> use [`Garl-Protocol/garl-receipt-action`](https://github.com/Garl-Protocol/garl-receipt-action).
> This gate is preserved for existing deployments and the
> `/api/v1/trust/*` deprecated surface (sunset 2027-04-15).

Block deployments if your AI agent's trust score drops below a threshold.

## Usage

```yaml
name: Trust Gate
on: [push]

jobs:
  trust-check:
    runs-on: ubuntu-latest
    steps:
      - uses: Garl-Protocol/garl/integrations/github-action@main
        with:
          agent-id: ${{ secrets.GARL_AGENT_ID }}
          api-key: ${{ secrets.GARL_API_KEY }}
          min-score: '65'
          min-tier: 'silver'
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `agent-id` | Yes | — | GARL Agent UUID |
| `api-key` | Yes | — | GARL API key |
| `min-score` | No | `60` | Minimum trust score (0-100) |
| `min-tier` | No | `silver` | Minimum tier (bronze/silver/gold/enterprise) |
| `api-url` | No | `https://api.garl.ai/api/v1` | API base URL |

## Outputs

| Output | Description |
|--------|-------------|
| `trust-score` | Current trust score |
| `tier` | Current certification tier |
| `passed` | `true` or `false` |
