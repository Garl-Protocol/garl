"""Regression tests for the 2026-06-08 security hardening pass."""
import hashlib
import json
from unittest.mock import MagicMock, patch

from ecdsa import SECP256k1, SigningKey

from app.core import signing


class TestVerifySignatureKeyRegistry:
    """M4: verify_signature must only trust keys in the GARL registry, not
    whatever publicKey is embedded in the cert."""

    def test_foreign_key_cert_rejected(self):
        # A cert that is internally self-consistent but signed by a key GARL
        # never issued must NOT verify (would otherwise pass /verify/check).
        foreign = SigningKey.generate(curve=SECP256k1)
        payload = {"task": "anything", "n": 1}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).digest()
        sig = foreign.sign_digest_deterministic(digest, hashfunc=hashlib.sha256).hex()
        cert = {
            "payload": payload,
            "proof": {"publicKey": foreign.get_verifying_key().to_string().hex(),
                      "signature": sig},
        }
        assert signing.verify_signature(cert) is False

    def test_genuine_garl_cert_accepted(self):
        signing._signing_key = None  # reset so it picks up the configured key
        cert = signing.sign_trace({"task": "real", "n": 2})
        assert signing.verify_signature(cert) is True


class TestRevocationFailClosed:
    """M2: an unknown token_hash must be treated as revoked (fail closed)."""

    def test_unknown_token_is_revoked(self):
        from app.services import capability_tokens

        db = MagicMock()
        t = MagicMock()
        r = MagicMock(); r.data = []
        t.select.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t
        t.execute.return_value = r
        db.table.return_value = t
        with patch.object(capability_tokens, "_get_supabase", return_value=db):
            assert capability_tokens._is_revoked("d" * 64) is True

    def test_known_unrevoked_token_not_revoked(self):
        from app.services import capability_tokens

        db = MagicMock()
        t = MagicMock()
        r = MagicMock(); r.data = [{"revoked_at": None}]
        t.select.return_value = t
        t.eq.return_value = t
        t.limit.return_value = t
        t.execute.return_value = r
        db.table.return_value = t
        with patch.object(capability_tokens, "_get_supabase", return_value=db):
            assert capability_tokens._is_revoked("e" * 64) is False
