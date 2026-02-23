"""
GARL Protocol v1.0 — Comprehensive tests for reputation.py module.

Tests five-dimensional reputation system, certification tiers, anomaly detection,
and time decay functions.
"""
import pytest
from app.services.reputation import (
    clamp_score,
    compute_success_rate,
    compute_certification_tier,
    compute_reliability_delta_ema,
    compute_security_score,
    compute_speed_score,
    compute_cost_score,
    compute_consistency_score,
    compute_composite_score,
    apply_time_decay,
    detect_anomalies,
    auto_clear_anomalies,
    compute_endorsement_bonus,
    project_decay,
    BASELINE,
    MAX_SCORE,
    MIN_SCORE,
    TIER_THRESHOLDS,
)


# --- clamp_score ---
class TestClampScore:
    """Score clamping function tests."""

    def test_normal_range(self):
        """Normal value like 50.0 should be returned unchanged."""
        assert clamp_score(50.0) == 50.0

    def test_below_min(self):
        """Values below 0 should be clamped to 0."""
        assert clamp_score(-10.0) == MIN_SCORE
        assert clamp_score(-100.0) == MIN_SCORE

    def test_above_max(self):
        """Values above 100 should be clamped to 100."""
        assert clamp_score(150.0) == MAX_SCORE
        assert clamp_score(100.1) == MAX_SCORE

    def test_boundary_values(self):
        """Boundary values 0 and 100 should be preserved."""
        assert clamp_score(0.0) == 0.0
        assert clamp_score(100.0) == 100.0

    def test_rounding(self):
        """Score should be rounded to 2 decimal places."""
        assert clamp_score(50.123) == 50.12


# --- compute_success_rate ---
class TestComputeSuccessRate:
    """Success rate calculation tests."""

    def test_zero_total(self):
        """Should return 0.0 when total is 0."""
        assert compute_success_rate(0, 0) == 0.0

    def test_full_success(self):
        """100% when all traces are successful."""
        assert compute_success_rate(10, 10) == 100.0

    def test_half_success(self):
        """Half success should be 50%."""
        assert compute_success_rate(5, 10) == 50.0

    def test_partial_success(self):
        """Partial success rate should be calculated correctly."""
        assert compute_success_rate(7, 10) == 70.0


# --- compute_certification_tier ---
class TestComputeCertificationTier:
    """Certification tier calculation tests."""

    def test_bronze(self):
        """Bronze tier for 0-40 range."""
        assert compute_certification_tier(0.0) == "bronze"
        assert compute_certification_tier(39.9) == "bronze"

    def test_silver(self):
        """Silver tier for 40-70 range."""
        assert compute_certification_tier(40.0) == "silver"
        assert compute_certification_tier(69.9) == "silver"

    def test_gold(self):
        """Gold tier for 70-90 range."""
        assert compute_certification_tier(70.0) == "gold"
        assert compute_certification_tier(89.9) == "gold"

    def test_enterprise_no_anomaly(self):
        """Enterprise with 90+ and zero anomalies."""
        assert compute_certification_tier(90.0) == "enterprise"
        assert compute_certification_tier(90.0, []) == "enterprise"

    def test_enterprise_with_active_anomaly_becomes_gold(self):
        """With active anomaly, enterprise is not granted even at 90+, becomes gold."""
        anomaly = [{"type": "test", "archived": False}]
        assert compute_certification_tier(95.0, anomaly) == "gold"

    def test_enterprise_with_archived_anomaly(self):
        """Archived anomaly does not block enterprise."""
        anomaly = [{"type": "test", "archived": True}]
        assert compute_certification_tier(92.0, anomaly) == "enterprise"


# --- compute_reliability_delta_ema ---
class TestComputeReliabilityDeltaEma:
    """Reliability EMA calculation tests."""

    def test_success(self):
        """Successful trace should produce positive delta."""
        delta, new_score, new_ema = compute_reliability_delta_ema(
            50.0, 50.0, "success", 0
        )
        assert delta > 0
        assert new_score > 50.0

    def test_failure(self):
        """Failed trace should produce negative delta."""
        delta, new_score, new_ema = compute_reliability_delta_ema(
            50.0, 50.0, "failure", 0
        )
        assert delta < 0
        assert new_score < 50.0

    def test_partial(self):
        """Partial success should produce small positive delta."""
        delta, new_score, new_ema = compute_reliability_delta_ema(
            50.0, 50.0, "partial", 0
        )
        assert delta > 0
        assert delta < 2.0

    def test_streak_bonus(self):
        """Consecutive successes should add bonus."""
        delta_single, _, _ = compute_reliability_delta_ema(50.0, 50.0, "success", 1)
        delta_streak, _, _ = compute_reliability_delta_ema(50.0, 50.0, "success", 5)
        assert delta_streak > delta_single

    def test_diminishing_returns_high_score(self):
        """At 80+ score, positive delta should decrease with diminishing returns."""
        delta_low, _, _ = compute_reliability_delta_ema(50.0, 50.0, "success", 1)
        delta_high, _, _ = compute_reliability_delta_ema(85.0, 85.0, "success", 1)
        assert delta_high < delta_low

    def test_diminishing_penalty_low_score(self):
        """Below 20 score, negative penalty should be mitigated."""
        _, score_low, _ = compute_reliability_delta_ema(10.0, 10.0, "failure", 0)
        _, score_mid, _ = compute_reliability_delta_ema(50.0, 50.0, "failure", 0)
        # Penalty at low score should be lighter (clamped to 0)
        assert score_low >= MIN_SCORE


# --- compute_security_score ---
class TestComputeSecurityScore:
    """Security score calculation tests."""

    def test_safe_tools(self):
        """Successful trace with safe tools should get bonus."""
        score, _ = compute_security_score(
            50.0, 50.0, "success",
            [{"name": "search"}], ["search"], ["search"],
            False, None, 10
        )
        assert score > 50.0

    def test_dangerous_tools(self):
        """High-risk tools should incur penalty."""
        score, _ = compute_security_score(
            50.0, 50.0, "success",
            [{"name": "shell_exec"}, {"name": "file_delete"}],
            ["shell_exec", "file_delete"], ["shell_exec", "file_delete"],
            False, None, 10
        )
        assert score < 50.0

    def test_pii_mask_bonus(self):
        """PII masking should provide bonus."""
        score_no_mask, _ = compute_security_score(
            50.0, 50.0, "success", [], [], [], False, None, 10
        )
        score_mask, _ = compute_security_score(
            50.0, 50.0, "success", [], [], [], True, None, 10
        )
        assert score_mask > score_no_mask

    def test_prompt_injection_penalty(self):
        """Prompt injection detection should incur serious penalty (score drops)."""
        score, _ = compute_security_score(
            50.0, 50.0, "success",
            [], [], [],
            False, {"prompt_injection_detected": True}, 10
        )
        assert score < 50.0

    def test_permission_discipline_undeclared(self):
        """Undeclared permission usage should incur penalty (3+ undeclared)."""
        score, _ = compute_security_score(
            50.0, 50.0, "success",
            [], ["file_read", "secret_a", "secret_b", "secret_c"], ["file_read"],
            False, None, 10
        )
        assert score < 50.0

    def test_first_5_trace_dampening(self):
        """Dampening should be applied for first 5 traces."""
        score_early, _ = compute_security_score(
            50.0, 50.0, "success", [], [], [], False, None, 3
        )
        score_late, _ = compute_security_score(
            50.0, 50.0, "success", [], [], [], False, None, 20
        )
        assert abs(score_early - 50.0) < abs(score_late - 50.0)


# --- compute_speed_score ---
class TestComputeSpeedScore:
    """Speed score calculation tests."""

    def test_fast(self):
        """Trace faster than half of benchmark should get bonus."""
        benchmark = 10000  # coding
        score, _ = compute_speed_score(
            50.0, 50.0, benchmark // 2, "coding", 10
        )
        assert score > 50.0

    def test_slow(self):
        """Trace slower than 2x benchmark should incur penalty."""
        benchmark = 10000
        score, _ = compute_speed_score(
            50.0, 50.0, benchmark * 3, "coding", 10
        )
        assert score < 50.0

    def test_dampening_first_5(self):
        """Delta is halved for first 5 traces."""
        score_early, _ = compute_speed_score(50.0, 50.0, 1000, "coding", 2)
        score_late, _ = compute_speed_score(50.0, 50.0, 1000, "coding", 20)
        assert abs(score_early - 50.0) < abs(score_late - 50.0)


# --- compute_cost_score ---
class TestComputeCostScore:
    """Cost efficiency score tests."""

    def test_cheap(self):
        """Trace cheaper than half of benchmark should get bonus."""
        score, _ = compute_cost_score(50.0, 50.0, 0.02, "coding", 10)
        assert score > 50.0

    def test_expensive(self):
        """Trace more expensive than 2x benchmark should incur penalty."""
        score, _ = compute_cost_score(50.0, 50.0, 0.15, "coding", 10)
        assert score < 50.0

    def test_zero_cost(self):
        """Zero cost should not change score."""
        score, ema = compute_cost_score(50.0, 50.0, 0.0, "coding", 10)
        assert score == 50.0
        assert ema == 50.0


# --- compute_consistency_score ---
class TestComputeConsistencyScore:
    """Consistency score tests."""

    def test_insufficient_data(self):
        """Should return current score with fewer than 3 deltas."""
        assert compute_consistency_score(55.0, [1.0, 2.0]) == 55.0

    def test_low_variance(self):
        """Low standard deviation should bring bonus."""
        score = compute_consistency_score(50.0, [0.1, 0.2, 0.15, 0.12])
        assert score > 50.0

    def test_high_variance(self):
        """High standard deviation should incur penalty."""
        score = compute_consistency_score(50.0, [5.0, -5.0, 10.0, -8.0])
        assert score < 50.0


# --- compute_composite_score ---
class TestComputeCompositeScore:
    """Composite score calculation tests."""

    def test_all_dimensions_baseline(self):
        """If all dimensions are baseline, composite should also be baseline."""
        dims = {
            "reliability": BASELINE,
            "security": BASELINE,
            "speed": BASELINE,
            "cost_efficiency": BASELINE,
            "consistency": BASELINE,
        }
        assert compute_composite_score(dims) == BASELINE

    def test_weighted_average(self):
        """Weighted average should be calculated correctly."""
        dims = {
            "reliability": 80.0,
            "security": 60.0,
            "speed": 70.0,
            "cost_efficiency": 50.0,
            "consistency": 90.0,
        }
        # 0.30*80 + 0.20*60 + 0.15*70 + 0.10*50 + 0.25*90 = 24+12+10.5+5+22.5 = 74
        score = compute_composite_score(dims)
        assert 73.0 < score < 75.0

    def test_missing_dimension_baseline(self):
        """Missing dimensions should be filled with baseline."""
        dims = {"reliability": 100.0}
        score = compute_composite_score(dims)
        assert score > BASELINE
        assert score <= MAX_SCORE


# --- apply_time_decay ---
class TestApplyTimeDecay:
    """Time decay tests."""

    def test_zero_hours(self):
        """Score should not change with 0 hours."""
        assert apply_time_decay(70.0, 0) == 70.0

    def test_negative_hours(self):
        """Negative hours should not change score."""
        assert apply_time_decay(70.0, -10) == 70.0

    def test_short_duration(self):
        """Short duration should bring less decay."""
        original = 80.0
        decayed = apply_time_decay(original, 24)  # 1 day
        assert decayed < original
        assert decayed > BASELINE

    def test_long_duration(self):
        """Long duration should bring more decay."""
        day1 = apply_time_decay(80.0, 24)
        day30 = apply_time_decay(80.0, 30 * 24)
        assert day30 < day1
        assert day30 >= BASELINE

    def test_baseline_unchanged(self):
        """Baseline score does not decay."""
        assert apply_time_decay(BASELINE, 1000) == BASELINE


# --- detect_anomalies ---
class TestDetectAnomalies:
    """Anomaly detection tests."""

    def test_few_traces_no_anomaly(self):
        """No anomaly detected with fewer than 10 traces."""
        agent = {"total_traces": 5, "success_rate": 95}
        assert detect_anomalies(agent, "failure", 100, 0.1) == []

    def test_unexpected_failure(self):
        """Unexpected failure anomaly for agent with 90%+ success rate."""
        agent = {"total_traces": 20, "success_rate": 95}
        flags = detect_anomalies(agent, "failure", 1000, 0.05)
        assert any(f["type"] == "unexpected_failure" for f in flags)

    def test_duration_spike(self):
        """Duration anomaly at 5x average duration."""
        agent = {"total_traces": 20, "success_rate": 80, "avg_duration_ms": 1000}
        flags = detect_anomalies(agent, "success", 6000, 0.05)
        assert any(f["type"] == "duration_spike" for f in flags)

    def test_cost_spike(self):
        """Cost anomaly at 10x average cost."""
        agent = {"total_traces": 20, "success_rate": 80, "total_cost_usd": 0.20}
        # Average cost = 0.20/20 = 0.01, 10x = 0.10
        flags = detect_anomalies(agent, "success", 1000, 0.15)
        assert any(f["type"] == "cost_spike" for f in flags)


# --- auto_clear_anomalies ---
class TestAutoClearAnomalies:
    """Automatic anomaly archiving tests."""

    def test_insufficient_clean_traces(self):
        """No archiving with fewer than 50 consecutive clean traces."""
        flags = [{"type": "test", "severity": "warning", "archived": False}]
        result = auto_clear_anomalies(flags, 30)
        assert all(not f.get("archived") for f in result if "archived" in f)

    def test_warning_archived(self):
        """Warning level is archived after 50+ clean traces."""
        flags = [{"type": "test", "severity": "warning"}]
        result = auto_clear_anomalies(flags, 50)
        assert len(result) > 0
        archived = [f for f in result if f.get("archived")]
        assert len(archived) > 0

    def test_critical_not_archived(self):
        """Critical level anomalies are not archived."""
        flags = [{"type": "cost_spike", "severity": "critical"}]
        result = auto_clear_anomalies(flags, 100)
        assert not any(f.get("archived") for f in result)


# --- compute_endorsement_bonus ---
class TestComputeEndorsementBonus:
    """Endorsement bonus calculation tests."""

    def test_insufficient_traces_zero(self):
        """Bonus is 0 with fewer than 10 traces."""
        assert compute_endorsement_bonus(80.0, 5, "gold") == 0.0

    def test_low_score_zero(self):
        """Bonus is 0 with score below 60."""
        assert compute_endorsement_bonus(50.0, 50, "gold") == 0.0

    def test_bronze_multiplier(self):
        """Bronze tier has low multiplier."""
        bonus_bronze = compute_endorsement_bonus(80.0, 100, "bronze")
        bonus_gold = compute_endorsement_bonus(80.0, 100, "gold")
        assert bonus_gold > bonus_bronze

    def test_silver_multiplier(self):
        """Silver tier has higher multiplier than bronze."""
        bonus_silver = compute_endorsement_bonus(80.0, 100, "silver")
        bonus_bronze = compute_endorsement_bonus(80.0, 100, "bronze")
        assert bonus_silver > bonus_bronze

    def test_gold_enterprise_10x(self):
        """Gold and Enterprise have same bonus with 10x multiplier."""
        bonus_gold = compute_endorsement_bonus(80.0, 100, "gold")
        bonus_enterprise = compute_endorsement_bonus(80.0, 100, "enterprise")
        assert bonus_gold == bonus_enterprise
        assert bonus_gold > 0


# --- project_decay ---
class TestProjectDecay:
    """Decay projection tests."""

    def test_day_list(self):
        """Returns projection for given days."""
        result = project_decay(70.0, [7, 30, 60, 90])
        assert len(result) == 4
        assert result[0]["days"] == 7
        assert result[0]["projected_score"] < 70.0
        assert result[3]["days"] == 90
        assert result[3]["projected_score"] < result[0]["projected_score"]

    def test_empty_list(self):
        """Empty list returns empty result."""
        assert project_decay(70.0, []) == []
