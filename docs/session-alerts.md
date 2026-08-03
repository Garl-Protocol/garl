# Session Alerts (behavioral layer v0)

Per-action checks are not enough. In the Grok/Bankr incident (May 2026),
~$150-175K was lost through transactions that were each individually
legitimate — valid tokens, allowed merchants, per-action limits respected.
The attack was only visible as a **session-level pattern**: privilege
escalation attempts, spend velocity against the delegated budget, and
actions against targets the agent had never touched before.

The session-alert layer watches the last-24h receipt stream and
capability-token graph per agent, and mints a **signed alert envelope** when
a rule fires. Alerts are append-only public evidence (same disclosure and
immutability model as receipts) and are delivered to the agent's registered
webhooks under the existing `"anomaly"` event type.

## What it watches

| Rule | Signal | Severity |
|------|--------|----------|
| `spend_velocity` | Sum of receipt `cost.usd` in the last 24h vs the largest `spend_limit_usd` among the agent's active (non-revoked, non-expired) capability tokens. | warning at >= 80%, critical at > 100% |
| `scope_escalation_attempt` | A child capability token tried to WIDEN its parent at issue time (attenuation violation). The issuance is rejected exactly as before — this rule additionally records the attempt. Push-based: emitted at issuance, not by the scan. | critical |
| `delegation_depth` | Longest `parent_token_hash` chain among capability tokens issued in the window (root token = depth 1). | warning at depth >= 4, critical at >= 6 |
| `novel_target` | An `irreversible` action against a `tool_server` not seen anywhere in the agent's prior 30 days of receipts. | warning |
| `receipt_rate` | Receipts in the last hour vs the trailing 7-day hourly average (burst hour excluded from the baseline). Fires only when the count is both >= 20 and > 10x the baseline. | warning |

Deduplication: the same `(agent, rule)` pair alerts at most once per 6 hours.

## Alert envelope (`garl/session-alert/v0.1`)

Signed with the same pipeline as Action Receipts: canonical JSON
(`app.core.canonical`) → SHA-256 → ECDSA-secp256k1 (RFC 6979 deterministic,
low-S). The signature covers the envelope **without** `signature` and
`verification_key_id`; resolve `verification_key_id` against
[`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json).

```json
{
  "alert_id": "0d6f3a3e-…",
  "version": "garl/session-alert/v0.1",
  "issuer": "https://api.garl.ai",
  "agent_identity": "did:garl:<agent uuid>",
  "rule": "spend_velocity",
  "severity": "warning",
  "summary": "Spend in the last 24h ($82.50) is 83% of the active capability spend limit ($100.00).",
  "evidence": {
    "window_spend_usd": 82.5,
    "active_spend_limit_usd": 100.0,
    "ratio": 0.825,
    "receipt_count": 41
  },
  "window": {"start": "2026-08-02T04:23:00Z", "end": "2026-08-03T04:23:00Z", "hours": 24},
  "timestamp": "2026-08-03T04:23:00Z",
  "signature": "<128 hex chars>",
  "verification_key_id": "<16 hex chars>"
}
```

`evidence` is rule-specific (see the table above for what each rule
measures); `window` is the analysis window the rule ran over.

## API

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /api/v1/agents/{agent_id}/alerts?limit=&offset=` | public | One agent's alerts, newest first (limit <= 100). |
| `GET /api/v1/alerts?limit=` | public | Recent alerts across all agents (limit <= 100). |
| `POST /api/v1/agents/{agent_id}/scan` | `x-api-key` (agent owner) | Run the scan for this agent now; returns alerts minted by this run. |

Scans also run daily for every active agent via
`.github/workflows/session-scan.yml` (`scripts/session_scan.py`).

## Webhook payload

Delivered through the existing per-agent webhook mechanism — register a
webhook with `"anomaly"` in its `events` (the default set includes it).
Delivery reuses the receipt-webhook rail: HMAC-SHA256 of the raw body with
your webhook secret in `X-GARL-Signature`, no redirects followed, 5s
timeout, public-IP re-validation before each attempt.

```json
{
  "event": "anomaly",
  "type": "session_alert",
  "agent_id": "<agent uuid>",
  "rule": "novel_target",
  "severity": "warning",
  "summary": "…",
  "alert": { "…full signed envelope…": true },
  "timestamp": "2026-08-03T04:23:00Z"
}
```

Legacy trace-level anomaly webhooks (`event: "anomaly"` without
`"type": "session_alert"`) continue unchanged; discriminate on `type`.

## Honest v0 limitations

- **Rules, not ML.** Five fixed heuristics with fixed thresholds. No
  baselining per agent beyond the receipt-rate average, no sequence models,
  no cross-agent correlation.
- **24h window.** A "low-and-slow" pattern spread over days will not trip
  `spend_velocity` or `receipt_rate`.
- **Detection, not prevention.** Alerts fire after the receipts exist. The
  only preventive element is that `scope_escalation_attempt` records an
  issuance that was already being rejected.
- **Spend measurement trusts reported costs.** `cost` is self-reported in
  receipts; an agent that omits cost is invisible to `spend_velocity`.
  Budget = the *largest* active token limit, chosen to minimize false
  positives; an agent juggling several small-limit tokens is measured
  against its most generous one.
- **`novel_target` is noisy for young agents.** With under 30 days of
  history, most targets are "novel" by definition (dedupe caps this at one
  alert per 6h).
- **Scan cadence.** Between the daily cron and on-demand `POST /scan`
  calls, nothing runs continuously; a burst can be hours old before it is
  flagged.
