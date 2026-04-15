"""Dalga 7 — garl-verify CLI.

The CLI module lives in sdks/python/garl_verify.py. These tests import
it by explicit file path so the unit suite stays in-tree without
installing the SDK.
"""
import importlib.util
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


CLI_PATH = Path(__file__).resolve().parent.parent.parent / "sdks" / "python" / "garl_verify.py"


@pytest.fixture(scope="module")
def cli():
    spec = importlib.util.spec_from_file_location("garl_verify", CLI_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_signed_cert(payload_extra=None):
    """Build a fresh signed cert using the backend signing module."""
    from app.core import signing
    signing._signing_key = None
    data = {"trace_id": "t-1", "agent_id": "a-1", "status": "success"}
    if payload_extra:
        data.update(payload_extra)
    return signing.sign_trace(data), signing.get_public_key_hex(), signing.get_active_key_id()


class TestArgParsing:
    def test_url_extraction(self, cli):
        assert cli._extract_hash_or_url("https://garl.ai/r/abc") == ("url", "https://garl.ai/r/abc")

    def test_hash_extraction(self, cli):
        assert cli._extract_hash_or_url("6ff83db8") == ("hash", "6ff83db8")

    def test_rejects_non_hex_short(self, cli):
        with pytest.raises(ValueError):
            cli._extract_hash_or_url("not-a-hash")


class TestVerifyRoundtrip:
    def test_signed_cert_verifies(self, cli):
        cert, pk, _kid = _make_signed_cert()
        assert cli._verify_cert(cert, pk) is True

    def test_tampered_payload_fails(self, cli):
        cert, pk, _ = _make_signed_cert()
        cert["payload"]["status"] = "failure"  # tamper
        assert cli._verify_cert(cert, pk) is False

    def test_wrong_key_fails(self, cli):
        from ecdsa import SigningKey, SECP256k1
        cert, _, _ = _make_signed_cert()
        other_pk = SigningKey.generate(curve=SECP256k1).get_verifying_key().to_string().hex()
        assert cli._verify_cert(cert, other_pk) is False


class TestMainCliStdin:
    def test_stdin_verify_happy_path(self, cli, monkeypatch, capsys):
        cert, pk, kid = _make_signed_cert()
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(cert)))

        class FakeResp:
            status_code = 200
            def raise_for_status(self): return None
            def json(self):
                return {"keys": [{"key_id": kid, "public_key_hex": pk, "status": "active"}]}

        with patch.object(cli.httpx, "get", return_value=FakeResp()):
            rc = cli.main(["--stdin"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "verified=True" in out
        assert kid in out

    def test_stdin_verify_rejects_tampered(self, cli, monkeypatch, capsys):
        cert, pk, kid = _make_signed_cert()
        cert["payload"]["status"] = "failure"
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(cert)))

        class FakeResp:
            status_code = 200
            def raise_for_status(self): return None
            def json(self):
                return {"keys": [{"key_id": kid, "public_key_hex": pk, "status": "active"}]}

        with patch.object(cli.httpx, "get", return_value=FakeResp()):
            rc = cli.main(["--stdin"])
        assert rc == 1
        assert "verified=False" in capsys.readouterr().out

    def test_self_vouched_key_refused(self, cli, monkeypatch, capsys):
        """If proof.publicKey isn't in the registry, we refuse."""
        from ecdsa import SigningKey, SECP256k1
        rogue_sk = SigningKey.generate(curve=SECP256k1)
        import hashlib as _h, json as _j
        payload = {"trace_id": "evil", "agent_id": "x"}
        digest = _h.sha256(_j.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).digest()
        sig = rogue_sk.sign_digest_deterministic(digest, hashfunc=_h.sha256).hex()
        rogue_pk = rogue_sk.get_verifying_key().to_string().hex()
        cert = {
            "proof": {
                "type": "ECDSA-secp256k1",
                "publicKey": rogue_pk,
                "signature": sig,
                "key_id": "rogue" + "0" * 11,
            },
            "payload": payload,
        }
        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(cert)))

        # Registry returns some OTHER key — not the rogue one
        class FakeResp:
            status_code = 200
            def raise_for_status(self): return None
            def json(self):
                return {"keys": [{"key_id": "aa" * 8, "public_key_hex": "bb" * 64, "status": "active"}]}

        with patch.object(cli.httpx, "get", return_value=FakeResp()):
            rc = cli.main(["--stdin"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "self-vouched" in err or "refusing" in err
