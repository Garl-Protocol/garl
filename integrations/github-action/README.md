# GARL Trust Gate — GitHub Action

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
