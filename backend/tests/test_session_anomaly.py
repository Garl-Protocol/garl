"""Session-level behavioral layer v0 — rule engine tests.

Covers, per rule: fires / does not fire (boundary cases), the signed alert
envelope (verifiable via app.core.signing.verify_signature), the 6h dedupe
window, the webhook dispatch payload, and the scope-escalation hook wired
into capability-token issuance (ValueError behavior must stay identical).

Supabase is mocked with a small routable fake (per-table handlers) following
the conftest / test_anchors_endpoint pattern.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.signing import get_public_key_hex, verify_signature
from app.services import session_anomaly as sa

AGENT = "11111111-1111-1111-1111-111111111111"


# ──────────────────────────────────────────────────────────────────────
# Routable Supabase fake
# ──────────────────────────────────────────────────────────────────────

class _FakeResult:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count if count is not None else len(data or [])


class _FakeQuery:
    _CHAIN = ("select", "eq", "gte", "lt", "gt", "is_", "limit", "order", "range", "in_")

    def __init__(self, sb, table_name):
        self._sb = sb
        self.table_name = table_name
        self.ops = []          # [(method, args, kwargs)]
        self._insert_payload = None

    def __getattr__(self, name):
        if name in _FakeQuery._CHAIN:
            def _op(*args, **kwargs):
                self.ops.append((name, args, kwargs))
                return self
            return _op
        raise AttributeError(name)

    def insert(self, payload):
        self._insert_payload = payload
        return self

    def execute(self):
        if self._insert_payload is not None:
            self._sb.inserts.setdefault(self.table_name, []).append(self._insert_payload)
            return _FakeResult([self._insert_payload])
        handler = self._sb.handlers.get(self.table_name)
        if handler is not None:
            return handler(self)
        return _FakeResult([])

    # test helpers
    def args_of(self, method):
        return [a for (m, a, _k) in self.ops if m == method]

    def has(self, method):
        return any(m == method for (m, _a, _k) in self.ops)


class FakeSupabase:
    def __init__(self, handlers=None):
        self.handlers = handlers or {}   # table -> callable(query) -> _FakeResult
        self.inserts = {}

    def table(self, name):
        return _FakeQuery(self, name)


def _tokens_handler(active_limits=None):
    """capability_tokens handler for the spend rule: returns active rows."""
    rows = [{"spend_limit_usd": lim} for lim in (active_limits or [])]
    return lambda q: _FakeResult(rows)


@pytest.fixture
def no_webhooks():
    with patch.object(sa, "_deliver_alert_webhooks") as m:
        yield m


def _patch_sb(sb):
    return patch.object(sa, "_get_supabase", return_value=sb)


def _receipt(cost=None, side_effect="none", tool_server=None):
    return {
        "receipt_id": str(_uuid.uuid4()),
        "action_type": "tool_call",
        "side_effect": side_effect,
        "tool_server": tool_server,
        "cost": cost,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


NOW = datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────
# spend_velocity
# ──────────────────────────────────────────────────────────────────────

class TestSpendVelocity:
    def _run(self, receipts, limits):
        sb = FakeSupabase({"capability_tokens": _tokens_handler(limits)})
        with _patch_sb(sb):
            alert = sa._rule_spend_velocity(sb, AGENT, receipts, NOW)
        return alert, sb

    def test_warning_at_exactly_80_percent(self, no_webhooks):
        alert, sb = self._run([_receipt(cost={"usd": 80.0})], [100.0])
        assert alert is not None
        assert alert["rule"] == "spend_velocity"
        assert alert["severity"] == "warning"
        assert alert["evidence"]["ratio"] == 0.8
        assert len(sb.inserts["session_alerts"]) == 1

    def test_exactly_100_percent_is_warning_not_critical(self, no_webhooks):
        alert, _ = self._run([_receipt(cost={"usd": 100.0})], [100.0])
        assert alert["severity"] == "warning"

    def test_critical_above_100_percent(self, no_webhooks):
        alert, _ = self._run([_receipt(cost={"usd": 150.0})], [100.0])
        assert alert["severity"] == "critical"

    def test_no_alert_below_80_percent(self, no_webhooks):
        alert, sb = self._run([_receipt(cost={"usd": 79.99})], [100.0])
        assert alert is None
        assert "session_alerts" not in sb.inserts

    def test_no_alert_without_active_spend_limit(self, no_webhooks):
        alert, _ = self._run([_receipt(cost={"usd": 9999.0})], [])
        assert alert is None

    def test_budget_is_largest_active_limit(self, no_webhooks):
        # $90 spend vs limits [50, 200] -> 45% of 200 -> no alert.
        alert, _ = self._run([_receipt(cost={"usd": 90.0})], [50.0, 200.0])
        assert alert is None

    def test_malformed_and_missing_costs_are_zero(self, no_webhooks):
        receipts = [
            _receipt(cost=None),
            _receipt(cost={}),
            _receipt(cost={"usd": None}),
            _receipt(cost={"usd": "not-a-number"}),
            _receipt(cost={"usd": True}),          # bool is not money
            _receipt(cost={"tokens_in": 5000}),    # partial cost, no usd
            _receipt(cost={"usd": 40.0}),
            _receipt(cost=40.0),                   # bare-number tolerated
        ]
        alert, _ = self._run(receipts, [100.0])
        assert alert is not None  # 80.0 total -> exactly 80%
        assert alert["evidence"]["window_spend_usd"] == 80.0


# ──────────────────────────────────────────────────────────────────────
# delegation_depth
# ──────────────────────────────────────────────────────────────────────

def _chain_tokens_handler(chain_rows, window_hashes):
    """chain_rows: {token_hash: parent_token_hash}. Window query (gte on
    issued_at) returns window_hashes rows; eq(token_hash) does chain lookups."""
    def handler(q):
        eq_args = q.args_of("eq")
        for (col, val) in eq_args:
            if col == "token_hash":
                if val in chain_rows:
                    return _FakeResult(
                        [{"token_hash": val, "parent_token_hash": chain_rows[val]}]
                    )
                return _FakeResult([])
        # window listing
        return _FakeResult(
            [
                {"token_hash": h, "parent_token_hash": chain_rows.get(h)}
                for h in window_hashes
            ]
        )
    return handler


def _mk_chain(n):
    """n tokens: t0 (root) <- t1 <- ... <- t(n-1). Returns (rows, leaf)."""
    hashes = [f"{i:02d}" * 32 for i in range(n)]
    rows = {hashes[0]: None}
    for i in range(1, n):
        rows[hashes[i]] = hashes[i - 1]
    return rows, hashes[-1]


class TestDelegationDepth:
    def _run(self, chain_rows, window_hashes):
        sb = FakeSupabase({"capability_tokens": _chain_tokens_handler(chain_rows, window_hashes)})
        with _patch_sb(sb):
            return sa._rule_delegation_depth(sb, AGENT, NOW)

    def test_depth_4_warning(self, no_webhooks):
        rows, leaf = _mk_chain(4)
        alert = self._run(rows, [leaf])
        assert alert is not None
        assert alert["rule"] == "delegation_depth"
        assert alert["severity"] == "warning"
        assert alert["evidence"]["max_depth"] == 4

    def test_depth_6_critical(self, no_webhooks):
        rows, leaf = _mk_chain(6)
        alert = self._run(rows, [leaf])
        assert alert["severity"] == "critical"
        assert alert["evidence"]["max_depth"] == 6

    def test_depth_3_no_alert(self, no_webhooks):
        rows, leaf = _mk_chain(3)
        assert self._run(rows, [leaf]) is None

    def test_no_tokens_in_window_no_alert(self, no_webhooks):
        assert self._run({}, []) is None

    def test_parent_cycle_terminates_without_alert(self, no_webhooks):
        a, b = "aa" * 32, "bb" * 32
        rows = {a: b, b: a}  # cycle
        assert self._run(rows, [a]) is None


# ──────────────────────────────────────────────────────────────────────
# novel_target
# ──────────────────────────────────────────────────────────────────────

class TestNovelTarget:
    def _run(self, window_receipts, history_targets):
        history = [{"tool_server": t} for t in history_targets]
        sb = FakeSupabase({"receipts": lambda q: _FakeResult(history)})
        with _patch_sb(sb):
            return sa._rule_novel_target(sb, AGENT, window_receipts, NOW)

    def test_irreversible_on_unseen_target_fires(self, no_webhooks):
        receipts = [_receipt(side_effect="irreversible", tool_server="pay.evil.example")]
        alert = self._run(receipts, ["github.com"])
        assert alert is not None
        assert alert["rule"] == "novel_target"
        assert alert["severity"] == "warning"
        assert alert["evidence"]["novel_targets"] == ["pay.evil.example"]

    def test_known_target_does_not_fire(self, no_webhooks):
        receipts = [_receipt(side_effect="irreversible", tool_server="github.com")]
        assert self._run(receipts, ["github.com"]) is None

    def test_reversible_on_unseen_target_does_not_fire(self, no_webhooks):
        receipts = [_receipt(side_effect="reversible", tool_server="new.example")]
        assert self._run(receipts, []) is None

    def test_irreversible_without_tool_server_does_not_fire(self, no_webhooks):
        receipts = [_receipt(side_effect="irreversible", tool_server=None)]
        assert self._run(receipts, []) is None


# ──────────────────────────────────────────────────────────────────────
# receipt_rate
# ──────────────────────────────────────────────────────────────────────

def _rate_handler(last_hour, last_week):
    """Two count queries hit receipts, distinguished by their gte cutoff:
    the 1h cutoff is more recent than the 7d cutoff."""
    def handler(q):
        gte_args = q.args_of("gte")
        assert gte_args, "expected a gte filter on the count query"
        cutoff = datetime.fromisoformat(gte_args[0][1].replace("Z", "+00:00"))
        if cutoff > datetime.now(timezone.utc) - timedelta(hours=2):
            return _FakeResult([], count=last_hour)
        return _FakeResult([], count=last_week)
    return handler


class TestReceiptRate:
    def _run(self, last_hour, last_week):
        sb = FakeSupabase({"receipts": _rate_handler(last_hour, last_week)})
        with _patch_sb(sb):
            return sa._rule_receipt_rate(sb, AGENT, NOW)

    def test_burst_from_quiet_baseline_fires(self, no_webhooks):
        # 25 in the last hour, only those 25 all week -> baseline 0.
        alert = self._run(25, 25)
        assert alert is not None
        assert alert["rule"] == "receipt_rate"
        assert alert["severity"] == "warning"
        assert alert["evidence"]["receipts_last_hour"] == 25

    def test_burst_over_10x_baseline_fires(self, no_webhooks):
        # baseline (192-25)/167 = 1/h; 25 > 10x1.
        alert = self._run(25, 192)
        assert alert is not None

    def test_steady_high_volume_does_not_fire(self, no_webhooks):
        # 25/h steadily all week: baseline 25/h -> 25 <= 250.
        assert self._run(25, 25 * 168) is None

    def test_below_min_count_never_fires(self, no_webhooks):
        assert self._run(19, 19) is None

    def test_exactly_min_count_with_zero_baseline_fires(self, no_webhooks):
        assert self._run(20, 20) is not None


# ──────────────────────────────────────────────────────────────────────
# Envelope + signature + dedupe + webhook payload
# ──────────────────────────────────────────────────────────────────────

class TestAlertEnvelope:
    def _mint(self, sb=None):
        sb = sb or FakeSupabase()
        with _patch_sb(sb), patch.object(sa, "_deliver_alert_webhooks"):
            env = sa.mint_session_alert(
                agent_id=AGENT,
                rule="spend_velocity",
                severity="warning",
                summary="test alert",
                evidence={"x": 1},
            )
        return env, sb

    def test_envelope_shape(self):
        env, sb = self._mint()
        assert env["version"] == "garl/session-alert/v0.1"
        assert env["issuer"] == "https://api.garl.ai"
        assert env["agent_identity"] == f"did:garl:{AGENT}"
        assert env["timestamp"].endswith("Z")
        _uuid.UUID(env["alert_id"])  # valid uuid
        assert env["window"]["hours"] == sa.WINDOW_HOURS
        row = sb.inserts["session_alerts"][0]
        assert row["envelope_json"] == env
        assert row["rule"] == "spend_velocity"
        assert row["severity"] == "warning"
        assert row["signature"] == env["signature"]
        assert row["verification_key_id"] == env["verification_key_id"]

    def test_signature_verifies_and_tamper_fails(self):
        env, _ = self._mint()
        payload = dict(env)
        sig = payload.pop("signature")
        payload.pop("verification_key_id")
        cert = {"payload": payload, "proof": {"publicKey": get_public_key_hex(), "signature": sig}}
        assert verify_signature(cert) is True
        tampered = dict(payload)
        tampered["summary"] = "innocent-looking summary"
        assert verify_signature({"payload": tampered, "proof": cert["proof"]}) is False

    def test_invalid_severity_rejected(self):
        with pytest.raises(ValueError):
            sa.mint_session_alert(
                agent_id=AGENT, rule="x", severity="apocalyptic",
                summary="s", evidence={},
            )

    def test_dedupe_suppresses_within_window(self):
        sb = FakeSupabase({"session_alerts": lambda q: _FakeResult([{"id": "existing"}])})
        with _patch_sb(sb), patch.object(sa, "_deliver_alert_webhooks") as hooks:
            env = sa.mint_session_alert(
                agent_id=AGENT, rule="spend_velocity", severity="warning",
                summary="dup", evidence={},
            )
        assert env is None
        assert "session_alerts" not in sb.inserts
        hooks.assert_not_called()

    def test_no_recent_alert_mints(self):
        sb = FakeSupabase({"session_alerts": lambda q: _FakeResult([])})
        env, sb2 = self._mint(sb)
        assert env is not None
        assert len(sb.inserts["session_alerts"]) == 1

    def test_webhook_dispatch_reuses_anomaly_event(self):
        sb = FakeSupabase()
        with _patch_sb(sb), patch("app.services.traces._fire_webhooks_with_retry") as fire:
            env = sa.mint_session_alert(
                agent_id=AGENT, rule="novel_target", severity="warning",
                summary="s", evidence={},
            )
        fire.assert_called_once()
        called_agent, payload = fire.call_args[0]
        assert called_agent == AGENT
        assert payload["event"] == "anomaly"          # existing webhook rail
        assert payload["type"] == "session_alert"     # discriminator vs legacy
        assert payload["alert"] == env


# ──────────────────────────────────────────────────────────────────────
# scope_escalation_attempt hook (capability-token issuance)
# ──────────────────────────────────────────────────────────────────────

PARENT_HASH = "ab" * 32


def _parent_claims(scope="payment:stripe.com"):
    import time as _time
    return {
        "iss": "https://api.garl.ai",
        "sub": f"did:garl:{AGENT}",
        "scope": scope,
        "side_effect_class": "reversible",
        "caveats": [],
        "exp": int(_time.time()) + 7200,
    }


class TestScopeEscalationHook:
    def _attempt(self, child_scope, hook_mock):
        from app.services.capability_tokens import issue_capability_token
        with patch("app.services.capability_tokens._load_parent_claims",
                   return_value=_parent_claims()), \
             patch("app.services.capability_tokens._persist_token", lambda **kw: None), \
             patch("app.services.session_anomaly.record_escalation_attempt", hook_mock):
            return issue_capability_token(
                agent_id=AGENT,
                scope=child_scope,
                side_effect_class="none",
                expires_in_seconds=60,
                parent_token_hash=PARENT_HASH,
            )

    def test_widening_child_raises_and_records_attempt(self):
        hook = MagicMock()
        with pytest.raises(ValueError) as exc:
            self._attempt("payment:*", hook)  # broader than payment:stripe.com
        assert "scope" in str(exc.value)
        hook.assert_called_once()
        kwargs = hook.call_args.kwargs
        assert kwargs["agent_id"] == AGENT
        assert kwargs["parent_hash"] == PARENT_HASH
        assert "scope" in kwargs["reason"]

    def test_valid_narrowing_child_does_not_record(self):
        hook = MagicMock()
        out = self._attempt("payment:stripe.com:charge", hook)
        assert out["token"].count(".") == 2
        hook.assert_not_called()

    def test_hook_failure_does_not_change_valueerror(self):
        hook = MagicMock(side_effect=RuntimeError("alert rail down"))
        with pytest.raises(ValueError):
            self._attempt("payment:*", hook)

    def test_record_escalation_attempt_never_raises(self):
        with patch.object(sa, "mint_session_alert", side_effect=RuntimeError("db down")):
            assert sa.record_escalation_attempt(AGENT, PARENT_HASH, "reason") is None

    def test_record_escalation_attempt_mints_critical_alert(self):
        sb = FakeSupabase()
        with _patch_sb(sb), patch.object(sa, "_deliver_alert_webhooks"):
            env = sa.record_escalation_attempt(AGENT, PARENT_HASH, "Child scope wider")
        assert env["rule"] == "scope_escalation_attempt"
        assert env["severity"] == "critical"
        assert env["evidence"]["parent_token_hash"] == PARENT_HASH
        assert env["evidence"]["reason"] == "Child scope wider"


# ──────────────────────────────────────────────────────────────────────
# run_session_scan
# ──────────────────────────────────────────────────────────────────────

class TestRunSessionScan:
    def test_single_agent_scan(self):
        with patch.object(sa, "scan_agent", return_value=[{"rule": "x"}]) as scan, \
             _patch_sb(FakeSupabase()):
            out = sa.run_session_scan(AGENT)
        scan.assert_called_once_with(AGENT)
        assert out == {"scanned": 1, "alerts": [{"rule": "x"}], "window_hours": sa.WINDOW_HOURS}

    def test_all_agents_scan_discovers_active(self):
        a2 = "22222222-2222-2222-2222-222222222222"
        sb = FakeSupabase({
            "receipts": lambda q: _FakeResult([{"agent_id": AGENT}, {"agent_id": AGENT}]),
            "capability_tokens": lambda q: _FakeResult([{"agent_id": a2}]),
        })
        with patch.object(sa, "scan_agent", return_value=[]) as scan, _patch_sb(sb):
            out = sa.run_session_scan()
        assert out["scanned"] == 2
        assert sorted(c.args[0] for c in scan.call_args_list) == sorted([AGENT, a2])

    def test_one_rule_failure_does_not_block_others(self, no_webhooks):
        sb = FakeSupabase({
            # receipts handler raises -> receipt_rate/novel_target degrade;
            # window fetch also raises, exercising scan_agent isolation.
            "receipts": lambda q: (_ for _ in ()).throw(RuntimeError("db blip")),
            "capability_tokens": lambda q: _FakeResult([]),
        })
        with _patch_sb(sb):
            # Must not raise even though every receipts query explodes.
            alerts = sa.scan_agent(AGENT)
        assert alerts == []
