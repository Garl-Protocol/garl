"""Phase 6 — policy gate + multi-model attestation."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app


AGENT_ID = "a1b2c3d4-e5f6-4789-a012-345678901234"
FULL_HASH = "a" * 64


def _mk_trace(models=None, tier="gold", score=80, cert=None):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "agent_id": AGENT_ID,
        "trace_hash": FULL_HASH,
        "metadata": {"models": models} if models else {},
        "certificate": cert if cert is not None else {"proof": {}},
    }


def _mk_agent(score=80, tier="gold"):
    return {
        "id": AGENT_ID,
        "name": "Policy Probe",
        "trust_score": score,
        "certification_tier": tier,
    }


def _install_db(traces, agents):
    mock_db = MagicMock()

    def table_side_effect(name):
        t = MagicMock()

        class _Res:
            pass

        res = _Res()
        if name == "traces":
            res.data = traces
        elif name == "agents":
            res.data = agents
        else:
            res.data = []
        t.select.return_value = t
        t.eq.return_value = t
        t.like.return_value = t
        t.limit.return_value = t
        t.execute.return_value = res
        return t

    mock_db.table.side_effect = table_side_effect
    return mock_db


@pytest.fixture
def client():
    return TestClient(app)


class TestPolicyCheck:
    def test_pass_when_score_and_tier_met(self, client):
        traces = [_mk_trace()]
        agents = [_mk_agent(score=80, tier="gold")]
        with patch("app.api.routes._get_supabase", return_value=_install_db(traces, agents)):
            r = client.post(
                "/api/v1/policy/check",
                json={"policy": {"min_score": 60, "min_tier": "silver"}, "receipts": [FULL_HASH]},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["pass"] is True
        assert body["evaluations"][0]["pass"] is True

    def test_fail_when_score_below_min(self, client):
        traces = [_mk_trace()]
        agents = [_mk_agent(score=40, tier="bronze")]
        with patch("app.api.routes._get_supabase", return_value=_install_db(traces, agents)):
            r = client.post(
                "/api/v1/policy/check",
                json={"policy": {"min_score": 60}, "receipts": [FULL_HASH]},
            )
        body = r.json()
        assert body["pass"] is False
        assert any("score_below_min" in x for x in body["evaluations"][0]["reasons"])

    def test_fail_when_model_disclosure_required_but_missing(self, client):
        traces = [_mk_trace(models=None)]
        agents = [_mk_agent()]
        with patch("app.api.routes._get_supabase", return_value=_install_db(traces, agents)):
            r = client.post(
                "/api/v1/policy/check",
                json={"policy": {"require_model_disclosure": True}, "receipts": [FULL_HASH]},
            )
        body = r.json()
        assert body["pass"] is False
        assert "no_model_disclosure" in body["evaluations"][0]["reasons"]

    def test_pass_when_allowed_model_listed(self, client):
        traces = [_mk_trace(models=[{"name": "claude-opus-4-6"}])]
        agents = [_mk_agent()]
        with patch("app.api.routes._get_supabase", return_value=_install_db(traces, agents)):
            r = client.post(
                "/api/v1/policy/check",
                json={
                    "policy": {"allowed_models": ["claude-opus-4-6", "claude-sonnet-4-6"]},
                    "receipts": [FULL_HASH],
                },
            )
        body = r.json()
        assert body["pass"] is True
        assert body["evaluations"][0]["models"] == ["claude-opus-4-6"]

    def test_fail_when_forbidden_model_present(self, client):
        traces = [_mk_trace(models=[{"name": "gpt-4o"}, {"name": "claude-sonnet-4-6"}])]
        agents = [_mk_agent()]
        with patch("app.api.routes._get_supabase", return_value=_install_db(traces, agents)):
            r = client.post(
                "/api/v1/policy/check",
                json={"policy": {"forbidden_models": ["gpt-4o"]}, "receipts": [FULL_HASH]},
            )
        body = r.json()
        assert body["pass"] is False
        assert any("forbidden_model_present" in x for x in body["evaluations"][0]["reasons"])

    def test_receipt_not_found(self, client):
        with patch("app.api.routes._get_supabase", return_value=_install_db([], [])):
            r = client.post(
                "/api/v1/policy/check",
                json={"policy": {}, "receipts": ["b" * 64]},
            )
        body = r.json()
        assert body["pass"] is False
        assert "receipt_not_found" in body["evaluations"][0]["reasons"]

    def test_invalid_hash_format(self, client):
        r = client.post(
            "/api/v1/policy/check",
            json={"policy": {}, "receipts": ["NOTHEX"]},
        )
        body = r.json()
        assert body["evaluations"][0]["reasons"] == ["invalid_hash_format"]

    def test_empty_receipts_400(self, client):
        r = client.post("/api/v1/policy/check", json={"policy": {}, "receipts": []})
        assert r.status_code == 400


class TestModelAttestationSchema:
    def test_models_schema_accepts_multi_model_payload(self):
        from app.models.schemas import TraceSubmitRequest
        req = TraceSubmitRequest(
            agent_id="00000000-0000-0000-0000-000000000000",
            task_description="impl",
            status="success",
            duration_ms=1,
            models=[
                {"name": "claude-opus-4-6", "version": "1m", "role": "primary-author", "detection_confidence": 0.95},
                {"name": "copilot", "version": "n/a", "role": "reviewer"},
            ],
        )
        assert len(req.models) == 2
        assert req.models[0].name == "claude-opus-4-6"
        assert req.models[1].role == "reviewer"
