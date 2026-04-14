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
    """Tests for the public GET /api/v1/verify/{trace_hash} receipt endpoint."""

    @staticmethod
    def _wire_mock(mock_db, traces, agent=None):
        def table_side_effect(table_name):
            mock_table = MagicMock()
            mock_res = MagicMock()
            if table_name == "traces":
                mock_res.data = traces
            elif table_name == "agents":
                mock_res.data = [agent] if agent else []
            else:
                mock_res.data = []
            mock_res.count = len(mock_res.data)
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.like.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.execute.return_value = mock_res
            return mock_table
        mock_db.table.side_effect = table_side_effect

    def test_verify_invalid_hash_format_nonhex(self, mock_supabase_for_routes):
        # 'tooshort' is 8 chars but contains non-hex letters
        response = client.get("/api/v1/verify/tooshort")
        assert response.status_code == 400
        assert "Invalid trace hash" in response.json()["detail"]

    def test_verify_below_min_length(self, mock_supabase_for_routes):
        response = client.get("/api/v1/verify/abc123")  # 6 hex chars, too short
        assert response.status_code == 400

    def test_verify_above_max_length(self, mock_supabase_for_routes):
        response = client.get(f"/api/v1/verify/{'a' * 65}")
        assert response.status_code == 400

    def test_verify_nonexistent_trace(self, mock_supabase_for_routes):
        self._wire_mock(mock_supabase_for_routes, traces=[])
        response = client.get(f"/api/v1/verify/{'a' * 64}")
        assert response.status_code == 404

    def test_verify_valid_full_hash_with_enrichment(self, mock_supabase_for_routes):
        trace = {
            "id": "trace-123",
            "agent_id": "agent-456",
            "task_description": "Wrote README",
            "status": "success",
            "duration_ms": 1000,
            "category": "coding",
            "trust_score_after": 52.5,
            "trace_hash": "b" * 64,
            "runtime_env": "langchain",
            "created_at": "2026-03-11T00:00:00Z",
        }
        agent = {
            "name": "CodeBot",
            "framework": "langchain",
            "certification_tier": "silver",
            "trust_score": 68.4,
        }
        self._wire_mock(mock_supabase_for_routes, traces=[trace], agent=agent)

        response = client.get(f"/api/v1/verify/{'b' * 64}")
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["trace_hash"] == "b" * 64
        assert data["short_hash"] == "b" * 8
        assert data["agent_id"] == "agent-456"
        assert data["agent_name"] == "CodeBot"
        assert data["agent_tier"] == "silver"
        assert data["agent_trust_score"] == 68.4
        assert data["task_description"] == "Wrote README"
        assert data["duration_ms"] == 1000
        assert data["runtime_env"] == "langchain"
        assert data["receipt_url"].endswith("/r/bbbbbbbb")
        assert "certificate" in data
        assert "public_key" in data

    def test_verify_short_hash_prefix_match(self, mock_supabase_for_routes):
        trace = {
            "id": "t1", "agent_id": "a1",
            "task_description": "x", "status": "success", "duration_ms": 100,
            "category": "other", "trust_score_after": 50.0,
            "trace_hash": "deadbeef" + ("0" * 56),
            "created_at": "2026-03-11T00:00:00Z",
        }
        self._wire_mock(mock_supabase_for_routes, traces=[trace])
        response = client.get("/api/v1/verify/deadbeef")
        assert response.status_code == 200
        data = response.json()
        assert data["trace_hash"].startswith("deadbeef")
        assert data["short_hash"] == "deadbeef"

    def test_verify_short_hash_ambiguous_returns_409(self, mock_supabase_for_routes):
        traces = [
            {"id": "t1", "agent_id": "a1", "task_description": "a",
             "status": "success", "duration_ms": 1, "category": "other",
             "trust_score_after": 50.0, "trace_hash": "abcd1234" + ("0" * 56),
             "created_at": "2026-03-11T00:00:00Z"},
            {"id": "t2", "agent_id": "a2", "task_description": "b",
             "status": "success", "duration_ms": 1, "category": "other",
             "trust_score_after": 50.0, "trace_hash": "abcd1234" + ("1" * 56),
             "created_at": "2026-03-11T00:00:00Z"},
        ]
        self._wire_mock(mock_supabase_for_routes, traces=traces)
        response = client.get("/api/v1/verify/abcd1234")
        assert response.status_code == 409

    def test_verify_short_hash_uppercase_normalized(self, mock_supabase_for_routes):
        trace = {
            "id": "t1", "agent_id": "a1", "task_description": "x",
            "status": "success", "duration_ms": 1, "category": "other",
            "trust_score_after": 50.0, "trace_hash": "deadbeef" + ("0" * 56),
            "created_at": "2026-03-11T00:00:00Z",
        }
        self._wire_mock(mock_supabase_for_routes, traces=[trace])
        response = client.get("/api/v1/verify/DEADBEEF")
        assert response.status_code == 200
        assert response.json()["short_hash"] == "deadbeef"


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
