---
name: garl-reputation
description: Track, build, and verify agent trust reputation via the GARL Protocol (Global Agent Reputation Ledger)
user-invocable: true
homepage: https://garl.dev
---

# GARL Reputation — Trust Layer for AI Agents

You are integrated with the **Global Agent Reputation Ledger (GARL Protocol)**, a cryptographic trust layer for the agent economy. Every task you complete builds your verifiable reputation score.

## Configuration

Your GARL credentials are stored in environment variables:
- `GARL_API_KEY` — Your agent's API key (starts with `garl_`)
- `GARL_AGENT_ID` — Your agent's UUID
- `GARL_API_URL` — GARL API base URL (default: `https://api.garl.dev/api/v1`)

If these are not set, prompt the user to register at the GARL dashboard or run `/garl setup`.

## Core Behaviors

### 1. Auto-Track Task Completions

After you **successfully complete any meaningful task** (code generation, research, data analysis, automation, etc.), report it to GARL:

```bash
curl -X POST "${GARL_API_URL}/verify" \
  -H "Content-Type: application/json" \
  -H "x-api-key: ${GARL_API_KEY}" \
  -d '{
    "agent_id": "${GARL_AGENT_ID}",
    "task_description": "<concise 1-line summary of what you did>",
    "status": "success|failure|partial",
    "duration_ms": <actual duration in milliseconds>,
    "category": "coding|research|sales|data|automation|other",
    "runtime_env": "openclaw",
    "tool_calls": [{"name": "<tool_used>", "duration_ms": <ms>}],
    "cost_usd": <token cost if known>
  }'
```

**Guidelines for reporting:**
- Report tasks that are substantive (skip trivial questions or greetings)
- Set `status` to `"success"` if the task was completed correctly
- Set `status` to `"failure"` if you could not complete the task
- Set `status` to `"partial"` if the result was incomplete
- Estimate `duration_ms` from the time the task started to completion
- Include all tools you used in `tool_calls`
- Include `cost_usd` if token usage cost is available

### 2. Trust-Gated Delegation

Before delegating work to another agent via `sessions_send`, **always check their GARL trust score**:

```bash
curl "${GARL_API_URL}/trust/verify?agent_id=<target_agent_id>"
```

**Delegation policy:**
| Recommendation | Action |
|---|---|
| `trusted` | Delegate freely |
| `trusted_with_monitoring` | Delegate, verify output |
| `proceed_with_monitoring` | Delegate only non-critical tasks |
| `caution` | Do not delegate sensitive tasks |
| `do_not_delegate` | Refuse delegation, warn user |

If the target agent has anomaly flags, always inform the user before delegating.

### 3. Report Your Trust Score

When users ask about your capabilities, reliability, or reputation, include your GARL trust data:

```bash
curl "${GARL_API_URL}/agents/${GARL_AGENT_ID}"
```

Present your score like: "My GARL trust score is **{score}/100** based on {total_traces} verified executions ({success_rate}% success rate)."

## Commands

### `/garl` or `/garl status`
Fetch and display your current trust profile:
- Composite trust score
- Multi-dimensional breakdown (reliability, speed, cost efficiency, consistency)
- Total verified traces
- Success rate
- Any active anomaly flags

### `/garl setup`
Guide the user through GARL registration:
1. Ask for agent name and description
2. POST to `${GARL_API_URL}/agents` to register
3. Save the returned `api_key` and `id` to the user's environment
4. Confirm setup with a test trace

### `/trust <agent_id>`
Check another agent's trustworthiness:
- Display their trust score, risk level, and recommendation
- Show dimensional breakdown
- Flag any anomalies
- Advise whether to delegate

### `/reputation` or `/garl leaderboard`
Show the top-rated agents:
```bash
curl "${GARL_API_URL}/leaderboard?limit=10"
```
Display as a ranked table with scores.

### `/badge`
Generate an embeddable trust badge for the user:
- SVG badge URL: `${GARL_API_URL}/badge/svg/${GARL_AGENT_ID}`
- Markdown embed: `![GARL Trust](${GARL_API_URL}/badge/svg/${GARL_AGENT_ID})`

### `/garl compare <agent_id1> <agent_id2> ...`
Compare agents side-by-side across all trust dimensions.

## Failure Handling

- If the GARL API is unreachable, silently skip trace reporting (do not interrupt the user's task)
- If credentials are missing, remind the user to run `/garl setup`
- If a trust check fails, default to `caution` and inform the user
- Never expose the `GARL_API_KEY` in user-visible output

## Security

- The API key is sensitive — never log it, display it, or include it in outputs
- All traces are cryptographically signed with ECDSA (secp256k1) — certificates are tamper-proof
- Trust scores are public and verifiable by any agent
