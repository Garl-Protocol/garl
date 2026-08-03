"""Per-agent keyed content hashing (HMAC-SHA-256) — the EDPB ¶52 answer.

EDPB Guidelines 02/2025 ¶52 (adopted 7 July 2026): an UNSALTED hash of
personal data is itself personal data. GARL therefore hashes personal-data
payloads with a per-agent HMAC-SHA-256 key kept OFF-CHAIN in the
``agent_hash_keys`` table. ¶54 explicitly endorses "a hash generated from a
keyed hash function" on-chain with the verification data off-chain — exactly
this construction (only Merkle roots ever reach Base).

Erasure story: destroying the key (``destroy_keys``) irreversibly severs the
link between the published hash and the underlying personal data — the
¶52-sanctioned anonymisation mechanism. The hash stays in the immutable
ledger as an opaque commitment; without the key it can no longer be related
to a data subject, and preimage confirmation attacks are impossible.

Plain SHA-256 remains available ONLY for payloads the caller explicitly
declares non-personal (see submit_action_receipt's ``hash_scheme`` handling).

Full compliance mapping: docs/compliance/edpb.md.
"""
from __future__ import annotations

import hmac
import hashlib
import logging
import secrets
from typing import Any

from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

HASH_SCHEME_KEYED = "hmac-sha256"
HASH_SCHEME_PLAIN = "sha256"
VALID_HASH_SCHEMES = {HASH_SCHEME_KEYED, HASH_SCHEME_PLAIN}


class HashKeyDestroyed(RuntimeError):
    """The agent's hash key was destroyed (GDPR erasure) — keyed hashing is
    permanently unavailable for the destroyed key generation."""


def _new_key_id() -> str:
    return secrets.token_hex(8)  # 16 hex chars, matches signing key_id width


def get_active_hash_key(agent_id: str) -> dict[str, Any]:
    """Return the agent's active hash key row, creating one if none exists.

    A key is active when ``destroyed_at IS NULL`` and ``rotated_at IS NULL``.
    """
    sb = _get_supabase()
    rows = (
        sb.table("agent_hash_keys")
        .select("key_id, secret_hex, created_at")
        .eq("agent_id", agent_id)
        .is_("destroyed_at", "null")
        .is_("rotated_at", "null")
        .limit(1)
        .execute()
        .data
    )
    if rows:
        return rows[0]
    row = {
        "agent_id": agent_id,
        "key_id": _new_key_id(),
        "secret_hex": secrets.token_hex(32),  # 256-bit HMAC key
    }
    sb.table("agent_hash_keys").insert(row).execute()
    return row


def rotate_hash_key(agent_id: str) -> dict[str, Any]:
    """Retire the current key (kept for verifying old hashes) and mint a new
    one. Old hashes stay verifiable until the retired key is destroyed."""
    sb = _get_supabase()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    (
        sb.table("agent_hash_keys")
        .update({"rotated_at": now})
        .eq("agent_id", agent_id)
        .is_("destroyed_at", "null")
        .is_("rotated_at", "null")
        .execute()
    )
    row = {
        "agent_id": agent_id,
        "key_id": _new_key_id(),
        "secret_hex": secrets.token_hex(32),
    }
    sb.table("agent_hash_keys").insert(row).execute()
    return row


def destroy_hash_keys(agent_id: str) -> int:
    """GDPR erasure: null out every key secret for the agent and stamp
    ``destroyed_at``. Irreversible. Returns the number of keys destroyed.

    After destruction the agent's keyed hashes in the immutable ledger are
    unlinkable commitments (EDPB 02/2025 ¶52) — they can never again be
    related to the hashed content, even by GARL.
    """
    sb = _get_supabase()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    res = (
        sb.table("agent_hash_keys")
        .update({"secret_hex": None, "destroyed_at": now})
        .eq("agent_id", agent_id)
        .is_("destroyed_at", "null")
        .execute()
    )
    destroyed = len(res.data or [])
    logger.info("hash keys destroyed for agent %s: %d", agent_id, destroyed)
    return destroyed


def keyed_hash(agent_id: str, data: bytes | str) -> tuple[str, str]:
    """HMAC-SHA-256 of ``data`` under the agent's active hash key.

    Returns ``(hash_hex, key_id)``. The key never leaves the DB row; the
    resulting hash carries the same 64-lowercase-hex shape as plain SHA-256
    so every downstream surface (schema, Merkle leaves, proofs) is unchanged.
    """
    if isinstance(data, str):
        data = data.encode()
    key = get_active_hash_key(agent_id)
    if not key.get("secret_hex"):
        raise HashKeyDestroyed(f"hash key {key.get('key_id')} has no secret")
    digest = hmac.new(bytes.fromhex(key["secret_hex"]), data, hashlib.sha256).hexdigest()
    return digest, key["key_id"]
