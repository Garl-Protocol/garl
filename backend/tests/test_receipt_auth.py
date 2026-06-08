"""Auth regression tests for the Wave 2 write endpoints.

These endpoints (submit receipt, issue/revoke capability, undo) mint or mutate
GARL-signed artifacts under an agent's DID. They MUST verify the caller owns the
agent — otherwise anyone could impersonate any agent. A prior version keyed only
on rate-limiting and skipped ownership; these tests lock the fix in place.
"""
import hashlib
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

AGENT_ID = "36dcf4d5-12f1-43fc-a22b-2ef4d26efce5"
REAL_KEY = "garl_real_key"
WRONG_KEY = "garl_wrong_key"
REAL_HASH = hashlib.sha256(REAL_KEY.encode()).hexdigest()


def _result(rows):
    r = MagicMock()
    r.data = rows
    return r


def _db(*, agent_rows=None, token_rows=None, receipt_rows=None):
    """Table-dispatching Supabase mock. Returns configured rows per table for
    the simple select().eq().limit().execute() / select().eq().execute() chains
    used by the ownership lookups."""
    by_table = {
        "agents": agent_rows if agent_rows is not None else [{"id": AGENT_ID, "api_key_hash": REAL_HASH}],
        "capability_tokens": token_rows if token_rows is not None else [{"agent_id": AGENT_ID}],
        "receipts": receipt_rows if receipt_rows is not None else [{"agent_id": AGENT_ID}],
    }

    def table(name):
        t = MagicMock()
        t.select.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t
        t.execute.return_value = _result(by_table.get(name, []))
        return t

    db = MagicMock()
    db.table.side_effect = table
    return db


class TestReceiptSubmitAuth:
    def test_wrong_key_rejected_403(self):
        body = {"agent_id": AGENT_ID, "runtime": "claude-code", "protocol": "raw-http",
                "action_type": "code_write", "side_effect": "none",
                "input_hash": "a" * 64, "output_hash": "b" * 64}
        with patch("app.api.routes._get_supabase", return_value=_db()):
            r = TestClient(app).post("/api/v1/receipts", json=body, headers={"x-api-key": WRONG_KEY})
        assert r.status_code == 403

    def test_missing_agent_id_422(self):
        with patch("app.api.routes._get_supabase", return_value=_db()):
            r = TestClient(app).post("/api/v1/receipts", json={"runtime": "claude-code"},
                                     headers={"x-api-key": REAL_KEY})
        assert r.status_code == 422

    def test_unknown_agent_404(self):
        body = {"agent_id": AGENT_ID, "runtime": "claude-code", "protocol": "raw-http",
                "action_type": "code_write", "side_effect": "none",
                "input_hash": "a" * 64, "output_hash": "b" * 64}
        with patch("app.api.routes._get_supabase", return_value=_db(agent_rows=[])):
            r = TestClient(app).post("/api/v1/receipts", json=body, headers={"x-api-key": REAL_KEY})
        assert r.status_code == 404


class TestCapabilityIssueAuth:
    def test_wrong_key_rejected_403(self):
        body = {"agent_id": AGENT_ID, "scope": "read", "side_effect_class": "none"}
        with patch("app.api.routes._get_supabase", return_value=_db()):
            r = TestClient(app).post("/api/v1/capability/issue", json=body, headers={"x-api-key": WRONG_KEY})
        assert r.status_code == 403


class TestCapabilityRevokeAuth:
    def test_revoke_others_token_rejected_403(self):
        body = {"token_hash": "c" * 64}
        with patch("app.api.routes._get_supabase", return_value=_db()):
            r = TestClient(app).post("/api/v1/capability/revoke", json=body, headers={"x-api-key": WRONG_KEY})
        assert r.status_code == 403

    def test_revoke_unknown_token_404(self):
        body = {"token_hash": "c" * 64}
        with patch("app.api.routes._get_supabase", return_value=_db(token_rows=[])):
            r = TestClient(app).post("/api/v1/capability/revoke", json=body, headers={"x-api-key": REAL_KEY})
        assert r.status_code == 404


class TestReceiptUndoAuth:
    def test_undo_others_receipt_rejected_403(self):
        with patch("app.api.routes._get_supabase", return_value=_db()):
            r = TestClient(app).post(f"/api/v1/receipts/{AGENT_ID}/undo", json={},
                                     headers={"x-api-key": WRONG_KEY})
        assert r.status_code == 403

    def test_undo_requires_api_key_422(self):
        # No x-api-key header at all → FastAPI 422 (Header(...) required).
        r = TestClient(app).post(f"/api/v1/receipts/{AGENT_ID}/undo", json={})
        assert r.status_code == 422
