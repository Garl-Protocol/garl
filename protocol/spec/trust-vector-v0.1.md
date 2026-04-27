# GARL Trust Vector — v0.1

**Status:** Draft
**Date:** 2026-04-27
**Editors:** GARL Protocol maintainers

## 1. Why a vector instead of a score

A single composite trust score is convenient — and misleading. An agent
that's excellent at code generation is not necessarily excellent at
booking a reservation or settling a payment. Compressing those signals
into one number conflates domains and is trivially gameable.

The Trust Vector publishes the underlying dimensions and lets each
consumer pick the ones it needs.

> Stripe Radar + SLSA / Sigstore + a credit bureau, but for agent actions.

## 2. Wire shape

```json
{
  "version": "garl/trust-vector/v0.1",
  "agent_id": "<UUID>",
  "computed_at": "<RFC 3339 timestamp>",
  "dimensions": {
    "agent_identity_assurance":     0.0..1.0 | null,
    "code_task_reliability":        0.0..1.0 | null,
    "security_review_pass_rate":    0.0..1.0 | null,
    "reversible_action_success":    0.0..1.0 | null,
    "payment_dispute_rate":         0.0..1.0 | null,
    "human_override_rate":          0.0..1.0 | null,
    "recency_weighted_consistency": 0.0..1.0 | null
  },
  "counters": {
    "verified_receipt_count":         <int>,
    "third_party_attestation_count":  <int>
  },
  "legacy_composite": {
    "trust_score":         <float 0..100>,
    "certification_tier":  "bronze" | "silver" | "gold" | "enterprise"
  }
}
```

## 3. Dimension definitions

### `agent_identity_assurance`
How verified is the identity itself? Blends:
- Endorsement count (capped at 10).
- Agent age (asymptotic; saturates around 90 days).
- Activity (total receipts; saturates at 100).

Not a measure of "is this agent good", a measure of "is this *the* agent
you think it is".

### `code_task_reliability`
Reliability EMA filtered to receipts in the `code_write` action class.
Until per-class EMA tracking lands the projection uses the global EMA
discounted by trace volume — an agent with one perfect trace does not
outrank an agent with 200 mostly-perfect traces.

### `security_review_pass_rate`
Security-dimension EMA. Penalizes high-risk tool use, prompt-injection
hits, PII leakage flags.

### `reversible_action_success`
Success rate on receipts with `side_effect = reversible`. `null` until
non-code receipts start flowing through the system. Honest null beats
misleading 0.0.

### `payment_dispute_rate`
Of receipts with `action_type = payment`, fraction that subsequently
saw a chargeback or refund-cancel. `null` until payment receipts land.

### `human_override_rate`
Of receipts where the policy engine returned `requires_human`, the
fraction. Populated when the policy engine writes its decisions to
`policy_decisions` (v19+).

### `recency_weighted_consistency`
Variance with recency decay. Agents that were great two years ago and
average today should score lower than agents great today and untested
two years ago.

## 4. Counters (not normalized)

| Field | Meaning |
|---|---|
| `verified_receipt_count` | Total signed receipts the agent has ever produced. Authoritative. |
| `third_party_attestation_count` | Endorsements from other agents + external attestations. |

These are reported raw because consumers want them raw — a scaled
"endorsement quality score" hides the cardinality.

## 5. `legacy_composite`

The single composite `trust_score` (0–100) and `certification_tier` are
preserved here for backward compatibility with the legacy
`/api/v1/trust/*` surfaces. New code should prefer the vector.

## 6. Null semantics

`null` means **not yet measured**, not **scored zero**. Consumers MUST NOT
treat null as an implicit zero in averages or sorts; either skip the
dimension or surface it explicitly as "no data".

## 7. Version policy

- Adding new optional dimensions is **additive**; consumers ignore
  unknown keys.
- Removing or re-meaning a dimension is **breaking**; bumps to v0.2 etc.
- v1.0 freezes the wire format. Until then, expect movement.

## 8. License

Apache 2.0.
