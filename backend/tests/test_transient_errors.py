"""Regression tests for the 2026-07-07 transient-DB-error hardening.

Context: Supabase briefly returned a Cloudflare ``522`` (HTML body) on
``GET /verify/{hash}``. The decorative agent-enrichment lookup was unguarded,
so the blip ``500``'d the whole (already-verified) receipt, and the multi-KB
HTML error flooded the logs past the platform's 500 logs/sec limit.

Fixes under test:
  * ``app.core.errors.is_transient_upstream_error`` classifies such blips.
  * The global handler maps them to a bounded-log ``503`` (not a ``500``).
  * ``public_verify_trace`` degrades the agent summary instead of failing.
"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.errors import is_transient_upstream_error, bounded_error_text
from app.main import app
import app.api.routes as routes


class _FakeAPIError(Exception):
    """Stand-in for ``postgrest.exceptions.APIError``: a numeric-ish ``.code``
    plus a multi-KB HTML message, exactly like the observed Supabase/Cloudflare
    ``522``."""

    def __init__(self):
        self.code = "522"
        self.message = "JSON could not be generated"
        super().__init__("<html>" + "x" * 5000 + " 522 Connection timed out</html>")


class _ReadTimeout(Exception):
    """Class name mirrors ``httpx.ReadTimeout`` (classified by class name)."""


# --------------------------------------------------------------------------- #
# Unit: classifier + log-bounding helper
# --------------------------------------------------------------------------- #
class TestClassifier:
    def test_cloudflare_522_is_transient(self):
        assert is_transient_upstream_error(_FakeAPIError()) is True

    def test_httpx_named_timeout_is_transient(self):
        assert is_transient_upstream_error(_ReadTimeout("read timed out")) is True

    def test_builtin_timeout_and_connection_errors_are_transient(self):
        assert is_transient_upstream_error(TimeoutError()) is True
        assert is_transient_upstream_error(ConnectionResetError()) is True

    def test_message_marker_is_transient(self):
        assert is_transient_upstream_error(Exception("Connection refused")) is True

    def test_ordinary_errors_are_not_transient(self):
        assert is_transient_upstream_error(ValueError("bad hash")) is False
        assert is_transient_upstream_error(KeyError("agent_id")) is False

    def test_application_sqlstate_code_is_not_transient(self):
        # A genuine PostgREST SQLSTATE (not a gateway/CDN code) must NOT be
        # misread as a retriable blip.
        err = Exception("operator does not exist")
        err.code = "42883"
        assert is_transient_upstream_error(err) is False

    def test_bounded_error_text_truncates_and_flattens(self):
        out = bounded_error_text(_FakeAPIError(), limit=80)
        assert len(out) <= 80
        assert "\n" not in out and "\r" not in out
        # Prefers the short ``.message`` over the multi-KB body.
        assert out.startswith("JSON could not be generated")


# --------------------------------------------------------------------------- #
# Integration: /verify/{hash} resilience
# --------------------------------------------------------------------------- #
def _fake_db(*, traces_raises=False, agents_raises=False):
    db = MagicMock()

    def table(name):
        t = MagicMock()
        for m in ("select", "eq", "like", "limit", "order", "range", "in_", "gt", "ilike"):
            getattr(t, m).return_value = t
        res = MagicMock()
        if name == "traces":
            if traces_raises:
                t.execute.side_effect = _FakeAPIError()
            else:
                res.data = [{
                    "id": "11111111-1111-1111-1111-111111111111",
                    "trace_hash": "a" * 64,
                    "agent_id": "22222222-2222-2222-2222-222222222222",
                    "task_description": "did a thing",
                    "status": "success",
                    "duration_ms": 12,
                    "category": "other",
                    "certificate": {},  # no proof -> legacy branch, verified False
                }]
                t.execute.return_value = res
        elif name == "agents":
            if agents_raises:
                t.execute.side_effect = _FakeAPIError()
            else:
                res.data = [{
                    "name": "AgentX", "framework": "custom",
                    "certification_tier": "silver", "trust_score": 55.5,
                }]
                t.execute.return_value = res
        else:
            res.data = []
            t.execute.return_value = res
        return t

    db.table.side_effect = table
    return db


class TestVerifyDegradesEnrichment:
    def test_agent_blip_still_returns_verified_receipt(self):
        db = _fake_db(agents_raises=True)
        with patch.object(routes, "_get_supabase", return_value=db):
            resp = TestClient(app).get("/api/v1/verify/" + "a" * 64)
        assert resp.status_code == 200
        body = resp.json()
        assert body["trace_hash"] == "a" * 64
        assert body["task_description"] == "did a thing"
        assert body["agent_name"] is None  # degraded, not fatal

    def test_healthy_path_includes_agent_summary(self):
        db = _fake_db()
        with patch.object(routes, "_get_supabase", return_value=db):
            resp = TestClient(app).get("/api/v1/verify/" + "a" * 64)
        assert resp.status_code == 200
        assert resp.json()["agent_name"] == "AgentX"


class TestPrimaryLookupMapsTo503:
    def test_transient_db_error_on_lookup_returns_503(self):
        db = _fake_db(traces_raises=True)
        # raise_server_exceptions=False so the registered Exception handler's
        # response is returned instead of being re-raised into the test.
        client = TestClient(app, raise_server_exceptions=False)
        with patch.object(routes, "_get_supabase", return_value=db):
            resp = client.get("/api/v1/verify/" + "a" * 64)
        assert resp.status_code == 503
        assert resp.headers.get("Retry-After") == "5"
        assert resp.json()["detail"].startswith("Service temporarily unavailable")
