"""Route tests for the Evidence Pack API surface (app/api/evidence_routes.py).

Both endpoints are public reads (receipts are public evidence). The pack
builder is patched at its service home (the routes import it lazily), so
these tests cover HTTP semantics: status codes, content types, headers.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.evidence_pack import EVIDENCE_PACK_VERSION

RECEIPT_ID = "22222222-2222-2222-2222-222222222222"

PACK = {
    "version": EVIDENCE_PACK_VERSION,
    "generated_at": "2026-08-04T00:00:00Z",
    "issuer": "https://api.garl.ai",
    "receipt": {
        "receipt_id": RECEIPT_ID,
        "agent_identity": "did:garl:11111111-1111-1111-1111-111111111111",
        "action_type": "tool_call",
        "side_effect": "none",
        "input_hash": "1" * 64,
        "output_hash": "c" * 64,
        "timestamp": "2026-08-03T12:00:00Z",
        "signature": "f0" * 32,
        "verification_key_id": "deadbeefdeadbeef",
    },
    "capability_chain": [],
    "merkle_proof": None,
    "anchor": None,
    "session_alerts": [],
    "key_registry": {"keys": []},
    "verification": {"offline_steps": ["1. verify the signature"]},
    "retention": {"policy": "retain >= 6 months per Art. 19(1)", "exported_by": None},
    "signature": "ab" * 32,
    "verification_key_id": "deadbeefdeadbeef",
}


@pytest.fixture
def client():
    return TestClient(app)


class TestEvidencePackJson:
    def test_200_returns_signed_pack(self, client):
        with patch("app.services.evidence_pack.build_evidence_pack",
                   return_value=PACK) as build:
            resp = client.get(f"/api/v1/receipts/{RECEIPT_ID}/evidence-pack")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        body = resp.json()
        assert body["version"] == EVIDENCE_PACK_VERSION
        assert body["receipt"]["receipt_id"] == RECEIPT_ID
        assert body["signature"] == PACK["signature"]
        build.assert_called_once_with(RECEIPT_ID)

    def test_404_when_receipt_unknown(self, client):
        with patch("app.services.evidence_pack.build_evidence_pack",
                   return_value=None):
            resp = client.get("/api/v1/receipts/no-such-receipt/evidence-pack")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Receipt not found"


class TestEvidencePackPdf:
    def test_200_returns_pdf_attachment(self, client):
        with patch("app.services.evidence_pack.build_evidence_pack",
                   return_value=PACK):
            resp = client.get(f"/api/v1/receipts/{RECEIPT_ID}/evidence-pack.pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")
        cd = resp.headers["content-disposition"]
        assert cd.startswith("attachment;")
        # short id = first 8 header-safe chars of the receipt_id
        assert 'filename="garl-evidence-22222222.pdf"' in cd

    def test_404_when_receipt_unknown(self, client):
        with patch("app.services.evidence_pack.build_evidence_pack",
                   return_value=None):
            resp = client.get("/api/v1/receipts/no-such-receipt/evidence-pack.pdf")
        assert resp.status_code == 404

    def test_pdf_path_does_not_shadow_json_path(self, client):
        # both endpoints resolve independently for the same receipt id
        with patch("app.services.evidence_pack.build_evidence_pack",
                   return_value=PACK):
            json_resp = client.get(f"/api/v1/receipts/{RECEIPT_ID}/evidence-pack")
            pdf_resp = client.get(f"/api/v1/receipts/{RECEIPT_ID}/evidence-pack.pdf")
        assert json_resp.headers["content-type"].startswith("application/json")
        assert pdf_resp.headers["content-type"] == "application/pdf"
