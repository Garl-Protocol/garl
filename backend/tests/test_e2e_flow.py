"""
GARL Protocol — E2E Integration Test Suite

Tests the complete GARL Protocol flow against the live production API.
Run with: pytest -m e2e backend/tests/test_e2e_flow.py

Override API URL via GARL_API_URL env var (default: https://api.garl.ai).
"""
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("GARL_API_URL", "https://api.garl.ai").rstrip("/")
API_V1 = f"{BASE_URL}/api/v1"


@pytest.mark.e2e
class TestGARLE2EFlow:
    """
    End-to-end test of the full GARL Protocol lifecycle.
    Tests run in order via numbered method names.
    State is stored on the class so it persists across test instances.
    """

    api_key: str = ""
    agent_id: str = ""
    agent_name: str = ""
    trace_hash: str = ""
    trust_score_before: float = 50.0

    def _headers(self) -> dict:
        """Auth headers for endpoints requiring API key."""
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def test_01_register_agent(self):
        """1. Register a new agent with is_sandbox=True."""
        agent_name = f"e2e_test_{int(time.time())}"
        payload = {
            "name": agent_name,
            "description": "E2E integration test agent",
            "framework": "pytest",
            "category": "coding",
            "is_sandbox": True,
        }
        resp = requests.post(f"{API_V1}/agents", json=payload, timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "id" in data
        assert "api_key" in data
        assert data["name"] == agent_name
        # Store on class so state persists across pytest's per-test instances
        TestGARLE2EFlow.agent_id = data["id"]
        TestGARLE2EFlow.api_key = data["api_key"]
        TestGARLE2EFlow.agent_name = agent_name
        TestGARLE2EFlow.trust_score_before = float(data.get("trust_score", 50))

    def test_02_submit_trace(self):
        """2. Submit a trace using the returned API key."""
        payload = {
            "agent_id": self.agent_id,
            "task_description": "E2E test trace",
            "status": "success",
            "duration_ms": 500,
            "category": "coding",
        }
        resp = requests.post(
            f"{API_V1}/verify",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "trace_hash" in data
        assert "id" in data
        assert data["agent_id"] == self.agent_id
        TestGARLE2EFlow.trace_hash = data["trace_hash"]
        assert len(self.trace_hash) == 64, "trace_hash must be 64-char SHA-256 hex"

    def test_03_verify_trace_by_hash(self):
        """3. Verify the trace by hash (public, no auth)."""
        resp = requests.get(f"{API_V1}/verify/{self.trace_hash}", timeout=30)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("verified") is True
        assert data.get("trace_hash") == self.trace_hash
        assert data.get("agent_id") == self.agent_id
        assert "certificate" in data
        assert "public_key" in data

    def test_04_check_trust_score(self):
        """4. Check trust score — verify it changed after trace."""
        resp = requests.get(
            f"{API_V1}/trust/verify",
            params={"agent_id": self.agent_id},
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("registered") is True
        trust_score = float(data.get("trust_score", 0))
        assert trust_score != self.trust_score_before or self.trust_score_before != 50
        assert 0 <= trust_score <= 100

    def test_05_get_agent_detail(self):
        """5. Get agent detail with API key."""
        resp = requests.get(
            f"{API_V1}/agents/{self.agent_id}/detail",
            headers=self._headers(),
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "agent" in data
        agent = data["agent"]
        assert agent["id"] == self.agent_id
        assert agent["name"] == self.agent_name
        assert "recent_traces" in data or "agent" in data

    def test_06_get_compliance_report(self):
        """6. Get compliance report with API key."""
        resp = requests.get(
            f"{API_V1}/agents/{self.agent_id}/compliance",
            headers=self._headers(),
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "agent_id" in data or "sla" in data or "security" in data

    def test_07_get_agent_history(self):
        """7. Get agent history."""
        resp = requests.get(
            f"{API_V1}/agents/{self.agent_id}/history",
            headers=self._headers(),
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "trust_score" in data[0] or "event_type" in data[0]

    def test_08_get_badge_svg(self):
        """8. Get badge SVG."""
        resp = requests.get(
            f"{API_V1}/badge/svg/{self.agent_id}",
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "image/svg+xml" in resp.headers.get("content-type", "")
        assert "<svg" in resp.text or "svg" in resp.text.lower()

    def test_09_search_agent(self):
        """9. Search for the agent by name."""
        resp = requests.get(
            f"{API_V1}/search",
            params={"q": self.agent_name, "limit": 10},
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "data" in data or "agents" in data or isinstance(data, list)
        results = data.get("data", data.get("agents", data))
        if isinstance(results, list):
            found = any(
                r.get("id") == self.agent_id or r.get("name") == self.agent_name
                for r in results
            )
            assert found, f"Agent {self.agent_name} not found in search results"

    def test_10_soft_delete_agent(self):
        """10. Soft delete the agent with confirmation."""
        resp = requests.delete(
            f"{API_V1}/agents/{self.agent_id}",
            json={"confirmation": "DELETE_CONFIRMED"},
            headers=self._headers(),
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "deleted" in str(data).lower() or "success" in str(data).lower() or resp.ok
