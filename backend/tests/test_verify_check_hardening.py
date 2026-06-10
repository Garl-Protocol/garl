"""Regression tests for the 2026-06-10 adversarial hardening pass.

H1 — /verify/check passport branch must reject a passport signed by a key
     that is not in the GARL registry (self-vouched-key forgery).
H2 — the shipped offline verifier (sdks/python/garl_verify.py) must be able
     to verify a v0.1 Action Receipt envelope, and reject tampered/foreign ones.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from ecdsa import SECP256k1, SigningKey
from fastapi.testclient import TestClient

from app.core import signing
from app.main import app


class TestVerifyCheckPassportBranch:
    """H1: the passport branch of /verify/check trusted a caller-supplied
    public_key, letting anyone forge a 'valid' GARL trust passport."""

    def _passport_payload(self) -> dict:
        return {
            "version": "1.0",
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "agent_name": "attacker",
            "trust_score": 99.99,
            "certification_tier": "enterprise",
            "issuer": "garl-protocol",
        }

    def test_forged_passport_with_foreign_key_rejected(self):
        # Attacker signs a self-serving passport with their OWN key and submits
        # their own public_key. Must NOT verify.
        foreign = SigningKey.generate(curve=SECP256k1)
        payload = self._passport_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).digest()
        sig = foreign.sign_digest_deterministic(digest, hashfunc=hashlib.sha256).hex()
        body = {
            "passport": payload,
            "signature": sig,
            "public_key": foreign.get_verifying_key().to_string().hex(),
        }
        resp = TestClient(app).post("/api/v1/verify/check", json=body)
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_forged_passport_without_public_key_rejected(self):
        # Even omitting public_key (so the old code fell back to GARL's key)
        # must not validate an attacker signature.
        foreign = SigningKey.generate(curve=SECP256k1)
        payload = self._passport_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).digest()
        sig = foreign.sign_digest_deterministic(digest, hashfunc=hashlib.sha256).hex()
        body = {"passport": payload, "signature": sig}
        resp = TestClient(app).post("/api/v1/verify/check", json=body)
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_genuine_passport_accepted(self):
        # A passport signed by GARL's own key must still verify.
        signing._signing_key = None
        payload = self._passport_payload()
        sig, _ = signing.sign_payload(payload)
        body = {"passport": payload, "signature": sig}
        resp = TestClient(app).post("/api/v1/verify/check", json=body)
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


def _load_garl_verify():
    path = Path(__file__).resolve().parents[2] / "sdks" / "python" / "garl_verify.py"
    spec = importlib.util.spec_from_file_location("garl_verify", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReceiptEnvelopeVerifier:
    """H2: the v0.1 Action Receipt envelope was structurally unverifiable by
    the shipped garl-verify tool. It must now round-trip."""

    def _signed_envelope(self) -> dict:
        signing._signing_key = None
        envelope = {
            "receipt_id": "00000000-0000-0000-0000-0000000000aa",
            "version": "garl/action-receipt/v0.1",
            "issuer": "https://api.garl.ai",
            "agent_identity": "did:garl:00000000-0000-0000-0000-0000000000bb",
            "runtime": "claude-code",
            "protocol": "raw-http",
            "action_type": "code_write",
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "side_effect": "irreversible",
            "timestamp": "2026-06-10T00:00:00Z",
        }
        sig, _ = signing.sign_payload(envelope)
        envelope["signature"] = sig
        envelope["verification_key_id"] = signing.get_active_key_id()
        return envelope

    def test_envelope_is_detected(self):
        gv = _load_garl_verify()
        assert gv._is_receipt_envelope(self._signed_envelope()) is True
        # A legacy trace cert (proof-wrapped) is NOT a receipt envelope.
        assert gv._is_receipt_envelope({"payload": {}, "proof": {}}) is False

    def test_genuine_envelope_verifies(self):
        gv = _load_garl_verify()
        env = self._signed_envelope()
        pk = signing.get_public_key_hex()
        assert gv._verify_receipt_envelope(env, pk) is True

    def test_tampered_envelope_rejected(self):
        gv = _load_garl_verify()
        env = self._signed_envelope()
        env["side_effect"] = "reversible"  # flip a signed field
        pk = signing.get_public_key_hex()
        assert gv._verify_receipt_envelope(env, pk) is False

    def test_foreign_key_rejected(self):
        gv = _load_garl_verify()
        env = self._signed_envelope()
        foreign = SigningKey.generate(curve=SECP256k1)
        assert gv._verify_receipt_envelope(
            env, foreign.get_verifying_key().to_string().hex()
        ) is False
