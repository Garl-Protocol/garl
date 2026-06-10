"""
Capability tokens — JWT-shaped + ECDSA-secp256k1 + Biscuit-style caveats.

Why JWT-shaped + ECDSA-secp256k1 instead of full Biscuit-python:
  - Same crypto stack as the rest of GARL receipt signing (ECDSA-secp256k1
    RFC 6979 deterministic). One key registry, one verifier path.
  - JWT envelope is what enterprise/OAuth ecosystems already verify
    (header.payload.signature, base64url). Easy interop with WorkOS,
    Stytch, MCP authorization spec (OAuth 2.1).
  - Biscuit's public-key attenuation semantics are reproduced by chaining
    via parent_token_hash + caveats array. Verifier walks the chain.

Format:
  - Header:    {"alg": "ES256K", "typ": "garl-cap-v0.1", "kid": "<key_id>"}
  - Payload:   {iss, sub, iat, exp, scope, side_effect_class,
                spend_limit_usd, merchant_allowlist, caveats[], parent}
  - Signature: ECDSA-secp256k1 over header.payload (RFC 6979)
  - Wire:      base64url(header) + "." + base64url(payload) + "." + base64url(sig)

Spec: protocol/spec/capability-token-v0.1.md (TODO).

Attenuation:
  - Each child carries parent_token_hash = sha256(parent jwt_form).
  - Child's caveats[] MUST be a strict superset of parent's caveats (i.e.
    child can only narrow, never broaden). The verify step walks the
    chain and intersects all constraints.

Revocation:
  - Single token: mark revoked_at + reason in capability_tokens row.
  - Cascade: revoking a parent revokes all descendants (in this session
    we mark them; an SQL trigger could enforce it transactionally).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from ecdsa import BadSignatureError, SECP256k1, VerifyingKey
from ecdsa.errors import MalformedPointError

from app.core.canonical import canonical_str

from app.core.signing import (
    _get_signing_key,
    derive_key_id,
    get_active_key_id,
    get_key_registry,
    get_public_key_hex,
)
from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

CAPABILITY_TOKEN_VERSION = "garl-cap-v0.1"
DEFAULT_TTL_SECONDS = 3600
MAX_TTL_SECONDS = 7 * 24 * 3600  # 7 days; longer needs explicit policy override
SIDE_EFFECT_CLASSES = ("none", "reversible", "irreversible")
SIDE_EFFECT_RANK = {"none": 0, "reversible": 1, "irreversible": 2}


# ──────────────────────────────────────────────────────────────────────
# Encoding helpers
# ──────────────────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    """RFC 7515 base64url, no padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """RFC 7515 base64url decode, padding-tolerant."""
    s = s + "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _canonical_json(obj: dict) -> str:
    """Canonical JSON for signing — the single GARL canonical form (see
    app.core.canonical). Verification reconstructs the signing input from the
    raw base64 segments, so this only governs issue-time bytes."""
    return canonical_str(obj)


def _hash_token(jwt_form: str) -> str:
    """Stable handle: SHA-256 of the entire wire form."""
    return hashlib.sha256(jwt_form.encode("ascii")).hexdigest()


# ──────────────────────────────────────────────────────────────────────
# Issue
# ──────────────────────────────────────────────────────────────────────

def issue_capability_token(
    *,
    agent_id: str,
    scope: str,
    side_effect_class: str,
    expires_in_seconds: int = DEFAULT_TTL_SECONDS,
    spend_limit_usd: float | None = None,
    merchant_allowlist: list[str] | None = None,
    caveats: list[dict] | None = None,
    parent_token_hash: str | None = None,
    human_delegate: str | None = None,
) -> dict:
    """Issue a fresh capability token.

    Returns:
        {
          "token": "<header.payload.signature>",
          "token_hash": "<sha256 hex>",
          "expires_at": "<RFC 3339>",
          "claims": {...payload...},
        }

    Raises:
        ValueError: invalid side_effect_class, ttl out of range, parent
            attenuation violation.
    """
    if side_effect_class not in SIDE_EFFECT_CLASSES:
        raise ValueError(
            f"side_effect_class must be one of {SIDE_EFFECT_CLASSES}, got {side_effect_class!r}"
        )
    if expires_in_seconds <= 0 or expires_in_seconds > MAX_TTL_SECONDS:
        raise ValueError(
            f"expires_in_seconds must be in (0, {MAX_TTL_SECONDS}]; got {expires_in_seconds}"
        )

    parent_claims: dict | None = None
    if parent_token_hash:
        parent_claims = _load_parent_claims(parent_token_hash)
        _enforce_attenuation(
            parent_claims=parent_claims,
            child_side_effect=side_effect_class,
            child_spend_limit=spend_limit_usd,
            child_merchant_allowlist=merchant_allowlist,
            child_expires_in=expires_in_seconds,
        )

    now = int(time.time())
    expires_at_ts = now + expires_in_seconds
    expires_at_iso = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).isoformat()

    header = {
        "alg": "ES256K",
        "typ": CAPABILITY_TOKEN_VERSION,
        "kid": get_active_key_id(),
    }
    payload: dict[str, Any] = {
        "iss": "https://api.garl.ai",
        "sub": f"did:garl:{agent_id}",
        "iat": now,
        "exp": expires_at_ts,
        "scope": scope,
        "side_effect_class": side_effect_class,
        "caveats": caveats or [],
    }
    if spend_limit_usd is not None:
        payload["spend_limit_usd"] = spend_limit_usd
    if merchant_allowlist:
        payload["merchant_allowlist"] = sorted(set(merchant_allowlist))
    if parent_token_hash:
        payload["parent"] = parent_token_hash
    if human_delegate:
        payload["delegate"] = human_delegate

    sk = _get_signing_key()
    header_b64 = _b64url_encode(_canonical_json(header).encode("utf-8"))
    payload_b64 = _b64url_encode(_canonical_json(payload).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    digest = hashlib.sha256(signing_input).digest()
    signature_bytes = sk.sign_digest_deterministic(digest, hashfunc=hashlib.sha256)
    signature_b64 = _b64url_encode(signature_bytes)
    jwt_form = f"{header_b64}.{payload_b64}.{signature_b64}"
    token_hash = _hash_token(jwt_form)

    _persist_token(
        token_hash=token_hash,
        agent_id=agent_id,
        human_delegate=human_delegate,
        jwt_form=jwt_form,
        caveats=payload["caveats"],
        scope=scope,
        spend_limit_usd=spend_limit_usd,
        side_effect_class=side_effect_class,
        merchant_allowlist=merchant_allowlist,
        parent_token_hash=parent_token_hash,
        expires_at_iso=expires_at_iso,
    )

    try:
        from app.core.analytics import capture as _ph
        _ph("capability_issued", agent_id, {"side_effect_class": side_effect_class})
    except Exception:
        pass
    return {
        "token": jwt_form,
        "token_hash": token_hash,
        "expires_at": expires_at_iso,
        "claims": payload,
    }


# ──────────────────────────────────────────────────────────────────────
# Verify
# ──────────────────────────────────────────────────────────────────────

class CapabilityTokenInvalid(ValueError):
    """Verification failure. Subclass of ValueError so callers can use
    standard exception handling but still distinguish from regular bad
    input."""


def verify_capability_token(jwt_form: str, *, check_revocation: bool = True) -> dict:
    """Verify a token end-to-end.

    Returns the payload claims if valid. Raises CapabilityTokenInvalid
    otherwise.
    """
    parts = jwt_form.split(".")
    if len(parts) != 3:
        raise CapabilityTokenInvalid("Token must have 3 dot-separated parts")

    header_b64, payload_b64, sig_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature_bytes = _b64url_decode(sig_b64)
    except (ValueError, json.JSONDecodeError) as e:
        raise CapabilityTokenInvalid(f"Token segments not parseable: {e}") from e

    if header.get("typ") != CAPABILITY_TOKEN_VERSION:
        raise CapabilityTokenInvalid(
            f"Unsupported token type: {header.get('typ')!r}"
        )
    if header.get("alg") != "ES256K":
        raise CapabilityTokenInvalid(
            f"Unsupported alg: {header.get('alg')!r}; expected ES256K"
        )

    kid = header.get("kid")
    if not kid:
        raise CapabilityTokenInvalid("Token header missing kid")

    public_key_hex = _resolve_key(kid)
    if not public_key_hex:
        raise CapabilityTokenInvalid(f"Unknown signing key kid={kid}")

    try:
        vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)
    except (MalformedPointError, ValueError) as e:
        raise CapabilityTokenInvalid(f"Bad signing key for kid={kid}: {e}") from e

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    digest = hashlib.sha256(signing_input).digest()
    try:
        vk.verify_digest(signature_bytes, digest)
    except (BadSignatureError, MalformedPointError, ValueError) as e:
        raise CapabilityTokenInvalid(f"Signature verification failed: {e}") from e

    now = int(time.time())
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise CapabilityTokenInvalid("Token missing or non-integer exp")
    if exp <= now:
        raise CapabilityTokenInvalid("Token expired")

    iat = payload.get("iat")
    if isinstance(iat, int) and iat > now + 60:
        # Allow 60s clock skew but reject blatant future-iat
        raise CapabilityTokenInvalid("Token iat is in the future")

    side_effect = payload.get("side_effect_class")
    if side_effect not in SIDE_EFFECT_CLASSES:
        raise CapabilityTokenInvalid(
            f"Token side_effect_class must be one of {SIDE_EFFECT_CLASSES}"
        )

    if check_revocation:
        token_hash = _hash_token(jwt_form)
        if _is_revoked(token_hash):
            raise CapabilityTokenInvalid("Token revoked")
        # Walk the parent chain — if any ancestor is revoked, this token
        # is dead too.
        parent = payload.get("parent")
        while parent:
            parent_row = _load_parent_row(parent)
            if not parent_row:
                # Parent missing from the registry — fail closed.
                raise CapabilityTokenInvalid("Parent token unknown")
            if parent_row.get("revoked_at"):
                raise CapabilityTokenInvalid("Ancestor token revoked")
            parent_payload = _decode_payload(parent_row["jwt_form"])
            parent = parent_payload.get("parent") if parent_payload else None

    return payload


# ──────────────────────────────────────────────────────────────────────
# Revoke
# ──────────────────────────────────────────────────────────────────────

def revoke_capability_token(
    token_hash: str, reason: str, *, cascade: bool = True
) -> dict:
    """Mark a token as revoked. By default cascades to all descendants.

    Returns: {"revoked": [token_hash, ...]}
    """
    sb = _get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()
    revoked: list[str] = []

    primary = (
        sb.table("capability_tokens")
        .update({"revoked_at": now_iso, "revocation_reason": reason})
        .eq("token_hash", token_hash)
        .is_("revoked_at", "null")
        .execute()
    )
    if primary.data:
        revoked.append(token_hash)

    if cascade:
        # BFS over descendants. Each level: select children by parent_token_hash.
        frontier = [token_hash]
        seen: set[str] = {token_hash}
        while frontier:
            children = (
                sb.table("capability_tokens")
                .select("token_hash")
                .in_("parent_token_hash", frontier)
                .execute()
                .data
                or []
            )
            new_hashes = [c["token_hash"] for c in children if c["token_hash"] not in seen]
            if not new_hashes:
                break
            seen.update(new_hashes)
            sb.table("capability_tokens").update(
                {
                    "revoked_at": now_iso,
                    "revocation_reason": f"cascade: {reason}",
                }
            ).in_("token_hash", new_hashes).is_("revoked_at", "null").execute()
            revoked.extend(new_hashes)
            frontier = new_hashes

    return {"revoked": revoked, "count": len(revoked)}


# ──────────────────────────────────────────────────────────────────────
# Internal: persistence + lookups
# ──────────────────────────────────────────────────────────────────────

def _persist_token(**fields) -> None:
    sb = _get_supabase()
    row = {
        "token_hash": fields["token_hash"],
        "agent_id": fields["agent_id"],
        "jwt_form": fields["jwt_form"],
        "caveats": fields["caveats"],
        "scope": fields["scope"],
        "side_effect_class": fields["side_effect_class"],
        "expires_at": fields["expires_at_iso"],
    }
    if fields.get("human_delegate"):
        row["human_delegate"] = fields["human_delegate"]
    if fields.get("spend_limit_usd") is not None:
        row["spend_limit_usd"] = fields["spend_limit_usd"]
    if fields.get("merchant_allowlist"):
        row["merchant_allowlist"] = fields["merchant_allowlist"]
    if fields.get("parent_token_hash"):
        row["parent_token_hash"] = fields["parent_token_hash"]
    sb.table("capability_tokens").insert(row).execute()


def _is_revoked(token_hash: str) -> bool:
    sb = _get_supabase()
    res = (
        sb.table("capability_tokens")
        .select("revoked_at")
        .eq("token_hash", token_hash)
        .limit(1)
        .execute()
    )
    if not res.data:
        # Token unknown to the registry → treat as revoked (fail CLOSED).
        # Issuance persists the row before the token is returned, so a
        # legitimate token is always present here; an unknown token_hash means
        # it was never issued (or was purged) and must not pass a revocation
        # check. Failing open here would let a never-persisted (e.g. forged or
        # offline-minted) token verify as not-revoked.
        return True
    return res.data[0].get("revoked_at") is not None


def _load_parent_row(parent_hash: str) -> dict | None:
    sb = _get_supabase()
    res = (
        sb.table("capability_tokens")
        .select("token_hash, jwt_form, revoked_at, expires_at, caveats, scope, side_effect_class, spend_limit_usd, merchant_allowlist")
        .eq("token_hash", parent_hash)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def _decode_payload(jwt_form: str) -> dict | None:
    parts = jwt_form.split(".")
    if len(parts) != 3:
        return None
    try:
        return json.loads(_b64url_decode(parts[1]))
    except (ValueError, json.JSONDecodeError):
        return None


def _load_parent_claims(parent_hash: str) -> dict:
    parent = _load_parent_row(parent_hash)
    if not parent:
        raise ValueError(f"Parent token not found: {parent_hash[:16]}…")
    if parent.get("revoked_at"):
        raise ValueError("Parent token is revoked")
    parent_payload = _decode_payload(parent["jwt_form"])
    if not parent_payload:
        raise ValueError("Parent token payload undecodable")
    return parent_payload


def _enforce_attenuation(
    *,
    parent_claims: dict,
    child_side_effect: str,
    child_spend_limit: float | None,
    child_merchant_allowlist: list[str] | None,
    child_expires_in: int,
) -> None:
    """Children can only narrow. If the parent says max-$50 then a child
    saying max-$100 is rejected. If the parent allows ['stripe.com'] then a
    child cannot allow ['stripe.com', 'paypal.com']."""
    parent_se = parent_claims.get("side_effect_class", "irreversible")
    if SIDE_EFFECT_RANK[child_side_effect] > SIDE_EFFECT_RANK[parent_se]:
        raise ValueError(
            f"Child side_effect_class={child_side_effect!r} is more dangerous "
            f"than parent's {parent_se!r}; attenuation must narrow"
        )

    parent_spend = parent_claims.get("spend_limit_usd")
    if parent_spend is not None:
        if child_spend_limit is None or child_spend_limit > parent_spend:
            raise ValueError(
                "Child spend_limit_usd must be set and ≤ parent's"
            )

    parent_allowlist = parent_claims.get("merchant_allowlist")
    if parent_allowlist:
        if not child_merchant_allowlist:
            raise ValueError(
                "Parent restricts merchant_allowlist; child must inherit or narrow"
            )
        parent_set = set(parent_allowlist)
        child_set = set(child_merchant_allowlist)
        if not child_set.issubset(parent_set):
            extra = child_set - parent_set
            raise ValueError(
                f"Child merchant_allowlist introduces unauthorized merchants: {sorted(extra)}"
            )

    parent_exp = parent_claims.get("exp", 0)
    child_exp = int(time.time()) + child_expires_in
    if child_exp > parent_exp:
        raise ValueError("Child token cannot outlive parent (exp)")


def _resolve_key(kid: str) -> str | None:
    """Resolve a kid via the live registry. Active key + retired keys both
    work — important for verifying tokens issued before a key rotation."""
    if kid == get_active_key_id():
        return get_public_key_hex()
    registry = get_key_registry()
    for entry in registry.get("keys", []):
        if entry.get("key_id") == kid:
            return entry.get("public_key_hex")
    return None
