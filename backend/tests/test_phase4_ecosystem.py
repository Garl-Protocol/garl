"""Phase 4 — audit export formats: in-toto DSSE, SLSA v1.1 Statement."""
import base64
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


AGENT_ID = "a1b2c3d4-e5f6-4789-a012-345678901234"
TRACE_HASH = "6ff83db816ac25bc0daff2f4ccd3671ba1b3704cdeb638d3fb43937c56dfa992"


def _fake_agent():
    return {
        "id": AGENT_ID,
        "name": "Test Agent",
        "sovereign_id": "did:garl:test",
    }


def _fake_trace_rows():
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "trace_hash": TRACE_HASH,
            "task_description": "Implement login page",
            "status": "success",
            "category": "coding",
            "duration_ms": 1200,
            "cost_usd": 0.02,
            "token_count": 500,
            "created_at": "2026-04-15T10:00:00Z",
            "certificate": {
                "@type": "CertifiedExecutionTrace",
                "proof": {
                    "type": "ECDSA-secp256k1",
                    "created": 1776269706,
                    "key_id": "8c6e8f25ef3bf704",
                    "publicKey": "b7c8a722" + "0" * 120,
                    "signature": "ab" * 32,
                },
            },
        }
    ]


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def gte(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def execute(self):
        class _Res:
            def __init__(self, rows):
                self.data = rows
        return _Res(self._rows)


@pytest.fixture
def client_with_trace_rows():
    rows = _fake_trace_rows()
    with patch("app.api.routes.get_agent", return_value=_fake_agent()), \
         patch("app.api.routes._get_supabase") as mock_db:
        mock_db.return_value.table.return_value = _FakeTable(rows)
        yield TestClient(app)


class TestInTotoFormat:
    def test_returns_dsse_envelopes_with_ai_authorship_predicate(self, client_with_trace_rows):
        r = client_with_trace_rows.get(
            f"/api/v1/agents/{AGENT_ID}/audit?format=in-toto&days=30"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["@type"] == "GarlAuditReport.InToto"
        assert body["predicate_type"] == "https://garl.ai/ai-authorship/v1"
        assert body["envelope_count"] == 1
        env = body["envelopes"][0]
        assert env["payloadType"] == "application/vnd.in-toto+json"
        # Decode payload and check the Statement shape
        payload = json.loads(base64.b64decode(env["payload"]))
        assert payload["_type"] == "https://in-toto.io/Statement/v1"
        assert payload["predicateType"] == "https://garl.ai/ai-authorship/v1"
        assert payload["subject"][0]["digest"]["sha256"] == TRACE_HASH
        assert payload["predicate"]["agent_id"] == AGENT_ID
        assert payload["predicate"]["status"] == "success"
        # Signature is base64 of the hex bytes
        sig = env["signatures"][0]
        assert sig["keyid"] == "8c6e8f25ef3bf704"
        assert base64.b64decode(sig["sig"]) == bytes.fromhex("ab" * 32)


class TestSLSAv1_1Format:
    def test_returns_slsa_provenance_statements(self, client_with_trace_rows):
        r = client_with_trace_rows.get(
            f"/api/v1/agents/{AGENT_ID}/audit?format=slsa-v1.1&days=30"
        )
        assert r.status_code == 200
        body = r.json()
        assert body["@type"] == "GarlAuditReport.SLSAv1_1"
        assert body["predicate_type"] == "https://slsa.dev/provenance/v1"
        assert body["statement_count"] == 1
        stmt = body["statements"][0]
        assert stmt["_type"] == "https://in-toto.io/Statement/v1"
        assert stmt["predicateType"] == "https://slsa.dev/provenance/v1"
        pred = stmt["predicate"]
        assert pred["buildDefinition"]["buildType"] == "https://garl.ai/ai-authorship/v1"
        assert pred["runDetails"]["metadata"]["invocationId"] == "11111111-1111-1111-1111-111111111111"
        assert pred["garl"]["key_id"] == "8c6e8f25ef3bf704"
        assert pred["garl"]["signing_epoch"] == "original"


class TestFormatValidation:
    def test_unknown_format_rejected(self, client_with_trace_rows):
        r = client_with_trace_rows.get(
            f"/api/v1/agents/{AGENT_ID}/audit?format=bogus&days=1"
        )
        assert r.status_code == 400
        assert "csv, jsonld, in-toto, slsa-v1.1" in r.json()["detail"]
