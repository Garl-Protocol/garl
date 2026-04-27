"""Tests for the capability token service.

These tests cover the pure crypto path (issue → verify → tamper → expire)
without touching Supabase. The DB-backed paths (revocation, parent chain
walk, persistence) are exercised separately and tolerate a missing DB by
asserting the right error class — production has the DB; CI does not need
it for the core verifier to be correct.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from unittest.mock import patch

import pytest

from app.services.capability_tokens import (
    CAPABILITY_TOKEN_VERSION,
    CapabilityTokenInvalid,
    MAX_TTL_SECONDS,
    SIDE_EFFECT_CLASSES,
    SIDE_EFFECT_RANK,
    _b64url_decode,
    _b64url_encode,
    _canonical_json,
    _enforce_attenuation,
    _hash_token,
    issue_capability_token,
    verify_capability_token,
)


# ──────────────────────────────────────────────────────────────────────
# Helpers — patch out persistence for unit tests so we test the crypto
# path without needing Supabase.
# ──────────────────────────────────────────────────────────────────────

def _no_persist(*args, **kwargs):
    return None


def _no_revocation(*args, **kwargs):
    return False


def _issue_no_persist(**kwargs):
    with patch("app.services.capability_tokens._persist_token", _no_persist):
        return issue_capability_token(**kwargs)


def _verify_no_revocation(token: str):
    with patch("app.services.capability_tokens._is_revoked", _no_revocation):
        return verify_capability_token(token, check_revocation=True)


# ──────────────────────────────────────────────────────────────────────
# Issue + verify roundtrip
# ──────────────────────────────────────────────────────────────────────

def test_issue_returns_token_envelope():
    out = _issue_no_persist(
        agent_id="11111111-1111-1111-1111-111111111111",
        scope="github:issue:create",
        side_effect_class="reversible",
    )
    assert out["token"].count(".") == 2
    assert len(out["token_hash"]) == 64
    assert out["expires_at"].endswith("+00:00")
    assert out["claims"]["scope"] == "github:issue:create"
    assert out["claims"]["side_effect_class"] == "reversible"


def test_issue_then_verify_roundtrip():
    out = _issue_no_persist(
        agent_id="11111111-1111-1111-1111-111111111111",
        scope="payment:charge",
        side_effect_class="irreversible",
        spend_limit_usd=50.0,
        merchant_allowlist=["stripe.com"],
    )
    claims = verify_capability_token(out["token"], check_revocation=False)
    assert claims["scope"] == "payment:charge"
    assert claims["side_effect_class"] == "irreversible"
    assert claims["spend_limit_usd"] == 50.0
    assert claims["merchant_allowlist"] == ["stripe.com"]


def test_token_is_deterministic_for_identical_input():
    """ECDSA-secp256k1 with RFC 6979 — same payload → same signature.
    Important so issuers can de-dupe."""
    fixed_iat = 1714000000
    with patch("app.services.capability_tokens.time.time", return_value=fixed_iat):
        a = _issue_no_persist(
            agent_id="11111111-1111-1111-1111-111111111111",
            scope="x:y",
            side_effect_class="none",
            expires_in_seconds=3600,
        )
        b = _issue_no_persist(
            agent_id="11111111-1111-1111-1111-111111111111",
            scope="x:y",
            side_effect_class="none",
            expires_in_seconds=3600,
        )
    assert a["token"] == b["token"]


# ──────────────────────────────────────────────────────────────────────
# Tampering detection
# ──────────────────────────────────────────────────────────────────────

def test_tampered_payload_rejected():
    out = _issue_no_persist(
        agent_id="22222222-2222-2222-2222-222222222222",
        scope="x:y",
        side_effect_class="none",
    )
    header_b64, payload_b64, sig_b64 = out["token"].split(".")
    payload = json.loads(_b64url_decode(payload_b64))
    payload["spend_limit_usd"] = 999999.0  # forge a higher limit
    bad_payload_b64 = _b64url_encode(_canonical_json(payload).encode("utf-8"))
    bad_token = f"{header_b64}.{bad_payload_b64}.{sig_b64}"
    with pytest.raises(CapabilityTokenInvalid, match="Signature"):
        verify_capability_token(bad_token, check_revocation=False)


def test_tampered_header_rejected():
    out = _issue_no_persist(
        agent_id="22222222-2222-2222-2222-222222222222",
        scope="x:y",
        side_effect_class="none",
    )
    header_b64, payload_b64, sig_b64 = out["token"].split(".")
    header = json.loads(_b64url_decode(header_b64))
    header["alg"] = "HS256"  # downgrade attempt
    bad_header_b64 = _b64url_encode(_canonical_json(header).encode("utf-8"))
    bad_token = f"{bad_header_b64}.{payload_b64}.{sig_b64}"
    # Either alg-mismatch OR signature-mismatch is acceptable; both fail closed.
    with pytest.raises(CapabilityTokenInvalid):
        verify_capability_token(bad_token, check_revocation=False)


def test_swapped_signature_rejected():
    a = _issue_no_persist(agent_id="33333333-3333-3333-3333-333333333333",
                          scope="a", side_effect_class="none")
    b = _issue_no_persist(agent_id="33333333-3333-3333-3333-333333333333",
                          scope="b", side_effect_class="none")
    a_h, a_p, _ = a["token"].split(".")
    _, _, b_sig = b["token"].split(".")
    forged = f"{a_h}.{a_p}.{b_sig}"
    with pytest.raises(CapabilityTokenInvalid, match="Signature"):
        verify_capability_token(forged, check_revocation=False)


def test_random_signature_rejected():
    out = _issue_no_persist(
        agent_id="44444444-4444-4444-4444-444444444444",
        scope="x", side_effect_class="none",
    )
    h, p, _ = out["token"].split(".")
    fake_sig = _b64url_encode(b"\x00" * 64)
    forged = f"{h}.{p}.{fake_sig}"
    with pytest.raises(CapabilityTokenInvalid):
        verify_capability_token(forged, check_revocation=False)


def test_empty_signature_rejected():
    out = _issue_no_persist(
        agent_id="44444444-4444-4444-4444-444444444444",
        scope="x", side_effect_class="none",
    )
    h, p, _ = out["token"].split(".")
    forged = f"{h}.{p}."
    with pytest.raises(CapabilityTokenInvalid):
        verify_capability_token(forged, check_revocation=False)


def test_malformed_token_rejected():
    with pytest.raises(CapabilityTokenInvalid, match="3 dot-separated parts"):
        verify_capability_token("not.a.valid.jwt.shape", check_revocation=False)
    with pytest.raises(CapabilityTokenInvalid, match="3 dot-separated parts"):
        verify_capability_token("only-one-segment", check_revocation=False)


# ──────────────────────────────────────────────────────────────────────
# Expiration
# ──────────────────────────────────────────────────────────────────────

def test_expired_token_rejected():
    """Issue a token with a 1-second TTL, sleep past it, verify fails."""
    out = _issue_no_persist(
        agent_id="55555555-5555-5555-5555-555555555555",
        scope="x", side_effect_class="none",
        expires_in_seconds=1,
    )
    # Don't actually sleep — patch the clock forward.
    future = int(time.time()) + 5
    with patch("app.services.capability_tokens.time.time", return_value=future):
        with pytest.raises(CapabilityTokenInvalid, match="expired"):
            verify_capability_token(out["token"], check_revocation=False)


def test_future_iat_rejected():
    out = _issue_no_persist(
        agent_id="66666666-6666-6666-6666-666666666666",
        scope="x", side_effect_class="none",
    )
    past = int(time.time()) - 3600  # pretend it's 1h ago
    with patch("app.services.capability_tokens.time.time", return_value=past):
        # Now iat (which was real-time) is in the future relative to the
        # patched clock; verifier should reject.
        with pytest.raises(CapabilityTokenInvalid, match="future"):
            verify_capability_token(out["token"], check_revocation=False)


# ──────────────────────────────────────────────────────────────────────
# TTL bounds
# ──────────────────────────────────────────────────────────────────────

def test_zero_ttl_rejected():
    with pytest.raises(ValueError, match="expires_in_seconds"):
        _issue_no_persist(
            agent_id="77777777-7777-7777-7777-777777777777",
            scope="x", side_effect_class="none", expires_in_seconds=0,
        )


def test_huge_ttl_rejected():
    with pytest.raises(ValueError, match="expires_in_seconds"):
        _issue_no_persist(
            agent_id="77777777-7777-7777-7777-777777777777",
            scope="x", side_effect_class="none",
            expires_in_seconds=MAX_TTL_SECONDS + 1,
        )


# ──────────────────────────────────────────────────────────────────────
# side_effect_class enforcement
# ──────────────────────────────────────────────────────────────────────

def test_invalid_side_effect_rejected_at_issue():
    with pytest.raises(ValueError, match="side_effect_class"):
        _issue_no_persist(
            agent_id="88888888-8888-8888-8888-888888888888",
            scope="x", side_effect_class="catastrophic",
        )


def test_side_effect_rank_strictly_orders_the_three_classes():
    assert SIDE_EFFECT_RANK["none"] < SIDE_EFFECT_RANK["reversible"] < SIDE_EFFECT_RANK["irreversible"]
    # Defensive — protects against accidental rank-shuffle in future edits
    assert set(SIDE_EFFECT_CLASSES) == set(SIDE_EFFECT_RANK.keys())


# ──────────────────────────────────────────────────────────────────────
# Attenuation policy
# ──────────────────────────────────────────────────────────────────────

def _parent_claims(**overrides):
    base = {
        "exp": int(time.time()) + 3600,
        "side_effect_class": "reversible",
        "spend_limit_usd": 100.0,
        "merchant_allowlist": ["stripe.com", "calendly.com"],
    }
    base.update(overrides)
    return base


def test_child_cannot_broaden_side_effect():
    parent = _parent_claims(side_effect_class="reversible")
    with pytest.raises(ValueError, match="more dangerous"):
        _enforce_attenuation(
            parent_claims=parent,
            child_side_effect="irreversible",
            child_spend_limit=10.0,
            child_merchant_allowlist=["stripe.com"],
            child_expires_in=600,
        )


def test_child_must_set_spend_limit_if_parent_did():
    parent = _parent_claims(spend_limit_usd=100.0)
    with pytest.raises(ValueError, match="spend_limit_usd"):
        _enforce_attenuation(
            parent_claims=parent,
            child_side_effect="reversible",
            child_spend_limit=None,
            child_merchant_allowlist=["stripe.com"],
            child_expires_in=600,
        )


def test_child_spend_limit_must_be_at_or_below_parent():
    parent = _parent_claims(spend_limit_usd=100.0)
    with pytest.raises(ValueError, match="spend_limit_usd"):
        _enforce_attenuation(
            parent_claims=parent,
            child_side_effect="reversible",
            child_spend_limit=200.0,
            child_merchant_allowlist=["stripe.com"],
            child_expires_in=600,
        )
    # Equal is OK
    _enforce_attenuation(
        parent_claims=parent,
        child_side_effect="reversible",
        child_spend_limit=100.0,
        child_merchant_allowlist=["stripe.com"],
        child_expires_in=600,
    )
    # Strictly less is OK
    _enforce_attenuation(
        parent_claims=parent,
        child_side_effect="reversible",
        child_spend_limit=10.0,
        child_merchant_allowlist=["stripe.com"],
        child_expires_in=600,
    )


def test_child_merchant_allowlist_must_be_subset():
    parent = _parent_claims(merchant_allowlist=["stripe.com"])
    with pytest.raises(ValueError, match="unauthorized merchants"):
        _enforce_attenuation(
            parent_claims=parent,
            child_side_effect="reversible",
            child_spend_limit=10.0,
            child_merchant_allowlist=["stripe.com", "evil.com"],
            child_expires_in=600,
        )


def test_child_cannot_outlive_parent():
    parent = _parent_claims(exp=int(time.time()) + 600)  # parent dies in 10m
    with pytest.raises(ValueError, match="outlive parent"):
        _enforce_attenuation(
            parent_claims=parent,
            child_side_effect="reversible",
            child_spend_limit=10.0,
            child_merchant_allowlist=["stripe.com"],
            child_expires_in=3600,  # child wants 1h
        )


# ──────────────────────────────────────────────────────────────────────
# Hash + b64 helpers
# ──────────────────────────────────────────────────────────────────────

def test_token_hash_is_sha256_of_jwt_form():
    token = "aaa.bbb.ccc"
    expected = hashlib.sha256(token.encode("ascii")).hexdigest()
    assert _hash_token(token) == expected
    assert len(_hash_token(token)) == 64


def test_b64url_roundtrip():
    for raw in [b"", b"a", b"ab", b"abc", b"\x00\xff" * 32]:
        encoded = _b64url_encode(raw)
        # No padding in our encoding
        assert "=" not in encoded
        # Decoded byte-for-byte
        assert _b64url_decode(encoded) == raw


def test_canonical_json_is_sorted_and_compact():
    """Same payload → same bytes → same signature. This is the load-bearing
    canonicalization that makes RFC 6979 deterministic ECDSA work."""
    a = _canonical_json({"b": 2, "a": 1, "c": [3, 2, 1]})
    b = _canonical_json({"a": 1, "c": [3, 2, 1], "b": 2})
    assert a == b
    assert a == '{"a":1,"b":2,"c":[3,2,1]}'  # exact bytes


# ──────────────────────────────────────────────────────────────────────
# Header / version constraints
# ──────────────────────────────────────────────────────────────────────

def test_unknown_alg_rejected():
    out = _issue_no_persist(
        agent_id="99999999-9999-9999-9999-999999999999",
        scope="x", side_effect_class="none",
    )
    h_b64, p_b64, sig = out["token"].split(".")
    h = json.loads(_b64url_decode(h_b64))
    h["alg"] = "RS256"  # wrong family
    bad_h_b64 = _b64url_encode(_canonical_json(h).encode("utf-8"))
    bad = f"{bad_h_b64}.{p_b64}.{sig}"
    with pytest.raises(CapabilityTokenInvalid, match="alg"):
        verify_capability_token(bad, check_revocation=False)


def test_missing_kid_rejected():
    out = _issue_no_persist(
        agent_id="99999999-9999-9999-9999-999999999999",
        scope="x", side_effect_class="none",
    )
    h_b64, p_b64, sig = out["token"].split(".")
    h = json.loads(_b64url_decode(h_b64))
    h.pop("kid", None)
    bad_h_b64 = _b64url_encode(_canonical_json(h).encode("utf-8"))
    bad = f"{bad_h_b64}.{p_b64}.{sig}"
    with pytest.raises(CapabilityTokenInvalid, match="kid"):
        verify_capability_token(bad, check_revocation=False)


def test_unknown_kid_rejected():
    out = _issue_no_persist(
        agent_id="99999999-9999-9999-9999-999999999999",
        scope="x", side_effect_class="none",
    )
    h_b64, p_b64, sig = out["token"].split(".")
    h = json.loads(_b64url_decode(h_b64))
    h["kid"] = "0123456789abcdef"  # made up
    bad_h_b64 = _b64url_encode(_canonical_json(h).encode("utf-8"))
    bad = f"{bad_h_b64}.{p_b64}.{sig}"
    with pytest.raises(CapabilityTokenInvalid, match="Unknown signing key"):
        verify_capability_token(bad, check_revocation=False)


def test_version_constant_matches_header_typ():
    assert CAPABILITY_TOKEN_VERSION == "garl-cap-v0.1"
    out = _issue_no_persist(
        agent_id="99999999-9999-9999-9999-999999999999",
        scope="x", side_effect_class="none",
    )
    header = json.loads(_b64url_decode(out["token"].split(".")[0]))
    assert header["typ"] == CAPABILITY_TOKEN_VERSION
