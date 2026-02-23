"""
GARL Protocol v1.0 — Tests for signing.py module.

Tests ECDSA signing, certificate structure, and verification functions.
"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.signing import (
    sign_trace,
    verify_signature,
    get_public_key_hex,
    _get_signing_key,
)


class TestSignTrace:
    """sign_trace function tests."""

    def test_valid_certificate_structure(self):
        """sign_trace should produce valid certificate structure (payload, proof, signature)."""
        trace_data = {"agent_id": "test-123", "status": "success", "score": 75.5}
        cert = sign_trace(trace_data)

        assert "@context" in cert
        assert cert["@context"] == "https://garl.io/schema/v1"
        assert cert["@type"] == "CertifiedExecutionTrace"
        assert cert["payload"] == trace_data
        assert "proof" in cert
        assert "type" in cert["proof"]
        assert cert["proof"]["type"] == "ECDSA-secp256k1"
        assert "created" in cert["proof"]
        assert "publicKey" in cert["proof"]
        assert "signature" in cert["proof"]
        assert isinstance(cert["proof"]["publicKey"], str)
        assert isinstance(cert["proof"]["signature"], str)
        assert len(cert["proof"]["signature"]) > 0

    def test_different_payloads_different_signatures(self):
        """Different payloads should produce different signatures."""
        cert1 = sign_trace({"a": 1})
        cert2 = sign_trace({"a": 2})
        assert cert1["proof"]["signature"] != cert2["proof"]["signature"]


class TestVerifySignature:
    """verify_signature function tests."""

    def test_valid_certificate_returns_true(self):
        """Valid signed certificate verification should return True."""
        trace_data = {"test": "data", "value": 42}
        cert = sign_trace(trace_data)
        assert verify_signature(cert) is True

    def test_tampered_payload_returns_false(self):
        """Should return False if payload is tampered."""
        cert = sign_trace({"original": "data"})
        cert["payload"]["original"] = "tampered"
        assert verify_signature(cert) is False

    def test_tampered_signature_returns_false(self):
        """Should return False if signature is tampered."""
        cert = sign_trace({"data": "valid"})
        cert["proof"]["signature"] = "0" * 128  # Invalid signature
        assert verify_signature(cert) is False

    def test_missing_proof_returns_false(self):
        """Should return False if proof is missing."""
        cert = {"payload": {"a": 1}, "proof": {}}
        assert verify_signature(cert) is False


class TestGetPublicKeyHex:
    """get_public_key_hex function tests."""

    def test_returns_hex_string(self):
        """Should return public key string in hex format (0-9, a-f)."""
        key_hex = get_public_key_hex()
        assert isinstance(key_hex, str)
        assert len(key_hex) > 0
        # Valid hex characters: 0-9, a-f
        assert all(c in "0123456789abcdef" for c in key_hex.lower())


class TestGetSigningKey:
    """_get_signing_key function tests (debug off, no key)."""

    def test_runtime_error_when_no_key_debug_off(self):
        """Should raise RuntimeError when debug is off and SIGNING_PRIVATE_KEY_HEX is missing."""
        with patch("app.core.signing.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                signing_private_key_hex="",
                debug=False,
            )
            # Module-level _signing_key is reset (leftover from previous tests)
            import app.core.signing as signing_mod
            original_key = signing_mod._signing_key
            signing_mod._signing_key = None

            try:
                with pytest.raises(RuntimeError) as exc_info:
                    _get_signing_key()
                assert "SIGNING_PRIVATE_KEY_HEX" in str(exc_info.value)
            finally:
                signing_mod._signing_key = original_key
