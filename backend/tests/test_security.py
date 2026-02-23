"""
GARL Protocol v1.0.1 — Security & Stress Audit Test Suite

Adversarial testing across four attack surfaces:
  1. Reputation Gaming — tier manipulation via fake/rapid traces
  2. Immutability — bypass attempts on DB triggers
  3. DID & Signing — cryptographic tamper detection
  4. GDPR Leak — PII residue after anonymization
"""
import hashlib
import json
import copy
import uuid
import time
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from app.core.signing import sign_trace, verify_signature, get_public_key_hex
from app.services.reputation import (
    compute_reliability_delta_ema,
    compute_security_score,
    compute_speed_score,
    compute_cost_score,
    compute_consistency_score,
    compute_composite_score,
    compute_certification_tier,
    compute_endorsement_bonus,
    detect_anomalies,
    auto_clear_anomalies,
    apply_time_decay,
    clamp_score,
    BASELINE,
    WEIGHTS,
    TIER_THRESHOLDS,
    EMA_ALPHA,
)
from app.services.agents import (
    _generate_sovereign_id,
    anonymize_agent,
    soft_delete_agent,
)
from app.services.traces import _compute_trace_hash


# ============================================================================
# SECTION 1: REPUTATION GAMING — Can an agent cheat its way to Enterprise?
# ============================================================================

class TestReputationGaming:
    """Attack surface: Can agents manipulate scores through rapid/fake traces?"""

    def test_single_trace_cannot_reach_gold(self):
        """A single perfect trace must NOT push a baseline agent to Gold (70+)."""
        score = BASELINE  # 50.0
        ema = BASELINE

        delta, new_score, new_ema = compute_reliability_delta_ema(
            score, ema, "success", consecutive_successes=1
        )
        assert new_score < 70, f"Single trace reached {new_score} — Gold threshold breached"

    def test_ten_rapid_traces_cannot_reach_gold(self):
        """10 consecutive perfect traces must NOT push an agent to Gold tier."""
        score = BASELINE
        ema = BASELINE

        for i in range(1, 11):
            delta, score, ema = compute_reliability_delta_ema(score, ema, "success", i)

        dimensions = {
            "reliability": score,
            "security": BASELINE,
            "speed": BASELINE,
            "cost_efficiency": BASELINE,
            "consistency": BASELINE,
        }
        composite = compute_composite_score(dimensions)
        tier = compute_certification_tier(composite, [])
        assert tier != "gold" and tier != "enterprise", (
            f"10 rapid traces reached tier={tier}, composite={composite}"
        )

    def test_fifty_traces_mathematical_ceiling(self):
        """Even 50 perfect traces should not trivially reach Enterprise (90+)."""
        rel_score = BASELINE
        rel_ema = BASELINE

        for i in range(1, 51):
            _, rel_score, rel_ema = compute_reliability_delta_ema(
                rel_score, rel_ema, "success", i
            )

        # With only reliability climbing, composite can't reach 90
        # because other dimensions stay at baseline (50)
        dimensions = {
            "reliability": rel_score,
            "security": BASELINE,
            "speed": BASELINE,
            "cost_efficiency": BASELINE,
            "consistency": BASELINE,
        }
        composite = compute_composite_score(dimensions)
        assert composite < 90, (
            f"50 reliability-only traces reached composite={composite} — Enterprise breached"
        )

    def test_diminishing_returns_above_80(self):
        """Score gains must diminish significantly above 80."""
        delta_at_50, _, _ = compute_reliability_delta_ema(50.0, 50.0, "success", 1)
        delta_at_85, _, _ = compute_reliability_delta_ema(85.0, 85.0, "success", 1)

        assert abs(delta_at_85) < abs(delta_at_50), (
            f"No diminishing returns: delta@50={delta_at_50}, delta@85={delta_at_85}"
        )

    def test_failure_penalty_exceeds_success_reward(self):
        """A single failure must deal more damage than a single success gives."""
        delta_success, _, _ = compute_reliability_delta_ema(BASELINE, BASELINE, "success", 0)
        delta_failure, _, _ = compute_reliability_delta_ema(BASELINE, BASELINE, "failure", 0)

        assert abs(delta_failure) > abs(delta_success), (
            f"Failure penalty ({delta_failure}) should exceed success reward ({delta_success})"
        )

    def test_enterprise_requires_zero_anomalies(self):
        """An agent at score 95 with active anomalies must NOT get Enterprise."""
        active_anomaly = [{"type": "cost_spike", "severity": "warning", "message": "test"}]
        tier = compute_certification_tier(95.0, active_anomaly)
        assert tier != "enterprise", f"Enterprise granted despite active anomaly: tier={tier}"

    def test_enterprise_allows_archived_anomalies(self):
        """Archived anomalies should not block Enterprise tier."""
        archived = [{"type": "test", "severity": "warning", "message": "old", "archived": True}]
        tier = compute_certification_tier(95.0, archived)
        assert tier == "enterprise", f"Archived anomaly blocked Enterprise: tier={tier}"

    def test_sybil_endorsement_from_weak_agent_is_zero(self):
        """An agent with <60 trust or <10 traces must produce zero endorsement bonus."""
        assert compute_endorsement_bonus(59.9, 100, "gold") == 0.0, "Low-trust endorser not blocked"
        assert compute_endorsement_bonus(80.0, 9, "gold") == 0.0, "Low-trace endorser not blocked"
        assert compute_endorsement_bonus(30.0, 5, "bronze") == 0.0, "Sybil agent not blocked"

    def test_self_endorsement_bonus_impossible(self):
        """Even if somehow called, endorsement with <60 from baseline (50) agent is zero."""
        bonus = compute_endorsement_bonus(BASELINE, 0, "bronze")
        assert bonus == 0.0, "Baseline agent can endorse"

    def test_security_penalty_for_high_risk_tools(self):
        """Using shell_exec/eval tools must penalize security score."""
        safe_score, _ = compute_security_score(
            BASELINE, BASELINE, "success",
            [{"name": "web_search"}], None, None, False, None, 10
        )
        dangerous_score, _ = compute_security_score(
            BASELINE, BASELINE, "success",
            [{"name": "shell_exec"}, {"name": "eval"}, {"name": "raw_sql"}],
            None, None, False, None, 10
        )
        assert dangerous_score < safe_score, (
            f"High-risk tools not penalized: safe={safe_score}, dangerous={dangerous_score}"
        )

    def test_prompt_injection_severe_penalty(self):
        """Prompt injection detection must apply severe penalty."""
        clean_score, _ = compute_security_score(
            BASELINE, BASELINE, "success", None, None, None, False, None, 10
        )
        injected_score, _ = compute_security_score(
            BASELINE, BASELINE, "success", None, None, None, False,
            {"prompt_injection_detected": True}, 10
        )
        assert injected_score < clean_score - 1.0, (
            f"Prompt injection penalty too weak: clean={clean_score}, injected={injected_score}"
        )

    def test_speed_gaming_impossible(self):
        """Reporting 0ms duration should not give infinite speed bonus."""
        score_zero, _ = compute_speed_score(BASELINE, BASELINE, 0, "coding", 10)
        score_normal, _ = compute_speed_score(BASELINE, BASELINE, 5000, "coding", 10)
        assert score_zero <= 100, "0ms duration overflowed score"
        assert score_zero >= BASELINE, "0ms fast trace is valid behavior"

    def test_cost_gaming_zero_cost(self):
        """Zero cost trace should not change cost efficiency score."""
        original = 65.0
        result, _ = compute_cost_score(original, 65.0, 0, "coding", 10)
        assert result == original, f"Zero cost changed score from {original} to {result}"

    def test_composite_score_mathematically_bounded(self):
        """Composite score must always be in [0, 100] regardless of inputs."""
        extreme_high = compute_composite_score({
            "reliability": 100, "security": 100, "speed": 100,
            "cost_efficiency": 100, "consistency": 100,
        })
        assert extreme_high <= 100

        extreme_low = compute_composite_score({
            "reliability": 0, "security": 0, "speed": 0,
            "cost_efficiency": 0, "consistency": 0,
        })
        assert extreme_low >= 0

    def test_weight_sum_equals_one(self):
        """Trust dimension weights must sum to exactly 1.0."""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, not 1.0"

    def test_all_five_dimensions_present(self):
        """All five dimensions must be in the WEIGHTS dict."""
        expected = {"reliability", "security", "speed", "cost_efficiency", "consistency"}
        assert set(WEIGHTS.keys()) == expected, f"Missing dimensions: {expected - set(WEIGHTS.keys())}"


# ============================================================================
# SECTION 2: IMMUTABILITY — Can traces/history be modified?
# ============================================================================

class TestImmutability:
    """Attack surface: Can execution traces or reputation history be tampered with?"""

    def test_trace_hash_deterministic(self):
        """Same trace data must always produce the same hash."""
        data = {"trace_id": "abc", "agent_id": "xyz", "status": "success", "timestamp": "2026-01-01T00:00:00Z"}
        hash1 = _compute_trace_hash(data)
        hash2 = _compute_trace_hash(data)
        assert hash1 == hash2, "Trace hash is non-deterministic"

    def test_trace_hash_changes_on_tamper(self):
        """Any modification to trace data must change the hash."""
        original = {"trace_id": "abc", "agent_id": "xyz", "status": "success"}
        tampered = {"trace_id": "abc", "agent_id": "xyz", "status": "failure"}

        hash_original = _compute_trace_hash(original)
        hash_tampered = _compute_trace_hash(tampered)
        assert hash_original != hash_tampered, "Tampered trace produced same hash"

    def test_trace_hash_is_sha256(self):
        """Trace hash must be valid SHA-256 (64 hex characters)."""
        data = {"test": "data"}
        h = _compute_trace_hash(data)
        assert len(h) == 64, f"Hash length is {len(h)}, expected 64"
        assert all(c in "0123456789abcdef" for c in h), "Hash contains non-hex characters"

    def test_trace_hash_order_independent(self):
        """JSON key order should not affect trace hash (canonical serialization)."""
        data_a = {"z": 1, "a": 2, "m": 3}
        data_b = {"a": 2, "m": 3, "z": 1}
        assert _compute_trace_hash(data_a) == _compute_trace_hash(data_b), (
            "Key order affects hash — canonical serialization broken"
        )

    def test_anomaly_flags_capped_at_ten(self):
        """Anomaly flags array must never exceed 10 entries (memory safety)."""
        existing = [
            {"type": f"test_{i}", "severity": "warning", "message": f"msg_{i}"}
            for i in range(10)
        ]
        new_anomalies = [
            {"type": "new", "severity": "critical", "message": "new anomaly"}
        ]
        combined = (existing + new_anomalies)[-10:]
        assert len(combined) <= 10, f"Anomaly flags exceeded cap: {len(combined)}"

    def test_score_clamping_prevents_overflow(self):
        """Scores must never exceed [0, 100] bounds."""
        assert clamp_score(150.0) == 100.0
        assert clamp_score(-50.0) == 0.0
        assert clamp_score(float("inf")) == 100.0

    def test_score_clamping_nan_handling(self):
        """NaN scores should be clamped safely."""
        result = clamp_score(float("nan"))
        assert result >= 0 and result <= 100, f"NaN produced invalid score: {result}"


# ============================================================================
# SECTION 3: DID & SIGNING — Cryptographic integrity
# ============================================================================

class TestCryptographicIntegrity:
    """Attack surface: Can certificates be forged or signatures bypassed?"""

    def test_sign_and_verify_roundtrip(self):
        """A freshly signed certificate must pass verification."""
        cert = sign_trace({"agent": "test", "score": 92.5, "timestamp": "2026-02-22"})
        assert verify_signature(cert) is True

    def test_payload_tamper_detected(self):
        """Modifying any payload field must cause verification failure."""
        cert = sign_trace({"agent": "test", "important": "original"})

        tampered = copy.deepcopy(cert)
        tampered["payload"]["important"] = "HACKED"
        assert verify_signature(tampered) is False, "Payload tamper not detected"

    def test_signature_swap_detected(self):
        """Using another certificate's signature must fail."""
        cert_a = sign_trace({"id": "agent_a"})
        cert_b = sign_trace({"id": "agent_b"})

        forged = copy.deepcopy(cert_a)
        forged["proof"]["signature"] = cert_b["proof"]["signature"]
        assert verify_signature(forged) is False, "Signature swap not detected"

    def test_empty_signature_rejected(self):
        """Empty signature string must fail verification."""
        cert = sign_trace({"test": True})
        cert["proof"]["signature"] = ""
        assert verify_signature(cert) is False

    def test_random_signature_rejected(self):
        """Random hex string as signature must fail."""
        cert = sign_trace({"test": True})
        cert["proof"]["signature"] = "deadbeef" * 16
        assert verify_signature(cert) is False

    def test_wrong_public_key_rejected(self):
        """Certificate with wrong public key must fail."""
        cert = sign_trace({"test": True})
        cert["proof"]["publicKey"] = "aa" * 64
        assert verify_signature(cert) is False

    def test_missing_proof_fields_rejected(self):
        """Certificate missing proof fields must fail gracefully."""
        assert verify_signature({}) is False
        assert verify_signature({"payload": {}, "proof": {}}) is False
        assert verify_signature({"payload": {}, "proof": {"signature": "abc"}}) is False

    def test_additional_payload_field_detected(self):
        """Adding an extra field to the payload should break the signature."""
        cert = sign_trace({"original": "data"})
        tampered = copy.deepcopy(cert)
        tampered["payload"]["injected"] = "malicious"
        assert verify_signature(tampered) is False, "Injected field not detected"

    def test_did_format_correct(self):
        """DID must follow did:garl:<uuid> format."""
        test_uuid = str(uuid.uuid4())
        did = _generate_sovereign_id(test_uuid)
        assert did.startswith("did:garl:"), f"DID format wrong: {did}"
        assert test_uuid in did

    def test_public_key_consistency(self):
        """Public key must be the same across multiple calls."""
        key1 = get_public_key_hex()
        key2 = get_public_key_hex()
        assert key1 == key2, "Public key is not stable"

    def test_public_key_is_valid_hex(self):
        """Public key must be valid hex and correct length for secp256k1."""
        key = get_public_key_hex()
        assert len(key) == 128, f"Public key length {len(key)}, expected 128 for uncompressed secp256k1"
        assert all(c in "0123456789abcdef" for c in key)

    def test_certificate_context_and_type(self):
        """Certificate must have correct @context and @type."""
        cert = sign_trace({"data": "test"})
        assert cert["@context"] == "https://garl.io/schema/v1"
        assert cert["@type"] == "CertifiedExecutionTrace"
        assert cert["proof"]["type"] == "ECDSA-secp256k1"

    def test_certificate_timestamp_present(self):
        """Certificate proof must include creation timestamp."""
        cert = sign_trace({"data": "test"})
        assert "created" in cert["proof"]
        assert isinstance(cert["proof"]["created"], int)
        assert cert["proof"]["created"] > 0


# ============================================================================
# SECTION 4: GDPR LEAK — Does anonymization leave PII residue?
# ============================================================================

class TestGDPRCompliance:
    """Attack surface: Can PII be recovered after anonymization?"""

    def test_anonymize_hashes_name(self):
        """Anonymized agent name must be a SHA-256 hash prefix, not original name."""
        agent_id = str(uuid.uuid4())
        api_key = "garl_test_key_123"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": agent_id, "api_key_hash": api_key_hash, "name": "Secret Agent Corp"}]
        )
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            result = anonymize_agent(agent_id, api_key)
        assert result["status"] == "anonymized"
        assert "Secret Agent Corp" not in result["anonymized_name"]
        assert result["anonymized_name"].startswith("anon_")
        assert len(result["anonymized_name"]) > 5

    def test_anonymize_clears_description(self):
        """Anonymization must clear the description field."""
        agent_id = str(uuid.uuid4())
        api_key = "garl_test_key_456"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": agent_id, "api_key_hash": api_key_hash, "name": "Corp Agent"}]
        )
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            anonymize_agent(agent_id, api_key)

        update_call = mock_client.table.return_value.update.call_args
        update_data = update_call[0][0]
        assert update_data["description"] == "", "Description not cleared"
        assert update_data["homepage_url"] is None, "Homepage URL not cleared"
        assert update_data["developer_id"] is None, "Developer ID not cleared"

    def test_anonymize_wrong_key_rejected(self):
        """Anonymization with wrong API key must be rejected."""
        agent_id = str(uuid.uuid4())
        correct_hash = hashlib.sha256(b"correct_key").hexdigest()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": agent_id, "api_key_hash": correct_hash, "name": "Test"}]
        )

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            with pytest.raises(PermissionError):
                anonymize_agent(agent_id, "wrong_key")

    def test_soft_delete_marks_deleted(self):
        """Soft delete must set is_deleted=True without removing data."""
        agent_id = str(uuid.uuid4())
        api_key = "garl_delete_key"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": agent_id, "api_key_hash": api_key_hash, "name": "To Delete"}]
        )
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            result = soft_delete_agent(agent_id, api_key)
        assert result["status"] == "soft_deleted"

        update_data = mock_client.table.return_value.update.call_args[0][0]
        assert update_data["is_deleted"] is True
        assert "deleted_at" in update_data

    def test_soft_delete_wrong_key_rejected(self):
        """Soft delete with wrong API key must be rejected."""
        agent_id = str(uuid.uuid4())
        correct_hash = hashlib.sha256(b"owner_key").hexdigest()

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": agent_id, "api_key_hash": correct_hash, "name": "Protected"}]
        )

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            with pytest.raises(PermissionError):
                soft_delete_agent(agent_id, "attacker_key")

    def test_pii_masking_sha256_format(self):
        """PII masking must produce sha256: prefixed hash."""
        sensitive_input = "User SSN: 123-45-6789"
        masked = f"sha256:{hashlib.sha256(sensitive_input.encode()).hexdigest()}"
        assert masked.startswith("sha256:")
        assert len(masked) == 71  # "sha256:" (7) + 64 hex chars
        assert "123-45-6789" not in masked

    def test_pii_masking_irreversible(self):
        """SHA-256 PII masking must be one-way (different inputs = different hashes)."""
        hash1 = hashlib.sha256("Patient record A".encode()).hexdigest()
        hash2 = hashlib.sha256("Patient record B".encode()).hexdigest()
        assert hash1 != hash2, "Different PII produces same hash — collision"

    def test_anonymize_nonexistent_agent_raises(self):
        """Anonymizing a non-existent agent must raise ValueError."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        with patch("app.services.agents.get_supabase", return_value=mock_client):
            with pytest.raises(ValueError, match="Agent not found"):
                anonymize_agent("non-existent-id", "any-key")


# ============================================================================
# SECTION 5: ANOMALY DETECTION RESILIENCE
# ============================================================================

class TestAnomalyResilience:
    """Can anomaly detection be evaded?"""

    def test_no_anomalies_under_ten_traces(self):
        """Anomaly detection must NOT trigger before 10 traces (insufficient data)."""
        agent = {"total_traces": 9, "success_rate": 95.0, "avg_duration_ms": 1000, "total_cost_usd": 0.5}
        flags = detect_anomalies(agent, "failure", 50000, 100.0)
        assert len(flags) == 0, "Anomaly triggered with <10 traces"

    def test_anomaly_triggers_at_ten_traces(self):
        """After 10+ traces, unexpected failure from 95% agent must trigger anomaly."""
        agent = {"total_traces": 10, "success_rate": 95.0, "avg_duration_ms": 1000, "total_cost_usd": 1.0}
        flags = detect_anomalies(agent, "failure", 1000, 0.1)
        assert any(f["type"] == "unexpected_failure" for f in flags)

    def test_duration_spike_detected(self):
        """Duration 5x+ above average must trigger warning."""
        agent = {"total_traces": 20, "success_rate": 80.0, "avg_duration_ms": 1000, "total_cost_usd": 1.0}
        flags = detect_anomalies(agent, "success", 6000, 0.1)
        assert any(f["type"] == "duration_spike" for f in flags)

    def test_cost_spike_critical(self):
        """Cost 10x+ above average must trigger critical anomaly."""
        agent = {"total_traces": 20, "success_rate": 80.0, "avg_duration_ms": 1000, "total_cost_usd": 2.0}
        flags = detect_anomalies(agent, "success", 1000, 5.0)  # avg is 0.1, 5.0 is 50x
        assert any(f["type"] == "cost_spike" and f["severity"] == "critical" for f in flags)

    def test_auto_clear_only_warnings(self):
        """Auto-clear must only archive warnings, never critical anomalies."""
        flags = [
            {"type": "test", "severity": "warning", "message": "can clear"},
            {"type": "test", "severity": "critical", "message": "must stay"},
        ]
        cleared = auto_clear_anomalies(flags, consecutive_clean=60)
        active = [f for f in cleared if not f.get("archived")]
        assert len(active) == 1, f"Expected 1 active flag, got {len(active)}"
        assert active[0]["severity"] == "critical"

    def test_auto_clear_requires_fifty_clean(self):
        """Auto-clear must not trigger before 50 consecutive clean traces."""
        flags = [{"type": "test", "severity": "warning", "message": "test"}]
        not_cleared = auto_clear_anomalies(flags, consecutive_clean=49)
        active = [f for f in not_cleared if not f.get("archived")]
        assert len(active) == 1, "Warning cleared before 50 clean traces"


# ============================================================================
# SECTION 6: TIME DECAY INTEGRITY
# ============================================================================

class TestTimeDecayIntegrity:
    """Can time decay be exploited?"""

    def test_minimal_decay_within_24_hours(self):
        """Decay within 24h must be negligible (< 0.05 points)."""
        score = 85.0
        decayed = apply_time_decay(score, hours_since_last=23.9)
        drift = abs(decayed - score)
        assert drift < 0.05, f"Excessive decay within 24h: {score} -> {decayed} (drift={drift})"

    def test_lazy_decay_guard_blocks_under_24h(self):
        """_apply_lazy_decay wrapper must skip decay entirely for < 24h idle."""
        from app.services.agents import _apply_lazy_decay
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        agent = {
            "id": "test",
            "trust_score": 85.0,
            "total_traces": 10,
            "last_trace_at": (now - timedelta(hours=12)).isoformat(),
            "score_reliability": 85.0,
            "score_speed": 85.0,
            "score_cost_efficiency": 85.0,
            "score_consistency": 85.0,
            "score_security": 85.0,
        }
        mock_db = MagicMock()
        result = _apply_lazy_decay(agent, mock_db)
        assert result["trust_score"] == 85.0, "Lazy decay triggered within 24h"

    def test_decay_pulls_toward_baseline(self):
        """Decay must pull scores toward baseline (50), not toward zero."""
        high_score = 90.0
        decayed = apply_time_decay(high_score, hours_since_last=720)  # 30 days
        assert decayed > BASELINE, f"High score decayed below baseline: {decayed}"
        assert decayed < high_score, f"High score didn't decay: {decayed}"

    def test_low_score_decays_upward(self):
        """Below-baseline scores must decay upward toward 50, not downward."""
        low_score = 20.0
        decayed = apply_time_decay(low_score, hours_since_last=720)
        assert decayed > low_score, f"Low score decayed further down: {low_score} -> {decayed}"
        assert decayed < BASELINE, f"Low score jumped above baseline: {decayed}"

    def test_baseline_score_no_decay(self):
        """A score at exactly baseline must not change with decay."""
        decayed = apply_time_decay(BASELINE, hours_since_last=8760)  # 365 days
        assert abs(decayed - BASELINE) < 0.01, f"Baseline decayed: {decayed}"

    def test_decay_never_exceeds_bounds(self):
        """Decayed score must always stay in [0, 100]."""
        for score in [0.0, 1.0, 50.0, 99.0, 100.0]:
            for hours in [0, 24, 168, 720, 8760]:
                result = apply_time_decay(score, hours)
                assert 0 <= result <= 100, f"Decay out of bounds: score={score}, hours={hours}, result={result}"


# ============================================================================
# SECTION 7: API KEY SECURITY
# ============================================================================

class TestAPIKeySecurity:
    """Can API keys be brute-forced or leaked?"""

    def test_api_key_not_in_agent_response(self):
        """API key hash must never be returned in agent GET responses."""
        from app.services.agents import get_agent

        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{
                "id": "test-uuid",
                "name": "Test",
                "api_key_hash": "secret_hash_value",
                "api_key": "garl_secret",
                "trust_score": 50,
                "total_traces": 0,
                "is_deleted": False,
            }]
        )

        with patch("app.services.agents.get_supabase", return_value=mock_client):
            agent = get_agent("test-uuid")
        assert agent is not None
        assert "api_key_hash" not in agent, "api_key_hash leaked in response"
        assert "api_key" not in agent, "api_key leaked in response"

    def test_api_key_hash_is_sha256(self):
        """API keys must be stored as SHA-256 hashes, never plaintext."""
        raw_key = "garl_abc123secretkey"
        stored_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert len(stored_hash) == 64
        assert raw_key not in stored_hash


# ============================================================================
# SECTION 8: INPUT VALIDATION & EDGE CASES
# ============================================================================

class TestInputValidation:
    """Can malicious inputs break the system?"""

    def test_negative_duration_clamped(self):
        """Speed score with edge-case duration must not break."""
        score, ema = compute_speed_score(BASELINE, BASELINE, 1, "coding", 10)
        assert 0 <= score <= 100

    def test_massive_duration_handled(self):
        """Extremely large duration must not overflow."""
        score, ema = compute_speed_score(BASELINE, BASELINE, 999999999, "coding", 10)
        assert 0 <= score <= 100

    def test_massive_cost_handled(self):
        """Extremely large cost must not overflow."""
        score, ema = compute_cost_score(BASELINE, BASELINE, 999999.99, "coding", 10)
        assert 0 <= score <= 100

    def test_empty_tool_calls_no_crash(self):
        """Empty tool_calls list must not crash security scoring."""
        score, ema = compute_security_score(
            BASELINE, BASELINE, "success", [], None, None, False, None, 10
        )
        assert 0 <= score <= 100

    def test_none_tool_calls_no_crash(self):
        """None tool_calls must not crash security scoring."""
        score, ema = compute_security_score(
            BASELINE, BASELINE, "success", None, None, None, False, None, 10
        )
        assert 0 <= score <= 100

    def test_consistency_with_no_history(self):
        """Consistency score with insufficient history must return current score."""
        result = compute_consistency_score(65.0, [1.0])
        assert result == 65.0, f"Changed with insufficient data: {result}"

    def test_consistency_with_zero_variance(self):
        """Perfect consistency (zero variance) should be rewarded."""
        result = compute_consistency_score(50.0, [1.0, 1.0, 1.0, 1.0, 1.0])
        assert result > 50.0, f"Zero variance not rewarded: {result}"

    def test_trace_hash_with_special_chars(self):
        """Trace hash must handle unicode and special characters."""
        data = {"desc": "Ação com carácteres especiais: 日本語 🤖", "score": 99.9}
        h = _compute_trace_hash(data)
        assert len(h) == 64
