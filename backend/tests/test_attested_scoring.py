"""P2.8 Trust Vector honesty — self-reported vs attested evidence.

Bare self-reported traces must never lift an agent above the neutral
baseline (50). Only attested evidence (witnessed traces, qualified
endorsements) unlocks above-baseline headroom, and endorsements get
anti-farming controls (write rate tier + per-source daily cap).

Spec: protocol/spec/trust-vector-v0.1.md §4a.
"""
import hashlib
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.reputation import (
    BASELINE,
    MAX_SCORE,
    apply_attestation_cap,
    compute_attested_uplift,
    compute_effective_max_score,
    compute_evidence_summary,
)


# --- Formula units -----------------------------------------------------------

class TestAttestedUplift:
    def test_zero_evidence_zero_uplift(self):
        assert compute_attested_uplift(0, 0, 0) == 0.0
        assert compute_attested_uplift(0, 0, 10_000) == 0.0

    def test_small_agent_full_headroom_at_min_evidence(self):
        # <= 50 traces: ATTESTED_MIN_EVIDENCE (5) items unlock everything.
        assert compute_attested_uplift(5, 0, 50) == 1.0
        assert compute_attested_uplift(3, 2, 10) == 1.0

    def test_progressive_headroom(self):
        assert compute_attested_uplift(1, 0, 10) == pytest.approx(0.2)
        assert compute_attested_uplift(3, 0, 10) == pytest.approx(0.6)

    def test_volume_cannot_dilute_requirement(self):
        # 5 attested out of 1000 traces: required = 100 -> uplift 0.05.
        assert compute_attested_uplift(5, 0, 1000) == pytest.approx(0.05)

    def test_qualified_endorsements_count_as_evidence(self):
        assert compute_attested_uplift(0, 5, 20) == 1.0

    def test_none_and_negative_inputs_are_safe(self):
        assert compute_attested_uplift(None, None, None) == 0.0
        assert compute_attested_uplift(-3, -1, 10) == 0.0


class TestEffectiveMaxScore:
    def test_no_evidence_caps_at_baseline(self):
        assert compute_effective_max_score(0, 0, 500) == BASELINE

    def test_full_evidence_unlocks_max(self):
        assert compute_effective_max_score(5, 0, 20) == MAX_SCORE

    def test_partial_evidence_partial_headroom(self):
        # 1 attested / small agent -> 50 + 50*0.2 = 60
        assert compute_effective_max_score(1, 0, 10) == 60.0
        # 5 attested / 1000 traces -> 50 + 50*0.05 = 52.5
        assert compute_effective_max_score(5, 0, 1000) == 52.5


class TestApplyAttestationCap:
    def test_self_reported_only_clamped_to_baseline(self):
        # No matter how high the raw composite, zero evidence -> 50.
        assert apply_attestation_cap(95.0, 0, 0, 10_000) == BASELINE
        assert apply_attestation_cap(50.01, 0, 0, 1) == BASELINE

    def test_below_baseline_never_capped(self):
        # Bad behavior always counts — penalties pass through untouched.
        assert apply_attestation_cap(30.0, 0, 0, 100) == 30.0
        assert apply_attestation_cap(0.0, 0, 0, 100) == 0.0

    def test_exactly_baseline_unchanged(self):
        assert apply_attestation_cap(50.0, 0, 0, 100) == 50.0

    def test_full_evidence_no_cap(self):
        assert apply_attestation_cap(92.5, 5, 0, 20) == 92.5

    def test_partial_evidence_partial_cap(self):
        assert apply_attestation_cap(80.0, 1, 0, 10) == 60.0
        assert apply_attestation_cap(55.0, 1, 0, 10) == 55.0


class TestEvidenceSummary:
    def test_missing_columns_default_to_zero(self):
        # Pre-v23-migration rows have no counters: must not crash, cap engaged.
        s = compute_evidence_summary({"total_traces": 42})
        assert s["attested_traces"] == 0
        assert s["qualified_endorsements"] == 0
        assert s["self_reported_only"] is True
        assert s["effective_max_score"] == BASELINE

    def test_null_columns_default_to_zero(self):
        s = compute_evidence_summary({
            "total_traces": 10,
            "attested_trace_count": None,
            "qualified_endorsement_count": None,
        })
        assert s["self_reported_only"] is True

    def test_ratio_and_flags(self):
        s = compute_evidence_summary({
            "total_traces": 20,
            "attested_trace_count": 5,
            "qualified_endorsement_count": 2,
        })
        assert s["total_traces"] == 20
        assert s["attested_traces"] == 5
        assert s["attested_ratio"] == 0.25
        assert s["self_reported_only"] is False
        assert s["effective_max_score"] == MAX_SCORE

    def test_zero_traces_ratio_zero(self):
        s = compute_evidence_summary({})
        assert s["attested_ratio"] == 0.0


# --- submit_trace integration (mocked Supabase) ------------------------------

API_KEY = "test-api-key"
AGENT_ID = "11111111-1111-1111-1111-111111111111"


def _agent_row(**overrides) -> dict:
    """A dict-shaped agents row with dimensions high enough that the OLD
    behavior would have pushed the composite well above 50."""
    base = {
        "id": AGENT_ID,
        "name": "CapTest",
        "is_deleted": False,
        "api_key_hash": hashlib.sha256(API_KEY.encode()).hexdigest(),
        "total_traces": 30,
        "success_count": 30,
        "consecutive_successes": 30,
        "success_rate": 100.0,
        "trust_score": 80.0,
        "certification_tier": "silver",
        "score_reliability": 85.0,
        "score_security": 80.0,
        "score_speed": 80.0,
        "score_cost_efficiency": 80.0,
        "score_consistency": 80.0,
        "ema_reliability": 85.0,
        "ema_security": 80.0,
        "ema_speed": 80.0,
        "ema_cost_efficiency": 80.0,
        "endorsement_score": 0,
        "endorsement_count": 0,
        "anomaly_flags": [],
        "avg_duration_ms": 1000,
        "total_cost_usd": 0.0,
        "permissions_declared": None,
        "attested_trace_count": 0,
        "qualified_endorsement_count": 0,
    }
    base.update(overrides)
    return base


def _make_db(agent_row: dict):
    """Chainable Supabase mock with persistent per-table mocks so update
    payloads can be inspected."""
    db = MagicMock()
    tables: dict[str, MagicMock] = {}

    def table(name):
        if name in tables:
            return tables[name]
        t = MagicMock()
        res = MagicMock()
        res.data = []
        res.count = 0
        for m in ("select", "eq", "insert", "update", "order", "limit",
                  "range", "in_", "or_", "gt", "gte", "lt", "lte"):
            getattr(t, m).return_value = t
        t.execute.return_value = res
        if name == "agents":
            res.data = [agent_row]
        tables[name] = t
        return t

    db.table.side_effect = table
    return db, tables


def _submit(agent_row, attestations=None):
    from app.models.schemas import TraceSubmitRequest
    from app.services import traces as traces_mod

    db, tables = _make_db(agent_row)
    req = TraceSubmitRequest(
        agent_id=AGENT_ID,
        task_description="do the thing",
        status="success",
        duration_ms=2000,
        category="coding",
        attestations=attestations,
    )
    with patch("app.services.traces.get_supabase", return_value=db), \
         patch("app.services.monthly_cap.enforce_monthly_cap"), \
         patch("app.services.action_receipts.mint_receipt_for_trace"), \
         patch.object(traces_mod, "_fire_webhooks_with_retry"):
        traces_mod.submit_trace(req, API_KEY)

    # The agents-table update payload
    update_payload = tables["agents"].update.call_args[0][0]
    return update_payload


class TestSubmitTraceNeutralCap:
    def test_self_reported_success_streak_cannot_exceed_baseline(self):
        payload = _submit(_agent_row())
        assert payload["trust_score"] <= BASELINE
        assert payload["attested_trace_count"] == 0

    def test_witnessed_attestation_unlocks_headroom_and_increments_counter(self):
        att = [{
            "type": "github-check-run",
            "repo": "acme/widgets",
            "commit_sha": "a" * 40,
            "conclusion": "success",
        }]
        with patch(
            "app.core.github_attest.verify_check_run",
            side_effect=lambda a, **kw: {**a, "witnessed": True},
        ):
            payload = _submit(_agent_row(attested_trace_count=4), attestations=att)
        # 4 prior + this witnessed trace = 5 -> full headroom for a small agent
        assert payload["attested_trace_count"] == 5
        assert payload["trust_score"] > BASELINE

    def test_unwitnessed_attestation_stays_self_reported(self):
        att = [{
            "type": "github-check-run",
            "repo": "acme/widgets",
            "commit_sha": "b" * 40,
            "conclusion": "success",
        }]
        # verify_check_run fails open (no stamp) when re-checking is disabled.
        payload = _submit(_agent_row(), attestations=att)
        assert payload["attested_trace_count"] == 0
        assert payload["trust_score"] <= BASELINE

    def test_failures_push_below_baseline_uncapped(self):
        from app.models.schemas import TraceSubmitRequest
        from app.services import traces as traces_mod

        agent = _agent_row(
            score_reliability=40.0, score_security=40.0, score_speed=40.0,
            score_cost_efficiency=40.0, score_consistency=40.0,
            ema_reliability=40.0, ema_security=40.0, ema_speed=40.0,
            ema_cost_efficiency=40.0,
            success_count=10, consecutive_successes=0, trust_score=40.0,
        )
        db, tables = _make_db(agent)
        req = TraceSubmitRequest(
            agent_id=AGENT_ID, task_description="broke it",
            status="failure", duration_ms=50000, category="coding",
        )
        with patch("app.services.traces.get_supabase", return_value=db), \
             patch("app.services.monthly_cap.enforce_monthly_cap"), \
             patch("app.services.action_receipts.mint_receipt_for_trace"), \
             patch.object(traces_mod, "_fire_webhooks_with_retry"):
            traces_mod.submit_trace(req, API_KEY)
        payload = tables["agents"].update.call_args[0][0]
        assert payload["trust_score"] < 40.0

    def test_pre_migration_row_without_counter_column_still_works(self):
        # Row lacks the v23 columns entirely: no crash, and the update payload
        # must NOT write the missing column (would 500 against a pre-v23 DB).
        row = _agent_row()
        del row["attested_trace_count"]
        del row["qualified_endorsement_count"]
        payload = _submit(row)
        assert "attested_trace_count" not in payload
        assert payload["trust_score"] <= BASELINE


# --- Endorsement anti-farming (mocked Supabase) ------------------------------

ENDORSER_ID = "22222222-2222-2222-2222-222222222222"
TARGET_ID = "33333333-3333-3333-3333-333333333333"
ENDORSER_KEY = "endorser-key"


def _endorsement_db(endorser, target, daily_rows):
    """agents table returns endorser then target; endorsements table returns
    [] for the pairwise dedupe query, then daily_rows for the 24h-cap query."""
    db = MagicMock()
    tables = {}

    agents_results = [MagicMock(data=[endorser]), MagicMock(data=[target])]
    endorsement_results = [MagicMock(data=[]), MagicMock(data=daily_rows), MagicMock(data=[])]

    def table(name):
        if name in tables:
            return tables[name]
        t = MagicMock()
        for m in ("select", "eq", "insert", "update", "order", "limit", "gte"):
            getattr(t, m).return_value = t
        if name == "agents":
            t.execute.side_effect = list(agents_results) + [MagicMock(data=[])] * 5
        elif name == "endorsements":
            t.execute.side_effect = endorsement_results
        else:
            t.execute.return_value = MagicMock(data=[])
        tables[name] = t
        return t

    db.table.side_effect = table
    return db, tables


def _endorser_row(**overrides):
    base = {
        "id": ENDORSER_ID,
        "api_key_hash": hashlib.sha256(ENDORSER_KEY.encode()).hexdigest(),
        "trust_score": 80.0,
        "total_traces": 100,
        "certification_tier": "gold",
    }
    base.update(overrides)
    return base


def _target_row(**overrides):
    base = {
        "id": TARGET_ID,
        "trust_score": 50.0,
        "total_traces": 20,
        "endorsement_score": 0.0,
        "endorsement_count": 0,
        "qualified_endorsement_count": 0,
        "attested_trace_count": 0,
        "anomaly_flags": [],
    }
    base.update(overrides)
    return base


class TestEndorsementAntiFarming:
    def _create(self, endorser, target, daily_rows):
        from app.services.agents import create_endorsement
        db, tables = _endorsement_db(endorser, target, daily_rows)
        with patch("app.services.agents.get_supabase", return_value=db):
            result = create_endorsement(ENDORSER_ID, TARGET_ID, "solid work", ENDORSER_KEY)
        return result, tables

    def test_daily_cap_blocks_sixth_endorsement(self):
        from app.services.agents import ENDORSEMENT_DAILY_CAP, create_endorsement
        daily = [{"id": str(uuid.uuid4())} for _ in range(ENDORSEMENT_DAILY_CAP)]
        db, _ = _endorsement_db(_endorser_row(), _target_row(), daily)
        with patch("app.services.agents.get_supabase", return_value=db):
            with pytest.raises(ValueError, match="daily limit"):
                create_endorsement(ENDORSER_ID, TARGET_ID, "spam", ENDORSER_KEY)

    def test_under_daily_cap_allowed(self):
        daily = [{"id": str(uuid.uuid4())} for _ in range(4)]
        result, _ = self._create(_endorser_row(), _target_row(), daily)
        assert result["bonus_applied"] > 0

    def test_qualified_endorsement_increments_both_counters(self):
        result, tables = self._create(_endorser_row(), _target_row(), [])
        assert result["qualified"] is True
        payload = tables["agents"].update.call_args[0][0]
        assert payload["endorsement_count"] == 1
        assert payload["qualified_endorsement_count"] == 1

    def test_unqualified_endorsement_raw_only(self):
        # Weak endorser (score < 60): bonus 0 -> raw count moves, qualified doesn't.
        weak = _endorser_row(trust_score=55.0, certification_tier="silver")
        result, tables = self._create(weak, _target_row(), [])
        assert result["bonus_applied"] == 0.0
        assert result["qualified"] is False
        payload = tables["agents"].update.call_args[0][0]
        assert payload["endorsement_count"] == 1
        assert payload["qualified_endorsement_count"] == 0
        assert payload["trust_score"] == 50.0

    def test_endorsement_capped_by_evidence_headroom(self):
        # Target already at the ceiling its evidence allows (1 qualified
        # endorsement -> effective max 60): the bonus cannot push past it.
        target = _target_row(trust_score=60.0, total_traces=10)
        result, tables = self._create(_endorser_row(), target, [])
        payload = tables["agents"].update.call_args[0][0]
        assert payload["trust_score"] == 60.0

    def test_pre_migration_target_without_column_not_written(self):
        target = _target_row()
        del target["qualified_endorsement_count"]
        del target["attested_trace_count"]
        result, tables = self._create(_endorser_row(), target, [])
        payload = tables["agents"].update.call_args[0][0]
        assert "qualified_endorsement_count" not in payload


# --- Trust vector / scorecard / profile exposure -----------------------------

class TestEvidenceExposure:
    def test_trust_vector_has_evidence_block(self):
        from app.services.trust_vector import compute_trust_vector
        v = compute_trust_vector({
            "id": AGENT_ID,
            "total_traces": 40,
            "attested_trace_count": 10,
            "qualified_endorsement_count": 2,
        })
        ev = v["evidence"]
        assert ev["total_traces"] == 40
        assert ev["attested_traces"] == 10
        assert ev["attested_ratio"] == 0.25
        assert ev["self_reported_only"] is False

    def test_trust_vector_third_party_count_matches_spec(self):
        from app.services.trust_vector import compute_trust_vector
        v = compute_trust_vector({
            "id": AGENT_ID,
            "endorsement_count": 50,          # raw, farmable — must NOT count
            "qualified_endorsement_count": 2,
            "attested_trace_count": 3,
        })
        assert v["counters"]["third_party_attestation_count"] == 5

    def test_scorecard_capped_and_has_evidence(self):
        from app.services.agents import generate_scorecard
        agent = {
            "id": AGENT_ID, "name": "CapTest",
            "score_reliability": 90, "score_security": 90, "score_speed": 90,
            "score_cost_efficiency": 90, "score_consistency": 90,
            "total_traces": 100,
        }
        card = generate_scorecard(agent)
        # Raw weighted composite would be 90; no attested evidence -> 50.
        assert card["composite_score"] == BASELINE
        assert card["evidence"]["self_reported_only"] is True

    def test_scorecard_uncapped_with_evidence(self):
        from app.services.agents import generate_scorecard
        agent = {
            "id": AGENT_ID, "name": "CapTest",
            "score_reliability": 90, "score_security": 90, "score_speed": 90,
            "score_cost_efficiency": 90, "score_consistency": 90,
            "total_traces": 100,
            "attested_trace_count": 10,
            "qualified_endorsement_count": 0,
        }
        card = generate_scorecard(agent)
        assert card["composite_score"] == 90.0
        assert card["evidence"]["attested_ratio"] == 0.1


# --- Route-level: rate tier + profile evidence -------------------------------

class TestEndorseRouteRateTier:
    def test_endorse_uses_write_tier(self, mock_supabase_for_routes):
        from fastapi.testclient import TestClient
        from app.main import app

        with patch("app.api.routes._check_rate_limit") as rl:
            client = TestClient(app)
            client.post(
                "/api/v1/endorse",
                json={"target_agent_id": TARGET_ID, "context": "x"},
                headers={"x-api-key": "some-key"},
            )
            assert rl.called
            args, kwargs = rl.call_args
            assert "write" in args or kwargs.get("tier") == "write"
