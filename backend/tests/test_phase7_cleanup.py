"""Phase 7 — deprecation headers on pre-pivot endpoints + trace insert shape."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestDeprecationHeaders:
    @pytest.mark.parametrize("path", [
        "/api/v1/trust/verify?agent_id=nope",
        "/api/v1/erc8004/nope",
        "/a2a",
    ])
    def test_deprecated_paths_carry_rfc_9745_headers(self, path):
        client = TestClient(app)
        resp = client.get(path)
        # We don't care whether the endpoint returns 200/400/404/405 —
        # only that deprecation metadata lands in the response. The
        # middleware runs after the route handler finalises status.
        assert resp.headers.get("Deprecation") == "true"
        assert resp.headers.get("Sunset", "").endswith("GMT")
        assert 'rel="successor-version"' in resp.headers.get("Link", "")

    def test_non_deprecated_path_has_no_deprecation(self):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.headers.get("Deprecation") is None
        assert resp.headers.get("Sunset") is None


class TestTraceInsertExcludesDroppedColumns:
    """Post-v14 the insert payload must not carry dropped columns.

    We check statically — mocking the whole scoring pipeline is brittle
    and offers no extra guarantee over a source-level grep of the one
    function that builds the insert dict. The full e2e trace-submit
    contract is already covered by test_routes + test_security."""

    def test_source_of_submit_trace_does_not_write_dropped_columns(self):
        import inspect
        from app.services import traces as traces_mod
        src = inspect.getsource(traces_mod.submit_trace)
        # The .insert({...}) dict must NOT contain any of these keys.
        # Surrounding each literal with a quote guards against the
        # metadata[...]-style usage in the same function.
        for key in ('"tool_calls"', '"proof_of_result"', '"runtime_env"'):
            # It IS valid for these to appear as keys into trace_metadata
            # (the stash for forward-compat). Only the literal
            # `"<key>":` followed by `req.` or similar at the insert-
            # dict position would be a regression. We narrow by looking
            # at the substring immediately after the insert({ opener.
            pass

        # Locate the insert({ ... }) block
        start = src.find('db.table("traces").insert({')
        assert start > 0, "insert block not found; test needs an update"
        end = src.find("}).execute()", start)
        block = src[start:end]
        assert "tool_calls" not in block, "insert still writes tool_calls"
        assert "proof_of_result" not in block, "insert still writes proof_of_result"
        assert "runtime_env" not in block, "insert still writes runtime_env"
