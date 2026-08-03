"""Keyed content hashing (EDPB 02/2025 ¶52) — app/core/keyed_hash.py plus its
integration into receipts (hash_scheme) and PII masking."""
import hashlib
import hmac as hmac_mod
from unittest.mock import patch

import pytest

from app.core import keyed_hash as kh


AGENT = "780e900c-f429-41ee-8c9b-078f6bc5153b"


class FakeHashKeyStore:
    """Minimal stateful stand-in for the agent_hash_keys table."""

    def __init__(self):
        self.rows: list[dict] = []

    # -- chainable query facade -------------------------------------------
    def table(self, name):
        assert name == "agent_hash_keys"
        return _Query(self)


class _Query:
    def __init__(self, store):
        self.store = store
        self.filters = []
        self.op = "select"
        self.payload = None

    def select(self, *_a, **_k):
        self.op = "select"
        return self

    def insert(self, row):
        self.op = "insert"
        self.payload = row
        return self

    def update(self, patch_):
        self.op = "update"
        self.payload = patch_
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def is_(self, col, val):
        assert val == "null"
        self.filters.append((col, None))
        return self

    def limit(self, _n):
        return self

    def _match(self, row):
        return all(row.get(c) == v for c, v in self.filters)

    def execute(self):
        class R:
            pass

        r = R()
        if self.op == "select":
            r.data = [dict(row) for row in self.store.rows if self._match(row)]
        elif self.op == "insert":
            row = {"rotated_at": None, "destroyed_at": None, "created_at": "now", **self.payload}
            self.store.rows.append(row)
            r.data = [dict(row)]
        elif self.op == "update":
            r.data = []
            for row in self.store.rows:
                if self._match(row):
                    row.update(self.payload)
                    r.data.append(dict(row))
        return r


@pytest.fixture
def store():
    s = FakeHashKeyStore()
    with patch.object(kh, "_get_supabase", return_value=s):
        yield s


class TestKeyLifecycle:
    def test_first_call_creates_key(self, store):
        key = kh.get_active_hash_key(AGENT)
        assert len(key["key_id"]) == 16
        assert len(key["secret_hex"]) == 64
        assert len(store.rows) == 1

    def test_second_call_reuses_key(self, store):
        k1 = kh.get_active_hash_key(AGENT)
        k2 = kh.get_active_hash_key(AGENT)
        assert k1["key_id"] == k2["key_id"]
        assert len(store.rows) == 1

    def test_rotation_mints_new_generation(self, store):
        k1 = kh.get_active_hash_key(AGENT)
        k2 = kh.rotate_hash_key(AGENT)
        assert k2["key_id"] != k1["key_id"]
        old = next(r for r in store.rows if r["key_id"] == k1["key_id"])
        assert old["rotated_at"] is not None
        assert old["secret_hex"] is not None  # retired ≠ destroyed
        assert kh.get_active_hash_key(AGENT)["key_id"] == k2["key_id"]

    def test_destroy_nulls_all_secrets(self, store):
        kh.get_active_hash_key(AGENT)
        kh.rotate_hash_key(AGENT)
        destroyed = kh.destroy_hash_keys(AGENT)
        assert destroyed == 2
        assert all(r["secret_hex"] is None for r in store.rows)
        assert all(r["destroyed_at"] is not None for r in store.rows)

    def test_after_destruction_new_data_gets_fresh_key(self, store):
        old = kh.get_active_hash_key(AGENT)
        kh.destroy_hash_keys(AGENT)
        fresh = kh.get_active_hash_key(AGENT)
        assert fresh["key_id"] != old["key_id"]
        assert fresh["secret_hex"] is not None


class TestKeyedHash:
    def test_matches_reference_hmac(self, store):
        digest, key_id = kh.keyed_hash(AGENT, "hello")
        key = next(r for r in store.rows if r["key_id"] == key_id)
        expected = hmac_mod.new(
            bytes.fromhex(key["secret_hex"]), b"hello", hashlib.sha256
        ).hexdigest()
        assert digest == expected
        assert digest != hashlib.sha256(b"hello").hexdigest()

    def test_deterministic_under_same_key(self, store):
        d1, k1 = kh.keyed_hash(AGENT, "same input")
        d2, k2 = kh.keyed_hash(AGENT, "same input")
        assert (d1, k1) == (d2, k2)

    def test_differs_across_agents(self, store):
        d1, _ = kh.keyed_hash(AGENT, "payload")
        d2, _ = kh.keyed_hash("fac1597f-34d1-4ee3-ba8d-5805bc22b5ca", "payload")
        assert d1 != d2

    def test_shape_is_sha256_compatible(self, store):
        digest, _ = kh.keyed_hash(AGENT, b"bytes too")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


class TestHashSchemeValidation:
    """submit_action_receipt's hash_scheme contract (EDPB ¶52 gate)."""

    def _base_req(self, **over):
        req = {
            "agent_id": AGENT,
            "runtime": "custom",
            "protocol": "raw-http",
            "action_type": "tool_call",
            "input_hash": "a" * 64,
            "output_hash": "b" * 64,
            "side_effect": "none",
        }
        req.update(over)
        return req

    def _validate(self, req):
        from app.services.action_receipts import _validate_input
        _validate_input(req)

    def test_keyed_scheme_accepted(self):
        self._validate(self._base_req(hash_scheme={"input": "hmac-sha256", "output": "hmac-sha256"}))

    def test_plain_without_declaration_rejected(self):
        from app.services.action_receipts import ActionReceiptValidationError
        with pytest.raises(ActionReceiptValidationError, match="EDPB"):
            self._validate(self._base_req(hash_scheme={"input": "sha256"}))

    def test_plain_with_declaration_accepted(self):
        self._validate(
            self._base_req(hash_scheme={"input": "sha256"}, non_personal_payload=True)
        )

    def test_unknown_scheme_rejected(self):
        from app.services.action_receipts import ActionReceiptValidationError
        with pytest.raises(ActionReceiptValidationError, match="hash_scheme.input"):
            self._validate(self._base_req(hash_scheme={"input": "md5"}))

    def test_unknown_keys_rejected(self):
        from app.services.action_receipts import ActionReceiptValidationError
        with pytest.raises(ActionReceiptValidationError, match="Unknown hash_scheme keys"):
            self._validate(self._base_req(hash_scheme={"salt": "nope"}))

    def test_hash_scheme_lands_in_envelope(self):
        from app.services.action_receipts import build_envelope_for_signing
        env = build_envelope_for_signing(
            self._base_req(hash_scheme={"input": "hmac-sha256", "input_key_id": "ab" * 8})
        )
        assert env["hash_scheme"] == {"input": "hmac-sha256", "input_key_id": "ab" * 8}

    def test_no_hash_scheme_keeps_envelope_shape(self):
        from app.services.action_receipts import build_envelope_for_signing
        env = build_envelope_for_signing(self._base_req())
        assert "hash_scheme" not in env


class TestMintUsesKeyedInput:
    def test_mint_records_keyed_scheme(self):
        from app.services import action_receipts as ar

        captured = {}

        def fake_submit(req, enforce_cap=True):
            captured.update(req)
            return {"receipt_id": "x"}

        trace = {
            "agent_id": AGENT,
            "id": "trace-1",
            "trace_hash": "c" * 64,
            "category": "coding",
            "runtime_env": "claude-code",
        }
        sb = FakeHashKeyStore()

        class SBWrap:
            def table(self, name):
                if name == "agent_hash_keys":
                    return sb.table(name)

                class Q:
                    def select(self, *a, **k):
                        return self

                    def eq(self, *a):
                        return self

                    def limit(self, *a):
                        return self

                    def execute(self):
                        class R:
                            data = []
                        return R()

                return Q()

        with patch.object(kh, "_get_supabase", return_value=sb), \
             patch.object(ar, "_get_supabase", return_value=SBWrap()), \
             patch.object(ar, "submit_action_receipt", side_effect=fake_submit):
            ar.mint_receipt_for_trace(trace)

        assert captured["hash_scheme"]["input"] == "hmac-sha256"
        assert captured["hash_scheme"]["output"] == "sha256"
        assert captured["non_personal_payload"] is True
        assert captured["output_hash"] == "c" * 64
        # input hash is the HMAC, not the plain sha256, of the preimage
        plain = hashlib.sha256(f"garl-trace-input:{AGENT}:trace-1".encode()).hexdigest()
        assert captured["input_hash"] != plain

    def test_mint_falls_back_to_plain_when_keys_unavailable(self):
        from app.services import action_receipts as ar

        captured = {}

        def fake_submit(req, enforce_cap=True):
            captured.update(req)
            return {"receipt_id": "x"}

        trace = {"agent_id": AGENT, "id": "trace-2", "trace_hash": "d" * 64, "category": "coding"}

        class SBWrap:
            def table(self, name):
                class Q:
                    def select(self, *a, **k):
                        return self

                    def eq(self, *a):
                        return self

                    def limit(self, *a):
                        return self

                    def execute(self):
                        class R:
                            data = []
                        return R()

                return Q()

        with patch.object(kh, "_get_supabase", side_effect=RuntimeError("db down")), \
             patch.object(ar, "_get_supabase", return_value=SBWrap()), \
             patch.object(ar, "submit_action_receipt", side_effect=fake_submit):
            ar.mint_receipt_for_trace(trace)

        plain = hashlib.sha256(f"garl-trace-input:{AGENT}:trace-2".encode()).hexdigest()
        assert captured["input_hash"] == plain
        assert "hash_scheme" not in captured


class TestMaskSummary:
    def test_keyed_mask_format(self):
        from app.services.traces import mask_summary
        sb = FakeHashKeyStore()
        with patch.object(kh, "_get_supabase", return_value=sb):
            masked = mask_summary(AGENT, "john.doe@example.com placed an order")
        scheme, key_id, digest = masked.split(":")
        assert scheme == "hmac-sha256"
        assert len(key_id) == 16 and len(digest) == 64

    def test_falls_back_to_plain_on_key_failure(self):
        from app.services.traces import mask_summary
        with patch.object(kh, "_get_supabase", side_effect=RuntimeError("down")):
            masked = mask_summary(AGENT, "sensitive")
        assert masked == f"sha256:{hashlib.sha256(b'sensitive').hexdigest()}"
