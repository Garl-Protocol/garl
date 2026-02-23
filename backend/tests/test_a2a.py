"""
A2A v1.0 Protocol — Agent Card + JSON-RPC endpoint tests.

Validates:
- /.well-known/agent-card.json (AgentCard schema compliance)
- POST /a2a (JSON-RPC 2.0: SendMessage, GetTask)
- A2A-Version header middleware
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


MOCK_AGENT_ID = "a1b2c3d4-e5f6-4789-a012-345678901234"

MOCK_TRUST_DATA = {
    "agent_id": MOCK_AGENT_ID,
    "name": "Test Agent",
    "trust_score": 82.5,
    "success_rate": 0.95,
    "total_traces": 42,
    "verified": True,
    "risk_level": "low",
    "recommendation": "trusted",
    "certification_tier": "gold",
    "sovereign_id": f"did:garl:{MOCK_AGENT_ID}",
    "dimensions": {
        "reliability": 85.0,
        "security": 78.0,
        "speed": 80.0,
        "cost_efficiency": 75.0,
        "consistency": 82.0,
    },
    "anomalies": [],
    "last_active": "2026-02-22T10:00:00Z",
}


class TestAgentCard:
    """/.well-known/agent-card.json endpoint tests."""

    def test_agent_card_returns_200(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        assert resp.status_code == 200

    def test_agent_card_has_required_fields(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "name" in data
        assert "description" in data
        assert "supportedInterfaces" in data
        assert "version" in data
        assert "capabilities" in data
        assert "defaultInputModes" in data
        assert "defaultOutputModes" in data
        assert "skills" in data

    def test_supported_interfaces_structure(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        interfaces = resp.json()["supportedInterfaces"]
        assert len(interfaces) >= 1
        iface = interfaces[0]
        assert "url" in iface
        assert iface["protocolBinding"] == "JSONRPC"
        assert iface["protocolVersion"] == "1.0"

    def test_capabilities_no_state_transition_history(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        caps = resp.json()["capabilities"]
        assert caps["streaming"] is False
        assert caps["pushNotifications"] is False
        assert "stateTransitionHistory" not in caps

    def test_security_schemes_format(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        schemes = data["securitySchemes"]
        assert "garlApiKey" in schemes
        api_key_scheme = schemes["garlApiKey"]["apiKeySecurityScheme"]
        assert api_key_scheme["location"] == "header"
        assert api_key_scheme["name"] == "x-api-key"

    def test_security_requirements_present(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "securityRequirements" in data
        assert data["securityRequirements"] == [{"garlApiKey": []}]

    def test_skills_have_required_fields(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        skills = resp.json()["skills"]
        assert len(skills) >= 1
        for skill in skills:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill
            assert "tags" in skill
            assert isinstance(skill["tags"], list)
            assert len(skill["tags"]) >= 1


class TestA2AVersionMiddleware:
    """A2A-Version header validation tests."""

    def test_missing_version_rejected(self, client):
        resp = client.get("/.well-known/agent-card.json")
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["message"] == "VersionNotSupported"

    def test_unsupported_version_rejected(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "0.2"},
        )
        assert resp.status_code == 400

    def test_empty_version_defaults_to_03_rejected(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": ""},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"]["data"]["requested"] == "0.3"

    def test_valid_version_accepted(self, client):
        resp = client.get(
            "/.well-known/agent-card.json",
            headers={"A2A-Version": "1.0"},
        )
        assert resp.status_code == 200

    def test_non_a2a_endpoints_unaffected(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestA2AJsonRpc:
    """POST /a2a JSON-RPC endpoint tests."""

    def test_invalid_json(self, client):
        resp = client.post(
            "/a2a",
            content="not json",
            headers={"Content-Type": "application/json", "A2A-Version": "1.0"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"]["code"] == -32700

    def test_missing_jsonrpc_field(self, client):
        resp = client.post(
            "/a2a",
            json={"method": "SendMessage", "id": "1"},
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["error"]["code"] == -32600

    def test_method_not_found(self, client):
        resp = client.post(
            "/a2a",
            json={"jsonrpc": "2.0", "method": "DoSomething", "id": "1"},
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["error"]["code"] == -32601
        assert "MethodNotFound" in data["error"]["message"]

    def test_send_message_missing_message(self, client):
        resp = client.post(
            "/a2a",
            json={"jsonrpc": "2.0", "method": "SendMessage", "params": {}, "id": "1"},
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["error"]["code"] == -32602

    def test_send_message_missing_message_id(self, client):
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "1",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": "hello"}],
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["error"]["code"] == -32602
        assert "messageId" in data["error"]["data"]["detail"]

    @patch("app.api.a2a.get_a2a_trust")
    def test_send_message_trust_check(self, mock_trust, client):
        mock_trust.return_value = MOCK_TRUST_DATA.copy()

        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-1",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": f"Is agent {MOCK_AGENT_ID} trusted?"}],
                        "messageId": "msg-001",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "error" not in data
        assert data["id"] == "req-1"
        result = data["result"]
        assert "task" in result
        task = result["task"]
        assert task["status"]["state"] == "TASK_STATE_COMPLETED"
        assert len(task["artifacts"]) >= 1
        artifact = task["artifacts"][0]
        assert "artifactId" in artifact
        trust_result = artifact["parts"][0]["data"]
        assert trust_result["registered"] is True
        assert trust_result["trust_score"] == 82.5

    @patch("app.api.a2a.get_a2a_trust")
    def test_send_message_unregistered_agent(self, mock_trust, client):
        mock_trust.return_value = None

        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-2",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": f"Check trust for {MOCK_AGENT_ID}"}],
                        "messageId": "msg-002",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "error" not in data
        task = data["result"]["task"]
        assert task["status"]["state"] == "TASK_STATE_COMPLETED"
        trust_result = task["artifacts"][0]["parts"][0]["data"]
        assert trust_result["registered"] is False

    def test_send_message_register_intent(self, client):
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-3",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": "I want to register my agent"}],
                        "messageId": "msg-003",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "error" not in data
        result = data["result"]
        assert "message" in result
        msg = result["message"]
        assert msg["role"] == "ROLE_AGENT"
        assert "messageId" in msg
        assert msg["parts"][0]["data"]["endpoint"] is not None

    @patch("app.api.a2a.get_a2a_trust")
    def test_get_task_after_send(self, mock_trust, client):
        mock_trust.return_value = MOCK_TRUST_DATA.copy()

        send_resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-4",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": f"Trust score for {MOCK_AGENT_ID}"}],
                        "messageId": "msg-004",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        task_id = send_resp.json()["result"]["task"]["id"]

        get_resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "GetTask",
                "id": "req-5",
                "params": {"id": task_id},
            },
            headers={"A2A-Version": "1.0"},
        )
        data = get_resp.json()
        assert "error" not in data
        assert data["result"]["id"] == task_id
        assert data["result"]["status"]["state"] == "TASK_STATE_COMPLETED"

    def test_get_task_not_found(self, client):
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "GetTask",
                "id": "req-6",
                "params": {"id": "nonexistent-task-id"},
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["error"]["code"] == -32001
        assert "TaskNotFoundError" in data["error"]["message"]

    @patch("app.api.a2a.route_agents")
    def test_send_message_route_intent(self, mock_route, client):
        mock_route.return_value = {
            "category": "coding",
            "min_tier": "silver",
            "recommendations": [],
        }

        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-7",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": "Find best coding agent to delegate work"}],
                        "messageId": "msg-007",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "error" not in data
        task = data["result"]["task"]
        assert task["status"]["state"] == "TASK_STATE_COMPLETED"
        mock_route.assert_called_once_with("coding", "silver", 3)

    @patch("app.api.a2a.get_a2a_trust")
    def test_send_message_did_extraction(self, mock_trust, client):
        mock_trust.return_value = MOCK_TRUST_DATA.copy()

        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "SendMessage",
                "id": "req-8",
                "params": {
                    "message": {
                        "role": "ROLE_USER",
                        "parts": [{"text": f"Check did:garl:{MOCK_AGENT_ID}"}],
                        "messageId": "msg-008",
                    }
                },
            },
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert "error" not in data
        mock_trust.assert_called_once_with(MOCK_AGENT_ID)

    def test_response_has_correct_jsonrpc_format(self, client):
        resp = client.post(
            "/a2a",
            json={"jsonrpc": "2.0", "method": "SendMessage", "params": {}, "id": 42},
            headers={"A2A-Version": "1.0"},
        )
        data = resp.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 42
