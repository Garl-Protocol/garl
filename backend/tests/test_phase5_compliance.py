"""Phase 5 — compliance audit formats (CA SB 942, ISO 42001 Annex B, C2PA-adjacent)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


AGENT_ID = "a1b2c3d4-e5f6-4789-a012-345678901234"


def _fake_agent():
    return {
        "id": AGENT_ID,
        "name": "Compliance Probe",
        "framework": "langchain",
        "sovereign_id": "did:garl:test",
    }


def _fake_rows():
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "trace_hash": "6ff83db816ac25bc0daff2f4ccd3671ba1b3704cdeb638d3fb43937c56dfa992",
            "task_description": "Implement checkout flow",
            "status": "success",
            "category": "coding",
            "duration_ms": 3200,
            "cost_usd": 0.05,
            "token_count": 1400,
            "created_at": "2026-04-15T10:00:00Z",
            "certificate": {
                "proof": {
                    "type": "ECDSA-secp256k1",
                    "created": 1776269706,
                    "key_id": "8c6e8f25ef3bf704",
                    "publicKey": "b7c8a722" + "0" * 120,
                    "signature": "ab" * 32,
                }
            },
        }
    ]


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
    def select(self, *a, **kw): return self
    def eq(self, *a, **kw): return self
    def gte(self, *a, **kw): return self
    def order(self, *a, **kw): return self
    def limit(self, *a, **kw): return self
    def execute(self):
        class _R: data = self._rows
        return _R()


@pytest.fixture
def client():
    rows = _fake_rows()
    with patch("app.api.routes.get_agent", return_value=_fake_agent()), \
         patch("app.api.routes._get_supabase") as mock_db:
        mock_db.return_value.table.return_value = _FakeTable(rows)
        yield TestClient(app)


class TestCaSb942:
    def test_returns_sb942_records(self, client):
        r = client.get(f"/api/v1/agents/{AGENT_ID}/audit?format=ca-sb942&days=30")
        assert r.status_code == 200
        body = r.json()
        assert body["@type"] == "GarlAuditReport.CaliforniaSB942"
        assert body["regulation"].startswith("California SB 942")
        rec = body["records"][0]
        assert rec["record_type"] == "ai_generated_content_disclosure"
        assert rec["ai_system_name"].startswith("Compliance Probe")
        assert rec["provenance"]["signature_algorithm"] == "ECDSA-secp256k1"
        assert rec["provenance"]["key_id"] == "8c6e8f25ef3bf704"
        assert rec["provenance"]["receipt_url"].endswith("/r/6ff83db8")


class TestIso42001AnnexB:
    def test_returns_control_mapped_records(self, client):
        r = client.get(
            f"/api/v1/agents/{AGENT_ID}/audit?format=iso42001-annexb&days=30"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["@type"] == "GarlAuditReport.ISO42001AnnexB"
        assert "A.6.2" in body["controls_covered"]
        rec = body["records"][0]
        assert rec["evidence_type"] == "ai_system_execution_record"
        assert "A.6.2.5" in rec["controls"]
        assert rec["data_provenance"]["signature_algorithm"] == "ECDSA-secp256k1"


class TestC2paAdjacent:
    def test_returns_content_credentials_like_manifests(self, client):
        r = client.get(f"/api/v1/agents/{AGENT_ID}/audit?format=c2pa&days=30")
        assert r.status_code == 200
        body = r.json()
        assert body["@type"] == "GarlAuditReport.C2PA"
        m = body["manifests"][0]
        assert m["claim_generator"].startswith("GARL-Protocol/")
        acts = m["assertions"][0]["data"]["actions"]
        assert acts[0]["action"] == "c2pa.created"
        hash_assertion = m["assertions"][1]
        assert hash_assertion["label"] == "c2pa.hash.data"
        assert hash_assertion["alg"] == "sha256"
        assert m["signature"]["alg"] == "ES256K"
