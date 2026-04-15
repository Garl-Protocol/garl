"""Dalga 1 — B2 + M3 + M4:
  - /verify returns the STORED certificate, no re-sign, no bogus trust_score_after=50
  - ECDSA is RFC 6979 deterministic (same input → same signature bytes)
  - /receipts/{hash}/cert.json returns raw stored cert
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core import signing
from app.main import app


AGENT_ID = "3216b8ed-fa2c-452a-bda2-925cde273314"
FULL_HASH = "6ff83db816ac25bc0daff2f4ccd3671ba1b3704cdeb638d3fb43937c56dfa992"


class TestDeterministicEcdsa:
    def test_sign_trace_is_deterministic(self):
        signing._signing_key = None  # force re-load
        cert1 = signing.sign_trace({"task": "demo", "n": 1})
        cert2 = signing.sign_trace({"task": "demo", "n": 1})
        assert cert1["proof"]["signature"] == cert2["proof"]["signature"]

    def test_sign_payload_is_deterministic(self):
        signing._signing_key = None
        sig1, hash1 = signing.sign_payload({"a": 1, "b": 2})
        sig2, hash2 = signing.sign_payload({"a": 1, "b": 2})
        assert sig1 == sig2
        assert hash1 == hash2

    def test_different_payload_different_signature(self):
        c1 = signing.sign_trace({"task": "a"})
        c2 = signing.sign_trace({"task": "b"})
        assert c1["proof"]["signature"] != c2["proof"]["signature"]


class TestVerifyReturnsStoredCert:
    def _fake_trace_with_cert(self, trust_score_after=79.88):
        proof_payload = {
            "trust_score_after": trust_score_after,
            "agent_id": AGENT_ID,
            "trace_id": "11111111-1111-1111-1111-111111111111",
        }
        trace_data = {"trust_score_after": trust_score_after, "task": "x"}
        cert = signing.sign_trace(trace_data)
        return {
            "id": "11111111-1111-1111-1111-111111111111",
            "agent_id": AGENT_ID,
            "trace_hash": FULL_HASH,
            "task_description": "t",
            "status": "success",
            "duration_ms": 1000,
            "category": "coding",
            "created_at": "2026-04-15T10:00:00Z",
            "certificate": cert,
        }

    def _fake_pre_v03_trace(self):
        # empty certificate means pre-v0.3 unsigned legacy
        return {
            "id": "22222222-2222-2222-2222-222222222222",
            "agent_id": AGENT_ID,
            "trace_hash": "a" * 64,
            "task_description": "legacy",
            "status": "success",
            "duration_ms": 0,
            "category": "other",
            "created_at": "2026-02-01T00:00:00Z",
            "certificate": {},
        }

    def _fake_agent(self):
        return {"name": "T", "framework": "custom", "certification_tier": "gold", "trust_score": 79.88}

    def _install_db(self, trace_rows, agent_rows):
        db = MagicMock()

        def table_side_effect(name):
            t = MagicMock()
            class R: pass
            r = R()
            r.data = trace_rows if name == "traces" else agent_rows
            t.select.return_value = t
            t.eq.return_value = t
            t.like.return_value = t
            t.limit.return_value = t
            t.execute.return_value = r
            return t

        db.table.side_effect = table_side_effect
        return db

    def test_verify_returns_stored_signature_byte_for_byte(self):
        signing._signing_key = None
        trace = self._fake_trace_with_cert(trust_score_after=79.88)
        stored_sig = trace["certificate"]["proof"]["signature"]
        agent = self._fake_agent()
        client = TestClient(app)
        with patch("app.api.routes._get_supabase", return_value=self._install_db([trace], [agent])):
            r1 = client.get(f"/api/v1/verify/{FULL_HASH}")
            r2 = client.get(f"/api/v1/verify/{FULL_HASH}")
        assert r1.status_code == 200
        assert r1.json()["certificate"]["proof"]["signature"] == stored_sig
        assert r2.json()["certificate"]["proof"]["signature"] == stored_sig
        # No bogus trust_score_after=50
        payload = r1.json()["certificate"]["payload"]
        assert payload.get("trust_score_after") == 79.88

    def test_pre_v03_verify_does_not_fabricate_signature(self):
        trace = self._fake_pre_v03_trace()
        agent = self._fake_agent()
        client = TestClient(app)
        with patch("app.api.routes._get_supabase", return_value=self._install_db([trace], [agent])):
            r = client.get(f"/api/v1/verify/{'a' * 64}")
        assert r.status_code == 200
        body = r.json()
        assert body["signing_epoch"] == "pre-v0.3-unsigned-legacy"
        assert body["verified"] is False
        # No fake proof — the certificate has no `proof` key for unsigned legacy
        assert "proof" not in body["certificate"]


class TestRawReceiptEndpoint:
    def test_returns_stored_cert_as_is(self):
        signing._signing_key = None
        cert = signing.sign_trace({"task": "hello"})
        trace = {"trace_hash": FULL_HASH, "certificate": cert}
        db = MagicMock()
        t = MagicMock()
        class R: pass
        r = R(); r.data = [trace]
        t.select.return_value = t
        t.eq.return_value = t
        t.like.return_value = t
        t.limit.return_value = t
        t.execute.return_value = r
        db.table.return_value = t
        with patch("app.api.routes._get_supabase", return_value=db):
            resp = TestClient(app).get(f"/api/v1/receipts/{FULL_HASH}/cert.json")
        assert resp.status_code == 200
        assert resp.json()["proof"]["signature"] == cert["proof"]["signature"]
        assert "immutable" in resp.headers.get("Cache-Control", "")

    def test_pre_v03_returns_404(self):
        trace = {"trace_hash": "a" * 64, "certificate": {}}
        db = MagicMock()
        t = MagicMock()
        class R: pass
        r = R(); r.data = [trace]
        t.select.return_value = t
        t.eq.return_value = t
        t.like.return_value = t
        t.limit.return_value = t
        t.execute.return_value = r
        db.table.return_value = t
        with patch("app.api.routes._get_supabase", return_value=db):
            resp = TestClient(app).get(f"/api/v1/receipts/{'a' * 64}/cert.json")
        assert resp.status_code == 404
        assert "pre-v0.3" in resp.json()["detail"]

    def test_unknown_hash_returns_404(self):
        db = MagicMock()
        t = MagicMock()
        class R: pass
        r = R(); r.data = []
        t.select.return_value = t
        t.eq.return_value = t
        t.like.return_value = t
        t.limit.return_value = t
        t.execute.return_value = r
        db.table.return_value = t
        with patch("app.api.routes._get_supabase", return_value=db):
            resp = TestClient(app).get(f"/api/v1/receipts/{'b' * 64}/cert.json")
        assert resp.status_code == 404

    def test_bad_hash_format_returns_400(self):
        resp = TestClient(app).get("/api/v1/receipts/NOT_HEX/cert.json")
        assert resp.status_code == 400
