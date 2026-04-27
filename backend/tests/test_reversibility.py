"""Reversibility primitives — state machine + policy tests.

Mocks Supabase to test the state transitions and policy refusals without
needing a live DB. The DB row shapes match the v18 migration (compensations
+ receipts tables).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.reversibility import (
    VALID_STATUSES,
    ReversibilityError,
    mark_compensation_result,
    record_compensation,
    trigger_undo,
)


# ──────────────────────────────────────────────────────────────────────
# Supabase double — minimal fluent-builder shape
# ──────────────────────────────────────────────────────────────────────

class _FluentResult:
    def __init__(self, data):
        self.data = data


class _FluentBuilder:
    """Stand-in for the supabase-py builder. Records the call chain so
    tests can assert which table/operation was hit, and returns the
    canned data the test specifies."""

    def __init__(self, data=None):
        self._data = data or []
        self.last_table = None
        self.last_op = None
        self.last_filter = {}
        self.last_update = None
        self.last_insert = None

    def table(self, name):
        self.last_table = name
        return self

    def select(self, *_):
        self.last_op = "select"
        return self

    def insert(self, payload):
        self.last_op = "insert"
        self.last_insert = payload
        # For insert, return the inserted row(s) so caller can read .data[0].
        return _ChainedExec(self, [payload] if isinstance(payload, dict) else list(payload))

    def update(self, payload):
        self.last_op = "update"
        self.last_update = payload
        return self

    def eq(self, col, value):
        self.last_filter[col] = value
        return self

    def order(self, *_, **_kw):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return _FluentResult(self._data)


class _ChainedExec:
    def __init__(self, parent, data):
        self._parent = parent
        self._data = data

    def execute(self):
        return _FluentResult(self._data)


def _patched_supabase(builder):
    return patch("app.services.reversibility._get_supabase", return_value=builder)


# ──────────────────────────────────────────────────────────────────────
# record_compensation
# ──────────────────────────────────────────────────────────────────────

def test_record_compensation_inserts_with_recorded_status():
    sb = _FluentBuilder()
    with _patched_supabase(sb):
        out = record_compensation(
            receipt_id="11111111-1111-1111-1111-111111111111",
            agent_id="22222222-2222-2222-2222-222222222222",
            undo_payload={"action": "calendly:cancel", "event_id": "ev_42"},
            reason="recorded-at-receipt-time",
        )
    assert sb.last_table == "compensations"
    assert sb.last_op == "insert"
    assert sb.last_insert["status"] == "recorded"
    assert sb.last_insert["receipt_id"] == "11111111-1111-1111-1111-111111111111"
    assert sb.last_insert["undo_payload"] == {"action": "calendly:cancel", "event_id": "ev_42"}
    assert out["status"] == "recorded"


# ──────────────────────────────────────────────────────────────────────
# trigger_undo — happy path
# ──────────────────────────────────────────────────────────────────────

def test_trigger_undo_for_reversible_receipt_with_recorded_compensation():
    """Walk the full path: receipt is reversible, compensation is recorded
    → trigger flips status to pending and returns the undo_payload."""
    receipt_id = "11111111-1111-1111-1111-111111111111"
    payload = {"action": "calendly:cancel", "event_id": "ev_42"}
    rcpt_data = [{"side_effect": "reversible"}]
    comp_data = [{
        "id": "33333333-3333-3333-3333-333333333333",
        "receipt_id": receipt_id,
        "status": "recorded",
        "undo_payload": payload,
    }]

    # Two-stage builder — first .select() resolves to receipts, second to
    # compensations. We approximate by switching the data based on the
    # first table name seen.
    sb = MagicMock()
    rcpt_chain = MagicMock()
    rcpt_chain.execute.return_value = _FluentResult(rcpt_data)
    comp_chain = MagicMock()
    comp_chain.execute.return_value = _FluentResult(comp_data)
    update_chain = MagicMock()
    update_chain.execute.return_value = _FluentResult([])
    sb.table.side_effect = lambda name: {
        "receipts": _RcptStub(rcpt_chain),
        "compensations": _CompStub(comp_chain, update_chain),
    }[name]

    with patch("app.services.reversibility._get_supabase", return_value=sb):
        out = trigger_undo(receipt_id, "consumer-initiated-undo")
    assert out["status"] == "pending"
    assert out["undo_payload"] == payload
    assert out["compensation_id"] == "33333333-3333-3333-3333-333333333333"


# Helper stubs — minimal what the service does in order
class _RcptStub:
    def __init__(self, chain):
        self.chain = chain
    def select(self, *_):
        return self
    def eq(self, *_, **__):
        return self
    def limit(self, *_):
        return self
    def execute(self):
        return self.chain.execute()


class _CompStub:
    def __init__(self, select_chain, update_chain):
        self.select_chain = select_chain
        self.update_chain = update_chain
    def select(self, *_):
        return self
    def eq(self, *_, **__):
        return self
    def order(self, *_, **__):
        return self
    def limit(self, *_):
        return self
    def execute(self):
        return self.select_chain.execute()
    def update(self, *_):
        return self
    def in_(self, *_, **__):
        return self


# ──────────────────────────────────────────────────────────────────────
# trigger_undo — refusals
# ──────────────────────────────────────────────────────────────────────

def test_trigger_undo_refuses_irreversible_receipt():
    receipt_id = "11111111-1111-1111-1111-111111111111"
    rcpt_data = [{"side_effect": "irreversible"}]

    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult(rcpt_data))))
    sb.table.return_value = rcpt_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        with pytest.raises(ReversibilityError, match="irreversible"):
            trigger_undo(receipt_id, "consumer-initiated-undo")


def test_trigger_undo_refuses_no_side_effect_receipt():
    """Read-only actions don't need undo. Refuse cleanly so callers don't
    confuse a no-op with a failure."""
    receipt_id = "11111111-1111-1111-1111-111111111111"
    rcpt_data = [{"side_effect": "none"}]

    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult(rcpt_data))))
    sb.table.return_value = rcpt_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        with pytest.raises(ReversibilityError, match="no side effect"):
            trigger_undo(receipt_id, "consumer-initiated-undo")


def test_trigger_undo_refuses_when_receipt_missing():
    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult([]))))
    sb.table.return_value = rcpt_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        with pytest.raises(ReversibilityError, match="not found"):
            trigger_undo("11111111-1111-1111-1111-111111111111", "x")


def test_trigger_undo_refuses_when_no_compensation_recorded():
    """Reversible receipt but no compensation row — agent never recorded
    an undo action at submit time."""
    receipt_id = "11111111-1111-1111-1111-111111111111"
    rcpt_data = [{"side_effect": "reversible"}]
    comp_data = []

    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult(rcpt_data))))
    comp_stub = _CompStub(
        select_chain=MagicMock(execute=MagicMock(return_value=_FluentResult(comp_data))),
        update_chain=MagicMock(execute=MagicMock(return_value=_FluentResult([]))),
    )
    sb.table.side_effect = lambda name: rcpt_stub if name == "receipts" else comp_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        with pytest.raises(ReversibilityError, match="No compensation"):
            trigger_undo(receipt_id, "x")


def test_trigger_undo_refuses_when_already_succeeded():
    receipt_id = "11111111-1111-1111-1111-111111111111"
    rcpt_data = [{"side_effect": "reversible"}]
    comp_data = [{
        "id": "33333333-3333-3333-3333-333333333333",
        "status": "succeeded",
        "undo_payload": {},
    }]

    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult(rcpt_data))))
    comp_stub = _CompStub(
        select_chain=MagicMock(execute=MagicMock(return_value=_FluentResult(comp_data))),
        update_chain=MagicMock(execute=MagicMock(return_value=_FluentResult([]))),
    )
    sb.table.side_effect = lambda name: rcpt_stub if name == "receipts" else comp_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        with pytest.raises(ReversibilityError, match="Already undone"):
            trigger_undo(receipt_id, "x")


def test_trigger_undo_idempotent_when_already_pending():
    """Two callers race to undo. The second should get the same payload
    rather than a 409 — UETA consumer flow needs to be poll-safe."""
    receipt_id = "11111111-1111-1111-1111-111111111111"
    rcpt_data = [{"side_effect": "reversible"}]
    payload = {"action": "stripe:refund", "charge_id": "ch_123"}
    comp_data = [{
        "id": "33333333-3333-3333-3333-333333333333",
        "status": "pending",
        "undo_payload": payload,
    }]

    sb = MagicMock()
    rcpt_stub = _RcptStub(MagicMock(execute=MagicMock(return_value=_FluentResult(rcpt_data))))
    comp_stub = _CompStub(
        select_chain=MagicMock(execute=MagicMock(return_value=_FluentResult(comp_data))),
        update_chain=MagicMock(execute=MagicMock(return_value=_FluentResult([]))),
    )
    sb.table.side_effect = lambda name: rcpt_stub if name == "receipts" else comp_stub
    with patch("app.services.reversibility._get_supabase", return_value=sb):
        out = trigger_undo(receipt_id, "x")
    assert out["status"] == "pending"
    assert out["undo_payload"] == payload


# ──────────────────────────────────────────────────────────────────────
# mark_compensation_result
# ──────────────────────────────────────────────────────────────────────

def test_mark_result_succeeded_accepts():
    sb = _FluentBuilder()
    with _patched_supabase(sb):
        mark_compensation_result("33333333-3333-3333-3333-333333333333", "succeeded")
    assert sb.last_op == "update"
    assert sb.last_update == {"status": "succeeded"}


def test_mark_result_failed_accepts():
    sb = _FluentBuilder()
    with _patched_supabase(sb):
        mark_compensation_result("33333333-3333-3333-3333-333333333333", "failed")
    assert sb.last_update == {"status": "failed"}


def test_mark_result_other_status_rejected():
    """Only 'succeeded' or 'failed' are valid result statuses. 'pending'
    and 'recorded' are state-machine inputs, not results."""
    with pytest.raises(ReversibilityError, match="succeeded.*failed"):
        mark_compensation_result("33333333-3333-3333-3333-333333333333", "pending")


def test_mark_result_with_result_receipt_id_attaches():
    sb = _FluentBuilder()
    with _patched_supabase(sb):
        mark_compensation_result(
            "33333333-3333-3333-3333-333333333333",
            "succeeded",
            result_receipt_id="44444444-4444-4444-4444-444444444444",
        )
    assert sb.last_update == {
        "status": "succeeded",
        "result_receipt_id": "44444444-4444-4444-4444-444444444444",
    }


# ──────────────────────────────────────────────────────────────────────
# Sanity
# ──────────────────────────────────────────────────────────────────────

def test_valid_statuses_constant_matches_db_check_constraint():
    """The CHECK constraint in v18_wave2_foundation.sql must agree with
    this Python constant. If they drift, every undo call 500s."""
    assert set(VALID_STATUSES) == {"recorded", "pending", "succeeded", "failed"}
