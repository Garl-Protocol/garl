"""Capability Gate engine tests.

Mocks `get_agent`, `compute_trust_vector`, and `issue_capability_token` so
the gate logic is exercised without touching Supabase.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.capability_gate import (
    ACTION_DIMENSION_MAP,
    DEFAULT_THRESHOLDS,
    GateError,
    evaluate_request,
)


def _vector(**dim_overrides):
    """Build a Trust Vector dict with the same shape compute_trust_vector
    returns. Overrides go straight into `dimensions`."""
    base_dims = {
        "agent_identity_assurance": 0.6,
        "code_task_reliability": 0.8,
        "security_review_pass_rate": 0.7,
        "reversible_action_success": None,
        "payment_dispute_rate": None,
        "human_override_rate": None,
        "recency_weighted_consistency": 0.5,
    }
    base_dims.update(dim_overrides)
    return {
        "version": "garl/trust-vector/v0.1",
        "agent_id": "11111111-1111-1111-1111-111111111111",
        "computed_at": "2026-04-27T00:00:00+00:00",
        "dimensions": base_dims,
        "counters": {"verified_receipt_count": 100, "third_party_attestation_count": 0},
        "legacy_composite": {"trust_score": 75.0, "certification_tier": "gold"},
    }


class _FakeToken(dict):
    """Stand-in for issue_capability_token output so the gate can build a
    real-looking response without going through the persistence layer."""

    def __init__(self):
        super().__init__(
            token="aaa.bbb.ccc",
            token_hash="0" * 64,
            expires_at="2026-04-27T01:00:00+00:00",
            claims={},
        )


def _patch_gate(*, agent=None, vector=None, token=None):
    """Decorator-style helper so each test can opt in to the right mocks."""
    if agent is None:
        agent = {"id": "11111111-1111-1111-1111-111111111111", "name": "Test"}
    if vector is None:
        vector = _vector()
    if token is None:
        token = _FakeToken()
    return [
        patch("app.services.capability_gate.get_agent", return_value=agent),
        patch("app.services.capability_gate.compute_trust_vector", return_value=vector),
        patch("app.services.capability_gate.issue_capability_token", return_value=token),
    ]


# ──────────────────────────────────────────────────────────────────────
# Decision: allowed
# ──────────────────────────────────────────────────────────────────────

def test_high_trust_reversible_action_allowed():
    patches = _patch_gate(vector=_vector(code_task_reliability=0.9))
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="reversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "allowed"
    assert out["score"] == 0.9
    assert out["dimension"] == "code_task_reliability"
    assert out["token"] is not None
    assert out["token_hash"] is not None


def test_high_trust_irreversible_allowed_when_above_strict_threshold():
    patches = _patch_gate(vector=_vector(code_task_reliability=0.95))
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="irreversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "allowed"


# ──────────────────────────────────────────────────────────────────────
# Decision: denied / requires_human
# ──────────────────────────────────────────────────────────────────────

def test_low_trust_reversible_denied():
    patches = _patch_gate(vector=_vector(code_task_reliability=0.1))
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="reversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "denied"
    assert out["token"] is None


def test_low_trust_irreversible_escalates_to_human():
    """Below threshold + irreversible class => human review, not flat denial.
    This gives the operator a path; flat-deny is too brittle."""
    patches = _patch_gate(vector=_vector(code_task_reliability=0.1))
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="irreversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "requires_human"
    assert out["token"] is None


def test_unknown_agent_denied_cleanly():
    patches = [
        patch("app.services.capability_gate.get_agent", return_value=None),
        patch("app.services.capability_gate.compute_trust_vector"),
        patch("app.services.capability_gate.issue_capability_token"),
    ]
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="00000000-0000-0000-0000-000000000000",
            action_type="tool_call",
            side_effect_class="reversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "denied"
    assert out["token"] is None
    assert "not found" in out["reason"]


# ──────────────────────────────────────────────────────────────────────
# Dimension fallback
# ──────────────────────────────────────────────────────────────────────

def test_payment_action_falls_back_to_identity_assurance():
    """payment_dispute_rate is None for agents with no payment history.
    Gate should fall back to agent_identity_assurance, not crash."""
    patches = _patch_gate(vector=_vector(
        agent_identity_assurance=0.85,
        # payment_dispute_rate stays None from the helper
    ))
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="payment",
            side_effect_class="irreversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["dimension"] == "agent_identity_assurance"
    assert out["score"] == 0.85


def test_unknown_action_type_uses_identity_assurance_default():
    """If we add a new action_type and forget to map it, the gate should
    fall back to a sensible default rather than KeyError."""
    patches = _patch_gate()
    for p in patches: p.start()
    try:
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="some_new_unmapped_action",
            side_effect_class="reversible",
        )
    finally:
        for p in patches: p.stop()
    assert out["dimension"] == "agent_identity_assurance"


# ──────────────────────────────────────────────────────────────────────
# Threshold override
# ──────────────────────────────────────────────────────────────────────

def test_threshold_override_takes_precedence():
    """Org-level policy may want stricter thresholds than the defaults."""
    patches = _patch_gate(vector=_vector(code_task_reliability=0.5))
    for p in patches: p.start()
    try:
        # Default reversible threshold is 0.40 → 0.5 would normally pass.
        # Override to 0.6 → should now deny.
        out = evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="reversible",
            threshold_override=0.6,
        )
    finally:
        for p in patches: p.stop()
    assert out["decision"] == "denied"
    assert out["threshold"] == 0.6


# ──────────────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────────────

def test_invalid_side_effect_class_raises():
    with pytest.raises(GateError, match="Unknown side_effect_class"):
        evaluate_request(
            agent_id="11111111-1111-1111-1111-111111111111",
            action_type="tool_call",
            side_effect_class="explosive",
        )


# ──────────────────────────────────────────────────────────────────────
# Sanity on policy constants
# ──────────────────────────────────────────────────────────────────────

def test_threshold_table_covers_all_classes():
    assert set(DEFAULT_THRESHOLDS.keys()) == {"none", "reversible", "irreversible"}
    # Strictly increasing — irreversible needs the most trust
    assert DEFAULT_THRESHOLDS["none"] < DEFAULT_THRESHOLDS["reversible"] < DEFAULT_THRESHOLDS["irreversible"]


def test_action_dimension_map_only_uses_known_dimensions():
    """If we rename a Trust Vector dimension, this test catches the gate
    falling out of sync."""
    valid_dims = {
        "agent_identity_assurance",
        "code_task_reliability",
        "security_review_pass_rate",
        "reversible_action_success",
        "payment_dispute_rate",
        "human_override_rate",
        "recency_weighted_consistency",
    }
    for action, dim in ACTION_DIMENSION_MAP.items():
        assert dim in valid_dims, f"{action} maps to unknown dim {dim!r}"
