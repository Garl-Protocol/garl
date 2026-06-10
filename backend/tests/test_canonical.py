"""Freeze the GARL canonical JSON form (protocol/spec/canonical-json-v0.1.md).

The bytes produced here are what every historical receipt and trace was signed
over. If any of these change, historical signatures stop verifying — so these
tests are a tripwire, not just coverage.
"""
import json

import pytest

from app.core.canonical import canonical_str, canonical_bytes


def _historical_form(obj) -> str:
    # The exact json.dumps form used before canonical.py existed (ensure_ascii
    # defaults to True). Canonical output MUST stay byte-identical to this.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


class TestCanonicalFrozen:
    SAMPLES = [
        {"b": 2, "a": 1, "z": [3, 2, 1]},
        {"task": "café résumé 日本語", "n": 3.14, "nested": {"y": True, "x": None}},
        {"agent_identity": "did:garl:x", "cost": 0.025, "version": "garl/action-receipt/v0.1"},
        {},
        {"k": ""},
    ]

    def test_byte_identical_to_historical_form(self):
        for s in self.SAMPLES:
            assert canonical_str(s) == _historical_form(s)

    def test_keys_sorted_and_tight(self):
        assert canonical_str({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_non_ascii_is_escaped(self):
        # ensure_ascii=True → pure-ASCII output with \uXXXX escapes.
        out = canonical_str({"k": "é日"})
        assert out == '{"k":"\\u00e9\\u65e5"}'
        assert all(ord(c) < 128 for c in out)

    def test_bytes_are_utf8_of_str(self):
        for s in self.SAMPLES:
            assert canonical_bytes(s) == canonical_str(s).encode("utf-8")


class TestNanInfRejected:
    def test_nan_rejected(self):
        with pytest.raises(ValueError):
            canonical_str({"cost": float("nan")})

    def test_inf_rejected(self):
        with pytest.raises(ValueError):
            canonical_str({"cost": float("inf")})

    def test_neg_inf_rejected(self):
        with pytest.raises(ValueError):
            canonical_str({"cost": float("-inf")})
