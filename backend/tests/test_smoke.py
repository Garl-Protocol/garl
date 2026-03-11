"""
GARL Protocol — Smoke Test Suite

Two tiers of testing:
1. Integration tests: Run against local docker-compose with mocked Supabase
2. Production smoke tests: Read-only checks against live API (no data mutation)
"""
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================
# Tier 1: Integration Tests (Local / Docker-compose)
# ============================================================

class TestPublicVerifyEndpoint:
    """Tests for the new GET /api/v1/verify/{trace_hash} public endpoint."""

    def test_verify_invalid_hash_format(self, mock_supabase_for_routes):
        response = client.get("/api/v1/verify/tooshort")
        assert response.status_code == 400
        assert "Invalid trace hash" in response.json()["detail"]

    def test_verify_nonexistent_trace(self, mock_supabase_for_routes):
        fake_hash = "a" * 64
        response = client.get(f"/api/v1/verify/{fake_hash}")
        assert response.status_code == 404

    def test_verify_valid_trace(self, mock_supabase_for_routes):
        mock_db = mock_supabase_for_routes
        trace_data = {
            "id": "trace-123",
            "agent_id": "agent-456",
            "task_description": "Test task",
            "status": "success",
            "duration_ms": 1000,
            "category": "coding",
            "trust_score_after": 52.5,
            "trace_hash": "b" * 64,
            "created_at": "2026-03-11T00:00:00Z",
        }

        def table_side_effect(table_name):
            mock_table = MagicMock()
            mock_res = MagicMock()
            if table_name == "traces":
                mock_res.data = [trace_data]
            else:
                mock_res.data = []
            mock_res.count = 1 if table_name == "traces" else 0
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.execute.return_value = mock_res
            return mock_table

        mock_db.table.side_effect = table_side_effect

        response = client.get(f"/api/v1/verify/{'b' * 64}")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["trace_hash"] == "b" * 64
        assert data["agent_id"] == "agent-456"
        assert "certificate" in data
        assert "public_key" in data


class TestFeedWithCertificateInfo:
    """Tests for feed endpoint including certificate verification info."""

    def test_feed_includes_verification(self, mock_supabase_for_routes):
        mock_db = mock_supabase_for_routes

        def table_side_effect(table_name):
            mock_table = MagicMock()
            mock_res = MagicMock()
            if table_name == "traces":
                mock_res.data = [{
                    "id": "t1",
                    "agent_id": "a1",
                    "task_description": "test",
                    "status": "success",
                    "duration_ms": 500,
                    "trust_delta": 0.5,
                    "category": "coding",
                    "cost_usd": 0.01,
                    "trace_hash": "c" * 64,
                    "created_at": "2026-03-11T00:00:00Z",
                }]
                mock_res.count = 1
            else:
                mock_res.data = []
                mock_res.count = 0
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.order.return_value = mock_table
            mock_table.range.return_value = mock_table
            mock_table.execute.return_value = mock_res
            return mock_table

        mock_db.table.side_effect = table_side_effect

        response = client.get("/api/v1/feed?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        if data["data"]:
            trace = data["data"][0]
            assert "verification" in trace
            assert trace["verification"]["algorithm"] == "ECDSA-secp256k1"
            assert trace["verification"]["hash_algorithm"] == "SHA-256"
            assert trace["verification"]["trace_hash"] is not None


class TestPlaygroundEndpoints:
    """Verify playground-accessible endpoints respond correctly."""

    def test_stats_endpoint(self, mock_supabase_for_routes):
        response = client.get("/api/v1/stats")
        assert response.status_code == 200

    def test_leaderboard_endpoint(self, mock_supabase_for_routes):
        response = client.get("/api/v1/leaderboard?limit=5")
        assert response.status_code == 200


class TestNavigationPages:
    """Verify that key frontend-accessible API routes exist."""

    def test_mcp_tools_list(self, mock_supabase_for_routes):
        response = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        })
        assert response.status_code == 200

    def test_a2a_agent_card(self, mock_supabase_for_routes):
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200


# ============================================================
# Tier 2: Production Smoke Tests (Read-only, against live API)
# ============================================================

PROD_API = "https://api.garl.ai"


@pytest.mark.skipif(
    True,  # Set to False when running against production
    reason="Production smoke tests disabled by default"
)
class TestProductionSmoke:
    """Read-only smoke tests against the live API.
    Run with: pytest -k TestProductionSmoke --override-ini='addopts='
    Enable by setting the skipif condition to False."""

    def test_prod_stats(self):
        import httpx
        r = httpx.get(f"{PROD_API}/api/v1/stats", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("total_agents", 0) > 0

    def test_prod_leaderboard(self):
        import httpx
        r = httpx.get(f"{PROD_API}/api/v1/leaderboard?limit=5", timeout=10)
        assert r.status_code == 200

    def test_prod_mcp_tools(self):
        import httpx
        r = httpx.post(
            f"{PROD_API}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            timeout=10,
        )
        assert r.status_code == 200

    def test_prod_agent_card(self):
        import httpx
        r = httpx.get(f"{PROD_API}/.well-known/agent-card.json", timeout=10)
        assert r.status_code == 200

    def test_prod_feed(self):
        import httpx
        r = httpx.get(f"{PROD_API}/api/v1/feed?limit=3", timeout=10)
        assert r.status_code == 200
        data = r.json()
        if data.get("data"):
            assert "verification" in data["data"][0]
