"""Optional Sigstore Rekor transparency-log bridge.

Every signed GARL receipt can be *additionally* anchored to the
Sigstore Rekor public transparency log. This gives verifiers a second
independent witness of the signature — without Rekor, a verifier has
to trust our key registry; with Rekor they get a tamper-evident
Merkle log that multiple independent parties replicate.

Feature-flagged. When ``ENABLE_REKOR_ANCHOR`` env var is truthy, a
fire-and-forget daemon thread posts a ``hashedrekord`` entry to the
configured Rekor endpoint (default
``https://rekor.sigstore.dev/api/v1/log/entries``) after each trace
is signed. The returned UUID + log index + URL are stashed into
``trace.metadata.rekor`` so ``/verify`` can surface them to clients.
Any failure is logged and swallowed — Rekor is never on the critical
path.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading

import httpx
from ecdsa import VerifyingKey, SECP256k1

from app.core.signing import get_public_key_hex

logger = logging.getLogger("garl.rekor")

_REKOR_URL_ENV = "REKOR_ENDPOINT"
_REKOR_ENABLE_ENV = "ENABLE_REKOR_ANCHOR"
_REKOR_DEFAULT = "https://rekor.sigstore.dev/api/v1/log/entries"


def is_enabled() -> bool:
    return os.environ.get(_REKOR_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _public_key_pem() -> str:
    """Return the active GARL signer public key as PEM.

    Rekor accepts raw-public-key hashedrekord entries; the PEM is the
    format the spec requires.
    """
    pk_hex = get_public_key_hex()
    vk = VerifyingKey.from_string(bytes.fromhex(pk_hex), curve=SECP256k1)
    pem = vk.to_pem()
    if isinstance(pem, bytes):
        pem = pem.decode("ascii")
    return pem


def _build_hashedrekord_entry(content_hash_hex: str, signature_hex: str) -> dict:
    return {
        "apiVersion": "0.0.1",
        "kind": "hashedrekord",
        "spec": {
            "signature": {
                "content": base64.b64encode(bytes.fromhex(signature_hex)).decode("ascii"),
                "publicKey": {
                    "content": base64.b64encode(_public_key_pem().encode("ascii")).decode("ascii"),
                },
            },
            "data": {
                "hash": {"algorithm": "sha256", "value": content_hash_hex},
            },
        },
    }


def anchor_sync(
    content_hash_hex: str,
    signature_hex: str,
    endpoint: str | None = None,
    timeout_s: float = 8.0,
) -> dict | None:
    """POST a hashedrekord entry; return {uuid, log_index, url} or None."""
    url = endpoint or os.environ.get(_REKOR_URL_ENV) or _REKOR_DEFAULT
    try:
        entry = _build_hashedrekord_entry(content_hash_hex, signature_hex)
        resp = httpx.post(url, json=entry, timeout=timeout_s)
        if resp.status_code not in (200, 201):
            logger.warning("rekor anchor non-2xx %s: %s", resp.status_code, resp.text[:200])
            return None
        body = resp.json()
        # Rekor returns {"<uuid>": {...}} for a single entry.
        if not isinstance(body, dict) or not body:
            return None
        uuid, payload = next(iter(body.items()))
        log_index = (payload or {}).get("logIndex")
        base = url.rsplit("/api/", 1)[0]
        view_url = f"{base}/?uuid={uuid}"
        return {"uuid": uuid, "log_index": log_index, "url": view_url}
    except Exception as e:  # noqa: BLE001
        logger.warning("rekor anchor failed: %s", e)
        return None


def anchor_background(
    trace_id: str,
    content_hash_hex: str,
    signature_hex: str,
    on_success,
) -> None:
    """Fire-and-forget wrapper. Calls ``on_success(trace_id, rekor_info)``
    on the daemon thread when the anchor round-trip returns successfully."""
    if not is_enabled():
        return

    def _run():
        info = anchor_sync(content_hash_hex, signature_hex)
        if info:
            try:
                on_success(trace_id, info)
            except Exception as e:  # noqa: BLE001
                logger.warning("rekor on_success callback failed for %s: %s", trace_id, e)

    threading.Thread(target=_run, daemon=True).start()
