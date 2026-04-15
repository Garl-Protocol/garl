"""Phase 1 hardening — CORS fail-closed, unhandled-exception sanitization,
?fields=full owner authentication soft-cut."""
import hashlib
import os
from unittest.mock import patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


class TestCorsFailClosed:
    def test_production_ignores_dev_origins_when_env_missing(self):
        s = Settings(debug=False)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            origins = s.get_cors_origins()
        assert "http://localhost:3000" not in origins
        assert "https://garl.ai" in origins

    def test_production_uses_env_when_set(self):
        s = Settings(debug=False)
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "https://garl.ai,https://www.garl.ai"}):
            origins = s.get_cors_origins()
        assert origins == ["https://garl.ai", "https://www.garl.ai"]

    def test_debug_mode_keeps_localhost(self):
        s = Settings(debug=True)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALLOWED_ORIGINS", None)
            origins = s.get_cors_origins()
        assert "http://localhost:3000" in origins


class TestUnhandledExceptionHandler:
    def test_unhandled_exception_is_sanitized(self):
        # Mount a route that raises a bare Python exception so the
        # global handler is exercised end-to-end.
        from app.main import app as main_app
        router = APIRouter()

        @router.get("/_test_boom")
        async def _boom():
            raise RuntimeError("db password=hunter2 leaked!")

        main_app.include_router(router)
        client = TestClient(main_app, raise_server_exceptions=False)
        resp = client.get("/_test_boom")
        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"] == "Internal server error"
        assert "hunter2" not in resp.text
        assert "password" not in resp.text
        assert "correlation_id" in body
        # correlation id looks like a uuid
        assert len(body["correlation_id"]) == 36


class TestFieldsFullSoftCut:
    """?fields=full without matching api_key → slim projection + Deprecation headers."""

    def _fake_agent(self):
        return {
            "id": "a1b2c3d4-e5f6-4789-a012-345678901234",
            "name": "Auth Probe",
            "trust_score": 60.0,
            "certification_tier": "silver",
            "score_reliability": 60,
            "score_security": 60,
            "score_speed": 60,
            "score_cost_efficiency": 60,
            "score_consistency": 60,
            "total_traces": 10,
            "success_rate": 1.0,
            "framework": "custom",
            "category": "coding",
            "anomaly_flags": [],
            "sovereign_id": "did:garl:a1b2c3d4-e5f6-4789-a012-345678901234",
            # internal fields only visible in full mode:
            "ema_reliability": 62,
            "ema_security": 58,
            "permissions_declared": ["fs:read"],
            "security_events": [],
            "is_sandbox": False,
            "is_deleted": False,
            "developer_id": "dev-1",
            "api_key_hash": hashlib.sha256(b"super-secret-key").hexdigest(),
        }

    def test_full_without_key_downgrades_with_deprecation_header(self):
        with patch("app.api.routes.get_agent", return_value=self._fake_agent()):
            client = TestClient(app)
            resp = client.get(f"/api/v1/agents/{self._fake_agent()['id']}?fields=full")
        assert resp.status_code == 200
        body = resp.json()
        # internal fields leaked?
        assert "ema_reliability" not in body
        assert "permissions_declared" not in body
        assert "api_key_hash" not in body
        assert resp.headers.get("deprecation") == "true"
        assert "Sunset" in {k.title() for k in resp.headers.keys()}

    def test_full_with_matching_key_returns_full(self):
        with patch("app.api.routes.get_agent", return_value=self._fake_agent()):
            client = TestClient(app)
            resp = client.get(
                f"/api/v1/agents/{self._fake_agent()['id']}?fields=full",
                headers={"x-api-key": "super-secret-key"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "ema_reliability" in body
        assert "permissions_declared" in body
        # api_key_hash is part of the raw agent row — it SHOULD flow through
        # in full mode today (caller is the owner) but is still never exposed
        # via the slim projection. Guard for that invariant:
        assert body.get("api_key_hash") is not None
        assert resp.headers.get("deprecation") is None

    def test_full_with_wrong_key_downgrades_silently(self):
        with patch("app.api.routes.get_agent", return_value=self._fake_agent()):
            client = TestClient(app)
            resp = client.get(
                f"/api/v1/agents/{self._fake_agent()['id']}?fields=full",
                headers={"x-api-key": "wrong-key"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "ema_reliability" not in body
        assert resp.headers.get("deprecation") == "true"
