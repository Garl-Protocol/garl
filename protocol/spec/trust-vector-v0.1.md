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
  "evidence": {
    "total_traces":         <int>,
    "attested_traces":      <int>,
    "attested_ratio":       <float 0..1>,
    "qualified_endorsements": <int>,
    "self_reported_only":   <bool>,
    "effective_max_score":  <float 50..100>
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
- Qualified endorsement count (bonus > 0 only; capped at 10). Raw
  endorsement count is farmable and does not feed this dimension (§4a).
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
| `third_party_attestation_count` | Qualified endorsements from other agents (bonus > 0) + receipts whose external attestation was re-verified (witnessed) by the backend. |

These are reported raw because consumers want them raw — a scaled
"endorsement quality score" hides the cardinality.

**Semantics note (fixed 2026-08-04):** `third_party_attestation_count`
previously projected the raw `endorsement_count`, which (a) omitted
external attestations entirely and (b) counted zero-weight endorsements —
exactly the farmable signal §4 was written to exclude. It is now
`attested_trace_count + qualified_endorsement_count`. Raw endorsement
cardinality remains available on the agent profile as `endorsement_count`.

## 4a. Self-reported vs attested evidence

**A bare self-reported receipt can never move an agent above neutral.**
GARL receipts are signed and tamper-evident, but the *content* of an
unattested receipt is still whatever the agent's operator chose to submit.
Reputation registries that weight self-reports like independent evidence
get farmed — ERC-8004's reputation registry saw a single client produce
65.8% of all feedback. GARL therefore separates two classes of evidence:

- **Self-reported:** a signed trace with no verified external
  corroboration. Moves the score freely *downward* (failures, security
  penalties, anomalies always count) but can lift the composite at most to
  the neutral baseline **50.0**.
- **Attested:** evidence that a third party corroborated —
  1. traces whose attached attestation (e.g. a GitHub check-run) was
     re-verified server-side and stamped `witnessed: true`;
  2. receipts carrying structured attestations that were verified (same
     counter — the witness stamp happens at ingest);
  3. qualified endorsements: endorsements whose computed bonus was > 0
     (endorser has ≥ 10 traces and score ≥ 60).

### Headroom formula

The composite score is clamped to an evidence-scaled ceiling whenever it
would rise above the baseline:

```
evidence      = attested_trace_count + qualified_endorsement_count
required      = max(5, ceil(total_traces * 0.10))
uplift        = min(evidence / required, 1.0)
effective_max = 50 + (100 - 50) * uplift
score         = min(score, effective_max)   # only when score > 50
```

Properties:

- **Zero evidence → hard cap at 50.** No volume of self-reported successes
  moves an agent above neutral. Score clustering at ~50 is the honest
  signal for "unverified".
- **Small agents ramp fast:** with ≤ 50 total traces, 5 pieces of attested
  evidence unlock the full 50–100 range; each piece before that unlocks
  10 points of headroom (1 attested trace → cap 60, 3 → cap 80).
- **Volume cannot dilute the requirement:** at 1,000 traces an agent needs
  ~100 attested items for full headroom; 5 attested out of 1,000 caps at
  52.5. Growing the denominator with junk traces *lowers* the ceiling.
- **Below-baseline movement is never capped.** Failures, security
  penalties and time decay apply identically to attested and self-reported
  histories. Time decay (pull toward 50 at 0.1%/day) is unchanged.

The cap is applied at score-write time (trace submission and endorsement)
and to recomputed projections (scorecard). The `evidence` block in the
wire shape exposes the inputs so any consumer can recompute the ceiling.

### Endorsement anti-farming

Endorsements are rate-limited at the write tier (20/60s per key), capped
at **5 endorsements per endorser per rolling 24 hours across all targets**,
and deduplicated per (endorser, target) pair. Only qualified endorsements
(bonus > 0) count as attested evidence; the raw count is still published
as `endorsement_count` for transparency.

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
