"""
Trust Vector v0.1 — multi-dimensional reputation.

Replaces the single composite `trust_score` as the canonical agent reputation
signal. Different domains stress different dimensions; one number conflates
them. The vector exposes the underlying components so callers can pick the
dimensions they care about (e.g. a payment gateway looks at
`payment_dispute_rate` and `agent_identity_assurance`; a code-review system
looks at `code_task_reliability`).

Backward compatibility: legacy `trust_score` and `score_*` scalars stay on
the agents table and are still authoritative for the legacy `/api/v1/trust/*`
endpoints. The vector is derived from the same underlying state — it is a
*projection*, not a separate computation. When the v17 migration applies,
the projection result is cached in `agents.trust_vector` JSONB; if the
migration has not yet applied the projection is computed on read.

Spec: protocol/spec/trust-vector-v0.1.md
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Vector schema version. Bumped when fields are added/renamed in a way that
# changes the shape consumers see. Additive expansion (new optional fields)
# does NOT bump the version; semver-style minor bumps for additions are
# possible (v0.2 etc.) but the major version freezes once the spec is sealed.
TRUST_VECTOR_VERSION = "garl/trust-vector/v0.1"

# All dimensions the vector reports. Some are populated immediately from
# existing 5D scores; others (payment_dispute_rate, reversible_action_success)
# remain at None until receipt types beyond code commits start landing.
ALL_DIMENSIONS = (
    "agent_identity_assurance",
    "code_task_reliability",
    "security_review_pass_rate",
    "reversible_action_success",
    "payment_dispute_rate",
    "human_override_rate",
    "recency_weighted_consistency",
    "verified_receipt_count",
    "third_party_attestation_count",
)


def _clamp01(value: float) -> float:
    """Trust Vector dimensions are normalized to [0, 1]. Legacy 5D scores are
    in [0, 100]; converted on projection."""
    if value != value:  # NaN
        return 0.0
    return max(0.0, min(1.0, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def _agent_age_days(agent: dict) -> float:
    created = agent.get("created_at")
    if not created:
        return 0.0
    if isinstance(created, str):
        try:
            ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    else:
        ts = created
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0


def _identity_assurance(agent: dict) -> float:
    """How verified is the agent identity?

    DID stability is implicit (the row exists and the sovereign_id is
    immutable). We blend three signals:
      1. Endorsement count, capped at 10 (each endorsement = +0.05).
      2. Age in days, asymptotic to 1.0 (saturates around 90 days).
      3. Total trace count (saturates at 100 traces).
    """
    endorsements = _safe_float(agent.get("endorsement_count", 0))
    age_days = _agent_age_days(agent)
    traces = _safe_float(agent.get("total_traces", 0))

    endorsement_signal = min(endorsements / 10.0, 1.0) * 0.5
    age_signal = (1.0 - 1.0 / (1.0 + age_days / 30.0)) * 0.3
    activity_signal = min(traces / 100.0, 1.0) * 0.2

    return _clamp01(endorsement_signal + age_signal + activity_signal)


def _code_task_reliability(agent: dict) -> float:
    """Reliability EMA, lightly discounted by total trace volume so an agent
    with one perfect trace doesn't outrank an agent with 1000 mostly-perfect
    traces. Until per-category EMA tracking lands, we use the global EMA."""
    ema = _safe_float(agent.get("ema_reliability", 50.0))
    traces = _safe_float(agent.get("total_traces", 0))
    confidence = min(traces / 50.0, 1.0)
    return _clamp01((ema / 100.0) * confidence)


def _security_review_pass_rate(agent: dict) -> float:
    return _clamp01(_safe_float(agent.get("ema_security", 50.0)) / 100.0)


def _human_override_rate(agent: dict) -> float | None:
    """Fraction of recent receipts that triggered policy=requires_human.

    Policy decisions are written by the policy engine into the
    `policy_decisions` table (v19+). Until that lands we return None to
    signal "not yet measured" rather than a misleading 0.0.
    """
    return None


def _recency_weighted_consistency(agent: dict) -> float:
    """Consistency dimension already encodes recency via EMA on the legacy
    side. Project it directly."""
    return _clamp01(_safe_float(agent.get("ema_speed", 50.0)) / 100.0)


def compute_trust_vector(agent: dict) -> dict:
    """Project the legacy `agents` row into a Trust Vector v0.1 JSON shape.

    Returns the full vector with `null` for dimensions we cannot yet measure
    (payment_dispute_rate, reversible_action_success — depend on receipt
    types that arrive when Action Receipt v0.1 lands across non-code
    actions). All measurable dimensions are normalized to [0, 1].
    """
    vector = {
        "version": TRUST_VECTOR_VERSION,
        "agent_id": agent.get("id"),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": {
            "agent_identity_assurance":      _identity_assurance(agent),
            "code_task_reliability":          _code_task_reliability(agent),
            "security_review_pass_rate":      _security_review_pass_rate(agent),
            "reversible_action_success":      None,
            "payment_dispute_rate":           None,
            "human_override_rate":            _human_override_rate(agent),
            "recency_weighted_consistency":   _recency_weighted_consistency(agent),
        },
        "counters": {
            "verified_receipt_count":         int(_safe_float(agent.get("total_traces", 0))),
            "third_party_attestation_count":  int(_safe_float(agent.get("endorsement_count", 0))),
        },
        "legacy_composite": {
            "trust_score": _safe_float(agent.get("trust_score", 50.0)),
            "certification_tier": agent.get("certification_tier", "bronze"),
        },
    }
    return vector


def trust_vector_summary(vector: dict) -> dict:
    """Single-line summary suitable for leaderboard rows or hover cards.
    Surfaces the highest-confidence dimensions; consumers wanting full
    detail call the per-agent endpoint."""
    dims = vector.get("dimensions", {})
    measured = {k: v for k, v in dims.items() if v is not None}
    counters = vector.get("counters", {})
    avg = sum(measured.values()) / len(measured) if measured else 0.0
    return {
        "average_measured": round(avg, 4),
        "measured_dimension_count": len(measured),
        "verified_receipt_count": counters.get("verified_receipt_count", 0),
        "tier": vector.get("legacy_composite", {}).get("certification_tier", "bronze"),
    }
