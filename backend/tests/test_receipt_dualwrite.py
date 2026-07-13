"""Tests for the trace -> Action Receipt v0.1 dual-write (2026-07-13).

Every verified trace is mirrored onto the receipt rail (which feeds the Merkle
anchor + /proof) with output_hash == trace_hash, so the two ledgers resolve to
the same short hash and /r/{short} lights up the v0.1 enrichment + on-chain
proof. The mirror is best-effort: it must never affect an already-persisted
trace, and it must not double-charge the monthly cap.
"""
from unittest.mock import MagicMock, patch

import app.services.action_receipts as ar


def _mock_sb(existing_receipt=False):
    """Mock supabase where receipts.select(...).execute() reports whether a
    mirror already exists, and receipts.insert(row) records the row."""
    sb = MagicMock()
    inserted: list[dict] = []

    def table(_name):
        t = MagicMock()
        for m in ("select", "eq", "limit", "order", "in_"):
            getattr(t, m).return_value = t
        sel_res = MagicMock()
        sel_res.data = [{"receipt_id": "existing"}] if existing_receipt else []
        t.execute.return_value = sel_res

        def _insert(row):
            inserted.append(row)
            ins = MagicMock()
            ins.execute.return_value = MagicMock()
            return ins

        t.insert.side_effect = _insert
        return t

    sb.table.side_effect = table
    return sb, inserted


class TestMintMapping:
    def test_coding_github_claude_trace_maps_correctly(self):
        sb, inserted = _mock_sb()
        th = "a" * 64
        with patch.object(ar, "_get_supabase", return_value=sb):
            env = ar.mint_receipt_for_trace({
                "agent_id": "ag1", "trace_hash": th, "id": "tr1",
                "category": "coding", "runtime_env": "github-action-receipt/claude",
            })
        assert env is not None
        assert env["output_hash"] == th          # <-- links the two ledgers
        assert env["agent_identity"] == "did:garl:ag1"
        assert env["action_type"] == "code_write"
        assert env["side_effect"] == "reversible"
        assert env["runtime"] == "claude-code"
        assert env["protocol"] == "github"
        assert "signature" in env and "verification_key_id" in env
        assert any(r.get("output_hash") == th for r in inserted)

    def test_research_trace_maps_to_tool_call_none_custom(self):
        sb, _ = _mock_sb()
        with patch.object(ar, "_get_supabase", return_value=sb):
            env = ar.mint_receipt_for_trace({
                "agent_id": "ag", "trace_hash": "b" * 64, "id": "t",
                "category": "research", "runtime_env": "",
            })
        assert env["action_type"] == "tool_call"
        assert env["side_effect"] == "none"
        assert env["runtime"] == "custom"
        assert env["protocol"] == "raw-http"

    def test_input_hash_is_64_hex_and_deterministic(self):
        sb, _ = _mock_sb()
        trace = {"agent_id": "ag", "trace_hash": "c" * 64, "id": "tr", "category": "coding"}
        with patch.object(ar, "_get_supabase", return_value=sb):
            e1 = ar.mint_receipt_for_trace(dict(trace))
        sb2, _ = _mock_sb()
        with patch.object(ar, "_get_supabase", return_value=sb2):
            e2 = ar.mint_receipt_for_trace(dict(trace))
        assert e1["input_hash"] == e2["input_hash"]
        assert len(e1["input_hash"]) == 64
        assert all(c in "0123456789abcdef" for c in e1["input_hash"])


class TestMintSafety:
    def test_idempotent_when_mirror_already_exists(self):
        sb, inserted = _mock_sb(existing_receipt=True)
        with patch.object(ar, "_get_supabase", return_value=sb):
            env = ar.mint_receipt_for_trace({
                "agent_id": "ag", "trace_hash": "d" * 64, "id": "t", "category": "coding",
            })
        assert env is None
        assert inserted == []  # no duplicate insert

    def test_invalid_input_returns_none_without_raising(self):
        assert ar.mint_receipt_for_trace({"agent_id": "ag", "trace_hash": "tooshort", "id": "t"}) is None
        assert ar.mint_receipt_for_trace({"agent_id": None, "trace_hash": "e" * 64}) is None
        assert ar.mint_receipt_for_trace({}) is None

    def test_db_error_returns_none_without_raising(self):
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("supabase down")
        with patch.object(ar, "_get_supabase", return_value=sb):
            out = ar.mint_receipt_for_trace({
                "agent_id": "ag", "trace_hash": "f" * 64, "id": "t", "category": "coding",
            })
        assert out is None  # must not propagate — the trace is already saved


class TestEnforceCap:
    def test_dual_write_skips_the_monthly_cap(self):
        # The originating trace already passed its own cap; mirroring must not
        # call (and cannot be blocked by) enforce_monthly_cap.
        sb, inserted = _mock_sb()
        import app.services.monthly_cap as mc

        def _boom(_agent_id):
            raise AssertionError("enforce_monthly_cap must be skipped for the mirror")

        with patch.object(ar, "_get_supabase", return_value=sb), \
                patch.object(mc, "enforce_monthly_cap", _boom):
            env = ar.submit_action_receipt(
                {
                    "agent_id": "ag", "runtime": "custom", "protocol": "raw-http",
                    "action_type": "tool_call", "input_hash": "1" * 64,
                    "output_hash": "2" * 64, "side_effect": "none",
                },
                enforce_cap=False,
            )
        assert env["output_hash"] == "2" * 64
        assert len(inserted) == 1
