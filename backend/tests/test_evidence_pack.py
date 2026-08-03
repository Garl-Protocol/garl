"""Unit tests for the Evidence Pack service (app/services/evidence_pack.py).

Supabase is faked with per-table resolvers; the Merkle proof builder is
patched so anchored / unanchored packs can be exercised deterministically.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from app.core.signing import get_public_key_hex, verify_signature
from app.services.evidence_pack import (
    EVIDENCE_PACK_VERSION,
    build_evidence_pack,
    render_evidence_pack_pdf,
)

AGENT = "11111111-1111-1111-1111-111111111111"
RECEIPT_ID = "22222222-2222-2222-2222-222222222222"
OUTPUT_HASH = "c" * 64
LEAF_TOKEN = "a" * 64
PARENT_TOKEN = "b" * 64


def _jwt(payload: dict) -> str:
    def b64(o):
        return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=").decode()
    return f"{b64({'alg': 'ES256K', 'typ': 'garl-cap-v0.1'})}.{b64(payload)}.c2ln"


ENVELOPE = {
    "receipt_id": RECEIPT_ID,
    "version": "garl/action-receipt/v0.1",
    "issuer": "https://api.garl.ai",
    "agent_identity": f"did:garl:{AGENT}",
    "human_delegate": "ops@example.com",
    "runtime": "claude-code",
    "protocol": "mcp",
    "action_type": "payment",
    "input_hash": "1" * 64,
    "output_hash": OUTPUT_HASH,
    "side_effect": "irreversible",
    "timestamp": "2026-08-03T12:00:00Z",
    "capability_request": {"token_hash": LEAF_TOKEN, "side_effect_class": "irreversible"},
    "signature": "f0" * 32,
    "verification_key_id": "deadbeefdeadbeef",
}

RECEIPT_ROW = {
    "receipt_id": RECEIPT_ID,
    "agent_id": AGENT,
    "envelope_json": ENVELOPE,
    "capability_token_hash": LEAF_TOKEN,
    "merkle_batch_id": 7,
    "anchored_at": "2026-08-03T18:00:00+00:00",
    "created_at": "2026-08-03T12:00:01+00:00",
    "output_hash": OUTPUT_HASH,
}

LEAF_TOKEN_ROW = {
    "token_hash": LEAF_TOKEN,
    "jwt_form": _jwt({"sub": f"did:garl:{AGENT}", "scope": "payments:send",
                      "side_effect_class": "irreversible", "parent": PARENT_TOKEN}),
    "parent_token_hash": PARENT_TOKEN,
    "revoked_at": None,
    "scope": "payments:send",
    "spend_limit_usd": 50.0,
    "merchant_allowlist": ["acme.example"],
    "side_effect_class": "irreversible",
    "issued_at": "2026-08-03T11:00:00+00:00",
    "expires_at": "2026-08-03T13:00:00+00:00",
}

PARENT_TOKEN_ROW = {
    "token_hash": PARENT_TOKEN,
    "jwt_form": _jwt({"sub": f"did:garl:{AGENT}", "scope": "payments:*",
                      "side_effect_class": "irreversible"}),
    "parent_token_hash": None,
    "revoked_at": "2026-08-04T00:00:00+00:00",  # revoked ancestor
    "scope": "payments:*",
    "spend_limit_usd": 500.0,
    "merchant_allowlist": None,
    "side_effect_class": "irreversible",
    "issued_at": "2026-08-01T00:00:00+00:00",
    "expires_at": "2026-08-08T00:00:00+00:00",
}

ALERT_ROW = {
    "envelope_json": {
        "alert_id": "aaaaaaaa-0000-0000-0000-000000000001",
        "version": "garl/session-alert/v0.1",
        "rule": "spend_velocity",
        "severity": "warning",
    },
    "created_at": "2026-08-03T13:00:00+00:00",
}

PROOF = {
    "anchored": True,
    "chain": "base-mainnet",
    "chain_id": 8453,
    "contract_address": "0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2",
    "tx_hash": "0x" + "d" * 64,
    "anchored_at": "2026-08-03T18:00:00+00:00",
    "merkle_root": "e" * 64,
    "receipt_count": 2,
    "leaf": "f" * 64,
    "leaf_index": 0,
    "proof": [{"sibling": "9" * 64, "position": "right"}],
    "verify_proof_args": {
        "batchId": 7,
        "leaf": "0x" + "f" * 64,
        "proofSiblings": ["0x" + "9" * 64],
        "proofPositions": [True],
    },
}


class _Chain:
    def __init__(self, resolver):
        self._resolver = resolver
        self.filters: dict = {}

    def select(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, *a, **k):
        return self

    def eq(self, col, val):
        self.filters[col] = val
        return self

    def gte(self, col, val):
        self.filters["gte:" + col] = val
        return self

    def lte(self, col, val):
        self.filters["lte:" + col] = val
        return self

    def execute(self):
        res = MagicMock()
        res.data = self._resolver(self.filters)
        res.count = len(res.data)
        return res


class _FakeSB:
    def __init__(self, receipts=None, tokens=None, alerts=None):
        self.receipts = receipts if receipts is not None else [RECEIPT_ROW]
        self.tokens = tokens if tokens is not None else {
            LEAF_TOKEN: LEAF_TOKEN_ROW,
            PARENT_TOKEN: PARENT_TOKEN_ROW,
        }
        self.alerts = alerts if alerts is not None else [ALERT_ROW]

    def table(self, name):
        if name == "receipts":
            def resolve(f):
                return [
                    r for r in self.receipts
                    if f.get("receipt_id") == r["receipt_id"]
                    or f.get("output_hash") == r.get("output_hash")
                ]
            return _Chain(resolve)
        if name == "capability_tokens":
            return _Chain(
                lambda f: [self.tokens[f["token_hash"]]]
                if f.get("token_hash") in self.tokens else []
            )
        if name == "session_alerts":
            return _Chain(lambda f: self.alerts)
        return _Chain(lambda f: [])


def _build(sb=None, proof=PROOF, rid=RECEIPT_ID):
    with patch("app.services.evidence_pack._get_supabase", return_value=sb or _FakeSB()), \
         patch("app.services.evidence_pack.build_inclusion_proof", return_value=proof):
        return build_evidence_pack(rid)


class TestPackStructure:
    def test_anchored_pack_shape(self):
        pack = _build()
        assert pack["version"] == EVIDENCE_PACK_VERSION
        assert pack["issuer"] == "https://api.garl.ai"
        assert pack["generated_at"].endswith("Z")
        assert pack["receipt"] == ENVELOPE
        assert pack["merkle_proof"] == PROOF
        # anchor is the convenience subset of the proof
        assert pack["anchor"] == {
            "chain_id": 8453,
            "contract_address": PROOF["contract_address"],
            "tx_hash": PROOF["tx_hash"],
            "merkle_root": PROOF["merkle_root"],
            "anchored_at": PROOF["anchored_at"],
            "explorer_url": f"https://basescan.org/tx/{PROOF['tx_hash']}",
        }
        assert pack["session_alerts"] == [ALERT_ROW["envelope_json"]]
        assert any(k.get("status") == "active" for k in pack["key_registry"]["keys"])
        assert len(pack["verification"]["offline_steps"]) >= 4
        assert "6 months" in pack["retention"]["policy"]
        assert pack["retention"]["exported_by"] is None
        assert pack["signature"]
        assert pack["verification_key_id"]

    def test_capability_chain_leaf_to_root(self):
        pack = _build()
        chain = pack["capability_chain"]
        assert [l["token_hash"] for l in chain] == [LEAF_TOKEN, PARENT_TOKEN]
        leaf, parent = chain
        assert leaf["found"] and parent["found"]
        assert leaf["revoked"] is False
        assert parent["revoked"] is True
        assert parent["revoked_at"] == PARENT_TOKEN_ROW["revoked_at"]
        # decoded (unverified) claims + wire form both present
        assert leaf["claims"]["scope"] == "payments:send"
        assert leaf["jwt_form"] == LEAF_TOKEN_ROW["jwt_form"]
        assert leaf["spend_limit_usd"] == 50.0
        assert leaf["merchant_allowlist"] == ["acme.example"]

    def test_unanchored_receipt_null_proof_and_anchor(self):
        pack = _build(proof=None)
        assert pack["merkle_proof"] is None
        assert pack["anchor"] is None
        # the rest of the pack is still complete and signed
        assert pack["receipt"] == ENVELOPE
        assert pack["signature"]

    def test_unknown_receipt_returns_none(self):
        assert _build(sb=_FakeSB(receipts=[]), rid="unknown-id") is None

    def test_lookup_by_output_hash(self):
        pack = _build(rid=OUTPUT_HASH.upper())  # case-insensitive 64-hex
        assert pack is not None
        assert pack["receipt"]["receipt_id"] == RECEIPT_ID

    def test_no_capability_token_empty_chain(self):
        row = dict(RECEIPT_ROW, capability_token_hash=None)
        pack = _build(sb=_FakeSB(receipts=[row]))
        assert pack["capability_chain"] == []

    def test_unknown_token_marked_not_found(self):
        pack = _build(sb=_FakeSB(tokens={}))
        assert pack["capability_chain"] == [{"token_hash": LEAF_TOKEN, "found": False}]


class TestChainCycleSafety:
    def test_parent_cycle_terminates(self):
        a = dict(LEAF_TOKEN_ROW, parent_token_hash=PARENT_TOKEN)
        b = dict(PARENT_TOKEN_ROW, parent_token_hash=LEAF_TOKEN)  # cycle back
        pack = _build(sb=_FakeSB(tokens={LEAF_TOKEN: a, PARENT_TOKEN: b}))
        chain = pack["capability_chain"]
        assert [l["token_hash"] for l in chain] == [LEAF_TOKEN, PARENT_TOKEN]
        assert len(chain) == 2  # revisit of LEAF_TOKEN did not loop

    def test_self_parent_terminates(self):
        a = dict(LEAF_TOKEN_ROW, parent_token_hash=LEAF_TOKEN)
        pack = _build(sb=_FakeSB(tokens={LEAF_TOKEN: a}))
        assert len(pack["capability_chain"]) == 1


class TestPackSignature:
    @staticmethod
    def _as_certificate(pack: dict) -> dict:
        payload = {k: v for k, v in pack.items()
                   if k not in ("signature", "verification_key_id")}
        return {
            "payload": payload,
            "proof": {"publicKey": get_public_key_hex(),
                      "signature": pack["signature"]},
        }

    def test_signature_verifies(self):
        pack = _build()
        assert verify_signature(self._as_certificate(pack)) is True

    def test_signature_breaks_on_tamper(self):
        pack = _build()
        tampered = json.loads(json.dumps(pack))
        tampered["retention"]["policy"] = "retain for 5 minutes"
        assert verify_signature(self._as_certificate(tampered)) is False

    def test_signature_breaks_on_receipt_swap(self):
        pack = _build()
        tampered = json.loads(json.dumps(pack))
        tampered["receipt"]["output_hash"] = "0" * 64
        assert verify_signature(self._as_certificate(tampered)) is False


class TestPdfRendering:
    def test_anchored_pack_renders_pdf(self):
        pack = _build()
        pdf = render_evidence_pack_pdf(pack)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000

    def test_unanchored_pack_renders_pdf(self):
        pack = _build(proof=None)
        pdf = render_evidence_pack_pdf(pack)
        assert pdf.startswith(b"%PDF")

    def test_minimal_pack_renders_pdf(self):
        # Defensive rendering: missing optional sections must not crash.
        pack = {
            "version": EVIDENCE_PACK_VERSION,
            "generated_at": "2026-08-04T00:00:00Z",
            "issuer": "https://api.garl.ai",
            "receipt": {"receipt_id": RECEIPT_ID},
            "capability_chain": [],
            "merkle_proof": None,
            "anchor": None,
            "session_alerts": [],
            "key_registry": {"keys": []},
            "verification": {"offline_steps": ["1. verify"]},
            "retention": {"policy": "keep it", "exported_by": None},
            "signature": "ab" * 32,
            "verification_key_id": "deadbeefdeadbeef",
        }
        pdf = render_evidence_pack_pdf(pack)
        assert pdf.startswith(b"%PDF")
