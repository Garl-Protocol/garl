"""
GARL Protocol v1.0 — API route integration tests.

Verifies endpoint behavior with FastAPI TestClient.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


@pytest.fixture
def mock_supabase_for_routes():
    """
    Supabase mock for route handlers.
    Provides data for register_agent, route_agents, get_compliance_report.
    """
    mock_client = MagicMock()

    def table_side_effect(table_name):
        mock_table = MagicMock()
        mock_res = MagicMock()
        mock_res.data = []
        mock_res.count = 0

        if table_name == "agents":
            # register_agent: success after insert
            mock_table.insert.return_value = mock_table
            mock_table.execute.return_value = mock_res

            # route_agents and get_compliance_report: agent data (valid UUID)
            def agents_execute():
                mock_res.data = [
                    {
                        "id": "a1b2c3d4-e5f6-4789-a012-345678901234",
                        "name": "Test Agent",
                        "trust_score": 75.0,
                        "certification_tier": "silver",
                        "sovereign_id": "did:garl:a1b2c3d4-e5f6-4789-a012-345678901234",
                        "score_reliability": 75.0,
                        "score_security": 70.0,
                        "score_speed": 72.0,
                        "score_cost_efficiency": 68.0,
                        "score_consistency": 74.0,
                        "total_traces": 50,
                        "success_rate": 92.0,
                        "framework": "langchain",
                        "category": "coding",
                        "permissions_declared": [],
                        "created_at": "2025-01-01T00:00:00Z",
                        "last_trace_at": "2025-01-15T12:00:00Z",
                        "anomaly_flags": [],
                    }
                ]
                return mock_res

            mock_table.in_.return_value = mock_table
            mock_table.gt.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.order.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.select.return_value = mock_table
            mock_table.range.return_value = mock_table
            mock_table.or_.return_value = mock_table
            mock_table.execute.side_effect = agents_execute

        elif table_name == "reputation_history":
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.order.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.execute.return_value = mock_res

        elif table_name == "traces":
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.order.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.execute.return_value = mock_res

        elif table_name == "webhooks":
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.execute.return_value = mock_res

        else:
            mock_table.select.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.update.return_value = mock_table
            mock_table.order.return_value = mock_table
            mock_table.limit.return_value = mock_table
            mock_table.execute.return_value = mock_res

        return mock_table

    mock_client.table.side_effect = table_side_effect

    with patch("app.core.supabase_client.get_supabase", return_value=mock_client):
        with patch("app.services.agents.get_supabase", return_value=mock_client):
            with patch("app.services.traces.get_supabase", return_value=mock_client):
                with patch("app.api.routes._get_supabase", return_value=mock_client):
                    yield mock_client


class TestRootEndpoint:
    """GET / endpoint tests."""

    def test_protocol_info(self, client):
        """GET / returns protocol info and version 1.0.0."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["protocol"] == "GARL"
        assert data["version"] == "1.0.1"
        assert "docs" in data


class TestHealthEndpoint:
    """GET /health endpoint tests."""

    def test_healthy(self, client):
        """GET /health returns healthy."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestCreateAgent:
    """POST /api/v1/agents endpoint tests."""

    def test_agent_creation(self, client, mock_supabase_for_routes):
        """POST /api/v1/agents should create agent."""
        payload = {
            "name": "Test Agent",
            "description": "Description",
            "framework": "langchain",
            "category": "coding",
        }
        resp = client.post("/api/v1/agents", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["name"] == "Test Agent"
        assert "api_key" in data


class TestTrustRoute:
    """GET /api/v1/trust/route endpoint tests."""

    def test_route_recommendations(self, client, mock_supabase_for_routes):
        """GET /api/v1/trust/route returns recommendation list."""
        resp = client.get("/api/v1/trust/route?category=coding&min_tier=silver&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "recommendations" in data
        assert data["category"] == "coding"
        assert data["min_tier"] == "silver"


class TestComplianceReport:
    """GET /api/v1/agents/{id}/compliance endpoint tests."""

    def test_compliance_report(self, client, mock_supabase_for_routes):
        """Compliance report returned (mock agent-1 exists)."""
        # Fixture agents table returns agent by UUID; x-api-key required for read_auth
        resp = client.get(
            "/api/v1/agents/a1b2c3d4-e5f6-4789-a012-345678901234/compliance",
            headers={"x-api-key": "test-read-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_id" in data
        assert "sla_compliance" in data
        assert "security_risks" in data


class TestRateLimiting:
    """Rate limiting tests."""

    def test_rate_limit_429(self, client, mock_supabase_for_routes):
        """Should return 429 when limit exceeded."""
        with patch("app.api.routes.RATE_LIMITS", {"default": (120, 60), "write": (20, 60), "batch": (10, 60), "register": (2, 60)}):
            for _ in range(2):
                client.post("/api/v1/agents", json={
                    "name": "Rate Test",
                    "framework": "test",
                    "category": "other",
                })
            resp = client.post("/api/v1/agents", json={
                "name": "Rate Test 3",
                "framework": "test",
                "category": "other",
            })
            assert resp.status_code == 429
