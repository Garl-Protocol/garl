"""Dalga 6 — Sigstore Rekor anchor bridge (opt-in)."""
from unittest.mock import patch

import pytest

from app.core import rekor


class TestRekorToggle:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_REKOR_ANCHOR", raising=False)
        assert rekor.is_enabled() is False

    @pytest.mark.parametrize("v", ["1", "true", "TRUE", "yes", "on"])
    def test_truthy_values_enable(self, monkeypatch, v):
        monkeypatch.setenv("ENABLE_REKOR_ANCHOR", v)
        assert rekor.is_enabled() is True

    @pytest.mark.parametrize("v", ["", "0", "false", "off", "no"])
    def test_falsy_values_disable(self, monkeypatch, v):
        monkeypatch.setenv("ENABLE_REKOR_ANCHOR", v)
        assert rekor.is_enabled() is False


class TestHashedrekordEntry:
    def test_builds_valid_spec(self):
        entry = rekor._build_hashedrekord_entry(
            content_hash_hex="ab" * 32,
            signature_hex="cd" * 32,
        )
        assert entry["kind"] == "hashedrekord"
        assert entry["apiVersion"] == "0.0.1"
        assert entry["spec"]["data"]["hash"]["algorithm"] == "sha256"
        assert entry["spec"]["data"]["hash"]["value"] == "ab" * 32
        # signature is base64 of the hex bytes
        import base64
        assert base64.b64decode(entry["spec"]["signature"]["content"]) == bytes.fromhex("cd" * 32)
        # publicKey.content is base64 of PEM
        pem_bytes = base64.b64decode(entry["spec"]["signature"]["publicKey"]["content"])
        assert pem_bytes.startswith(b"-----BEGIN PUBLIC KEY-----")


class TestAnchorSync:
    def test_success_returns_uuid_and_log_index(self):
        class FakeResp:
            status_code = 201
            text = ""
            def json(self):
                return {
                    "abc-uuid-123": {"logIndex": 42, "body": "..."}
                }

        with patch("app.core.rekor.httpx.post", return_value=FakeResp()):
            r = rekor.anchor_sync("ab" * 32, "cd" * 32, endpoint="https://rekor.example.com/api/v1/log/entries")
        assert r == {
            "uuid": "abc-uuid-123",
            "log_index": 42,
            "url": "https://rekor.example.com/?uuid=abc-uuid-123",
        }

    def test_non_2xx_returns_none(self):
        class FakeResp:
            status_code = 500
            text = "oops"
            def json(self):
                return {}

        with patch("app.core.rekor.httpx.post", return_value=FakeResp()):
            r = rekor.anchor_sync("ab" * 32, "cd" * 32, endpoint="https://rekor.example.com/api/v1/log/entries")
        assert r is None

    def test_network_failure_returns_none(self):
        import httpx
        with patch("app.core.rekor.httpx.post", side_effect=httpx.ConnectError("boom")):
            r = rekor.anchor_sync("ab" * 32, "cd" * 32)
        assert r is None

    def test_empty_response_returns_none(self):
        class FakeResp:
            status_code = 201
            text = ""
            def json(self):
                return {}
        with patch("app.core.rekor.httpx.post", return_value=FakeResp()):
            assert rekor.anchor_sync("ab" * 32, "cd" * 32) is None
