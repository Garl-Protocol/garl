"""Phase 2 — public key registry + signing epoch disclosure."""
import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core import signing
from app.main import app


@pytest.fixture(autouse=True)
def _reset_signing_cache():
    # Force SigningKey re-load between tests so env var tweaks take effect.
    signing._signing_key = None
    yield
    signing._signing_key = None


class TestKeyId:
    def test_key_id_is_deterministic_16_hex(self):
        pk = signing.get_public_key_hex()
        kid = signing.derive_key_id(pk)
        assert len(kid) == 16
        assert all(c in "0123456789abcdef" for c in kid)
        assert signing.derive_key_id(pk) == kid

    def test_sign_trace_embeds_key_id(self):
        cert = signing.sign_trace({"hello": "world"})
        assert cert["proof"]["key_id"] == signing.get_active_key_id()
        assert len(cert["proof"]["key_id"]) == 16

    def test_verify_still_works_with_key_id_field(self):
        cert = signing.sign_trace({"hello": "world"})
        assert signing.verify_signature(cert) is True


class TestKeyRegistry:
    def test_well_known_registry_returns_active_key(self):
        c = TestClient(app)
        r = c.get("/.well-known/garl-keys.json")
        assert r.status_code == 200
        body = r.json()
        assert body["protocol"] == "garl"
        assert body["algorithm"] == "ECDSA-secp256k1"
        assert any(k["status"] == "active" for k in body["keys"])
        assert "public, max-age=300" in r.headers.get("Cache-Control", "")

    def test_api_v1_keys_mirrors_well_known(self):
        c = TestClient(app)
        wk = c.get("/.well-known/garl-keys.json").json()
        api = c.get("/api/v1/keys").json()
        assert wk["keys"][0]["key_id"] == api["keys"][0]["key_id"]
        assert wk["keys"][0]["public_key_hex"] == api["keys"][0]["public_key_hex"]

    def test_retired_keys_from_env_are_included(self, monkeypatch):
        retired = [
            {
                "public_key_hex": "aa" * 64,
                "retired_at": "2026-01-01T00:00:00Z",
                "note": "rotation test",
            }
        ]
        monkeypatch.setenv("GARL_RETIRED_KEYS_JSON", json.dumps(retired))
        reg = signing.get_key_registry()
        retired_keys = [k for k in reg["keys"] if k["status"] == "retired"]
        assert len(retired_keys) == 1
        assert retired_keys[0]["public_key_hex"] == "aa" * 64
        assert retired_keys[0]["key_id"] == signing.derive_key_id("aa" * 64)

    def test_malformed_retired_env_is_ignored(self, monkeypatch):
        monkeypatch.setenv("GARL_RETIRED_KEYS_JSON", "not json{")
        reg = signing.get_key_registry()
        # Only active key remains
        assert [k["status"] for k in reg["keys"]] == ["active"]
