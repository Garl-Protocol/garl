"""Route tests for the session-alert API surface (app/api/alert_routes.py).

GET endpoints are public; POST /agents/{id}/scan is owner-only via the same
x-api-key ownership pattern as the rest of the API. Supabase is mocked per
the test_anchors_endpoint pattern.
"""

from __future__ import annotations

import hashlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

AGENT = "11111111-1111-1111-1111-111111111111"
API_KEY = "garl_test_key_alert_routes_1"


@pytest.fixture
def client():
    return TestClient(app)


def _sb_alerts(rows, count=None):
    """Supabase mock whose session_alerts select chain resolves to rows."""
    sb = MagicMock()
    chain = MagicMock()
    for m in ("select", "eq", "order", "range", "limit"):
        getattr(chain, m).return_value = chain
    res = MagicMock()
    res.data = rows
    res.count = count if count is not None else len(rows)
    chain.execute.return_value = res
    sb.table.return_value = chain
    return sb


def _sb_agent_owner(api_key=API_KEY):
    """Supabase mock for routes._verify_agent_ownership."""
    sb = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    res = MagicMock()
    res.data = [{"id": AGENT, "api_key_hash": hashlib.sha256(api_key.encode()).hexdigest()}]
    chain.execute.return_value = res
    sb.table.return_value = chain
    return sb


_ROW = {
    "envelope_json": {
        "alert_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "version": "garl/session-alert/v0.1",
        "rule": "spend_velocity",
        "severity": "warning",
    },
    "created_at": "2026-08-03T10:00:00+00:00",
}


class TestListAgentAlerts:
    def test_returns_envelopes_newest_first(self, client):
        sb = _sb_alerts([_ROW], count=1)
        with patch("app.api.alert_routes._get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/agents/{AGENT}/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["agent_id"] == AGENT
        assert body["total"] == 1
        assert body["alerts"] == [_ROW["envelope_json"]]
        # newest-first ordering requested from the DB
        sb.table.return_value.order.assert_called_once_with("created_at", desc=True)

    def test_invalid_uuid_400(self, client):
        resp = client.get("/api/v1/agents/not-a-uuid/alerts")
        assert resp.status_code == 400

    def test_limit_clamped_to_100(self, client):
        sb = _sb_alerts([], count=0)
        with patch("app.api.alert_routes._get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/agents/{AGENT}/alerts?limit=5000&offset=0")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 100
        sb.table.return_value.range.assert_called_once_with(0, 99)

    def test_pagination_range(self, client):
        sb = _sb_alerts([], count=0)
        with patch("app.api.alert_routes._get_supabase", return_value=sb):
            resp = client.get(f"/api/v1/agents/{AGENT}/alerts?limit=10&offset=30")
        assert resp.status_code == 200
        sb.table.return_value.range.assert_called_once_with(30, 39)


class TestListRecentAlerts:
    def test_returns_recent_across_agents(self, client):
        sb = _sb_alerts([_ROW, _ROW])
        with patch("app.api.alert_routes._get_supabase", return_value=sb):
            resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["alerts"][0]["rule"] == "spend_velocity"

    def test_limit_clamped_to_100(self, client):
        sb = _sb_alerts([])
        with patch("app.api.alert_routes._get_supabase", return_value=sb):
            resp = client.get("/api/v1/alerts?limit=999")
        assert resp.status_code == 200
        assert resp.json()["limit"] == 100
        sb.table.return_value.limit.assert_called_once_with(100)


class TestScanEndpoint:
    def test_missing_api_key_401(self, client):
        resp = client.post(f"/api/v1/agents/{AGENT}/scan")
        assert resp.status_code == 401

    def test_wrong_api_key_403(self, client):
        with patch("app.api.routes._get_supabase", return_value=_sb_agent_owner()):
            resp = client.post(
                f"/api/v1/agents/{AGENT}/scan",
                headers={"x-api-key": "garl_wrong_key_for_403_test"},
            )
        assert resp.status_code == 403

    def test_unknown_agent_404(self, client):
        sb = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        res = MagicMock()
        res.data = []
        chain.execute.return_value = res
        sb.table.return_value = chain
        with patch("app.api.routes._get_supabase", return_value=sb):
            resp = client.post(
                f"/api/v1/agents/{AGENT}/scan",
                headers={"x-api-key": "garl_key_for_404_test_00"},
            )
        assert resp.status_code == 404

    def test_owner_scan_runs_and_returns_alerts(self, client):
        scan_result = {"scanned": 1, "alerts": [{"rule": "receipt_rate"}], "window_hours": 24}
        with patch("app.api.routes._get_supabase", return_value=_sb_agent_owner()), \
             patch("app.services.session_anomaly.run_session_scan",
                   return_value=scan_result) as scan:
            resp = client.post(
                f"/api/v1/agents/{AGENT}/scan",
                headers={"x-api-key": API_KEY},
            )
        assert resp.status_code == 200
        assert resp.json() == scan_result
        scan.assert_called_once_with(AGENT)

    def test_invalid_uuid_400(self, client):
        resp = client.post(
            "/api/v1/agents/not-a-uuid/scan",
            headers={"x-api-key": "garl_key_uuid_test_0001"},
        )
        assert resp.status_code == 400
