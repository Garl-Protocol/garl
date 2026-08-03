"""Tests for Trust Vector v0.1 projection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.trust_vector import (
    ALL_DIMENSIONS,
    TRUST_VECTOR_VERSION,
    compute_trust_vector,
    trust_vector_summary,
)


def _agent(**overrides) -> dict:
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "TestAgent",
        "trust_score": 72.5,
        "certification_tier": "gold",
        "ema_reliability": 88.0,
        "ema_security": 70.0,
        "ema_speed": 60.0,
        "ema_cost_efficiency": 50.0,
        "total_traces": 200,
        "endorsement_count": 3,
        "qualified_endorsement_count": 3,
        "attested_trace_count": 0,
        "created_at": (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
    }
    base.update(overrides)
    return base


def test_version_constant():
    assert TRUST_VECTOR_VERSION == "garl/trust-vector/v0.1"


def test_compute_returns_versioned_envelope():
    v = compute_trust_vector(_agent())
    assert v["version"] == TRUST_VECTOR_VERSION
    assert v["agent_id"] == "11111111-1111-1111-1111-111111111111"
    assert "computed_at" in v
    # ISO-8601 with timezone info
    parsed = datetime.fromisoformat(v["computed_at"])
    assert parsed.tzinfo is not None


def test_all_dimensions_present_in_response():
    v = compute_trust_vector(_agent())
    dims = v["dimensions"]
    counters = v["counters"]
    measurable_dims = {
        "agent_identity_assurance",
        "code_task_reliability",
        "security_review_pass_rate",
        "reversible_action_success",
        "payment_dispute_rate",
        "human_override_rate",
        "recency_weighted_consistency",
    }
    counter_dims = {"verified_receipt_count", "third_party_attestation_count"}
    assert set(dims.keys()) == measurable_dims
    assert set(counters.keys()) == counter_dims
    # Sanity: every advertised dimension is either measurable or counter
    advertised = set(ALL_DIMENSIONS)
    assert advertised == measurable_dims | counter_dims


def test_measurable_dimensions_normalized_to_unit_interval():
    v = compute_trust_vector(_agent())
    for name, value in v["dimensions"].items():
        if value is None:
            continue
        assert 0.0 <= value <= 1.0, f"{name} out of [0,1]: {value}"


def test_unmeasurable_dimensions_are_null_not_zero():
    """payment_dispute_rate and reversible_action_success need receipt types
    that don't exist yet. Returning 0.0 would be a lie; null is honest."""
    v = compute_trust_vector(_agent())
    assert v["dimensions"]["payment_dispute_rate"] is None
    assert v["dimensions"]["reversible_action_success"] is None


def test_identity_assurance_grows_with_qualified_endorsements():
    # Identity assurance keys off QUALIFIED endorsements (bonus > 0), not the
    # raw farmable endorsement_count (P2.8 anti-farming).
    base = compute_trust_vector(_agent(qualified_endorsement_count=0))
    high = compute_trust_vector(_agent(qualified_endorsement_count=10))
    assert high["dimensions"]["agent_identity_assurance"] > base["dimensions"]["agent_identity_assurance"]


def test_identity_assurance_ignores_raw_endorsement_count():
    # Piling up zero-weight endorsements must not move identity assurance.
    base = compute_trust_vector(_agent(endorsement_count=0, qualified_endorsement_count=0))
    spam = compute_trust_vector(_agent(endorsement_count=500, qualified_endorsement_count=0))
    # approx: the age signal is computed from wall-clock time at call time
    assert spam["dimensions"]["agent_identity_assurance"] == pytest.approx(
        base["dimensions"]["agent_identity_assurance"], abs=1e-6
    )


def test_identity_assurance_grows_with_age():
    new = compute_trust_vector(_agent(
        created_at=datetime.now(timezone.utc).isoformat(),
    ))
    old = compute_trust_vector(_agent(
        created_at=(datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
    ))
    assert old["dimensions"]["agent_identity_assurance"] > new["dimensions"]["agent_identity_assurance"]


def test_code_task_reliability_low_volume_low_confidence():
    """An agent with 1 perfect trace shouldn't beat an agent with 200 mostly-
    perfect traces. Confidence weighting applies."""
    high_volume = compute_trust_vector(_agent(ema_reliability=80.0, total_traces=200))
    low_volume = compute_trust_vector(_agent(ema_reliability=80.0, total_traces=1))
    assert high_volume["dimensions"]["code_task_reliability"] > low_volume["dimensions"]["code_task_reliability"]


def test_legacy_composite_preserved():
    """5D scoring stays authoritative for backward-compat /api/v1/trust/*
    endpoints; the vector projects without overwriting."""
    v = compute_trust_vector(_agent())
    assert v["legacy_composite"]["trust_score"] == 72.5
    assert v["legacy_composite"]["certification_tier"] == "gold"


def test_counters_are_integers():
    # Spec §4 (fixed): third_party_attestation_count = witnessed traces +
    # QUALIFIED endorsements — never the raw endorsement_count.
    v = compute_trust_vector(_agent(
        total_traces=200,
        endorsement_count=9,
        qualified_endorsement_count=3,
        attested_trace_count=2,
    ))
    assert v["counters"]["verified_receipt_count"] == 200
    assert v["counters"]["third_party_attestation_count"] == 5
    assert isinstance(v["counters"]["verified_receipt_count"], int)


def test_handles_missing_fields_without_crash():
    """Real Supabase rows may have nulls for fields like ema_reliability if
    the agent never had a trace. Vector should still compute."""
    minimal = {"id": "22222222-2222-2222-2222-222222222222"}
    v = compute_trust_vector(minimal)
    # Identity assurance falls back to age=0 + 0 endorsements => low but valid
    assert 0.0 <= v["dimensions"]["agent_identity_assurance"] <= 1.0
    # Reliability uses BASELINE 50 if EMA missing
    assert v["dimensions"]["code_task_reliability"] >= 0.0


def test_handles_nan_score_gracefully():
    """Postgres NUMERIC can serialize NaN in pathological cases. Vector must
    not propagate NaN to JSON output."""
    v = compute_trust_vector(_agent(ema_reliability=float("nan"), trust_score=float("nan")))
    for value in v["dimensions"].values():
        if value is not None:
            assert value == value  # NaN != NaN
    assert v["legacy_composite"]["trust_score"] == 0.0  # NaN coerced to default


def test_summary_returns_compact_shape():
    v = compute_trust_vector(_agent())
    s = trust_vector_summary(v)
    assert set(s.keys()) == {
        "average_measured",
        "measured_dimension_count",
        "verified_receipt_count",
        "tier",
    }
    assert 0.0 <= s["average_measured"] <= 1.0
    assert s["measured_dimension_count"] >= 1
    assert s["tier"] == "gold"


def test_summary_handles_all_null_dimensions():
    """A brand-new agent with no traces and no endorsements has mostly null
    measurable dimensions. Summary must not divide by zero."""
    v = compute_trust_vector({"id": "33333333-3333-3333-3333-333333333333"})
    s = trust_vector_summary(v)
    assert s["average_measured"] >= 0.0
