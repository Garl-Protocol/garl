"""Webhook endpoint integration tests.

Exercises the POST /api/v1/pr-bot/webhook HMAC gate + dispatch + ping,
and the GET /api/v1/pr-bot/summary/{...} read path.
"""
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


_SECRET = "pr-bot-webhook-test-secret"


def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_APP_WEBHOOK_SECRET", _SECRET)
    return TestClient(app)


class TestWebhookAuth:
    def test_rejects_when_secret_not_configured(self, monkeypatch):
        monkeypatch.delenv("GITHUB_APP_WEBHOOK_SECRET", raising=False)
        c = TestClient(app)
        r = c.post("/api/v1/pr-bot/webhook", content=b"{}", headers={"X-GitHub-Event": "ping"})
        assert r.status_code == 503

    def test_rejects_invalid_signature(self, client):
        r = client.post(
            "/api/v1/pr-bot/webhook",
            content=b'{"zen":"x"}',
            headers={
                "X-Hub-Signature-256": "sha256=" + "0" * 64,
                "X-GitHub-Event": "ping",
            },
        )
        assert r.status_code == 401

    def test_ping_returns_ok_with_valid_sig(self, client):
        body = b'{"zen":"Keep it logically awesome."}'
        r = client.post(
            "/api/v1/pr-bot/webhook",
            content=body,
            headers={"X-Hub-Signature-256": _sig(body), "X-GitHub-Event": "ping"},
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True, "event": "ping"}


class TestWebhookDispatch:
    def test_non_pull_request_event_ignored(self, client):
        body = b'{"action":"released"}'
        r = client.post(
            "/api/v1/pr-bot/webhook",
            content=body,
            headers={"X-Hub-Signature-256": _sig(body), "X-GitHub-Event": "release"},
        )
        assert r.status_code == 200
        assert r.json()["ignored"] is True

    def test_pull_request_event_queues_background_thread(self, client):
        payload = {
            "action": "opened",
            "installation": {"id": 42},
            "repository": {"owner": {"login": "acme"}, "name": "widgets"},
            "pull_request": {"number": 7, "head": {"sha": "beef"}},
        }
        body = json.dumps(payload).encode()
        with patch("app.api.pr_bot_routes._run_handler_in_background") as mock_run:
            r = client.post(
                "/api/v1/pr-bot/webhook",
                content=body,
                headers={"X-Hub-Signature-256": _sig(body), "X-GitHub-Event": "pull_request"},
            )
        # Thread is started but we patched the target, so it no-ops.
        assert r.status_code == 200
        assert r.json()["queued"] is True
        # The dispatch thread should have been asked to run the handler
        # exactly once with our payload.
        # (threading.Thread wraps it; waiting a tick is enough in CPython.)
        import time as _t
        _t.sleep(0.05)
        mock_run.assert_called_once()
        assert mock_run.call_args.args[0]["action"] == "opened"


class TestSummaryRead:
    def test_returns_stored_summary(self, client):
        row = {
            "owner": "acme",
            "repo": "widgets",
            "pr_number": 7,
            "ai_percentage": 72.5,
            "ai_commits": 5,
            "total_commits": 7,
            "model_counts": {"claude-code": 4, "cursor": 1},
            "updated_at": "2026-04-15T12:00:00Z",
        }

        class _FakeTable:
            def select(self, *a, **kw): return self
            def eq(self, *a, **kw): return self
            def limit(self, *a, **kw): return self
            def execute(self):
                class _R: data = [row]
                return _R()

        db = MagicMock()
        db.table.return_value = _FakeTable()

        with patch("app.api.pr_bot_routes.get_supabase", return_value=db):
            r = client.get("/api/v1/pr-bot/summary/acme/widgets/7")
        assert r.status_code == 200
        body = r.json()
        assert body["owner"] == "acme"
        assert body["ai_percentage"] == 72.5
        assert body["model_counts"]["claude-code"] == 4
        assert body["verify_url"] == "https://garl.ai/pr/acme/widgets/7"

    def test_returns_404_when_missing(self, client):
        class _FakeTable:
            def select(self, *a, **kw): return self
            def eq(self, *a, **kw): return self
            def limit(self, *a, **kw): return self
            def execute(self):
                class _R: data = []
                return _R()

        db = MagicMock()
        db.table.return_value = _FakeTable()
        with patch("app.api.pr_bot_routes.get_supabase", return_value=db):
            r = client.get("/api/v1/pr-bot/summary/acme/widgets/99")
        assert r.status_code == 404
