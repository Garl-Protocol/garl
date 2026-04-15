"""GitHub webhook HMAC-SHA256 signature validator.

GitHub signs every webhook with HMAC-SHA256 over the raw body using the
webhook secret configured on the App; the signature arrives in the
``X-Hub-Signature-256`` header as ``sha256=<hex>``. Any forwarder that
bypasses this check can forge PR events from arbitrary senders — so we
treat this validator as the single security gate for the entire PR bot
pipeline.

Constant-time comparison; never logs the secret.
"""
from __future__ import annotations

import hashlib
import hmac


def verify_github_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Return True iff ``signature_header`` is a valid HMAC-SHA256 of
    ``body`` under ``secret``. Accepts either the full ``sha256=<hex>``
    form GitHub sends or a bare hex digest."""
    if not isinstance(body, (bytes, bytearray)):
        return False
    if not signature_header or not secret:
        return False

    hex_part = signature_header.strip()
    if hex_part.startswith("sha256="):
        hex_part = hex_part[len("sha256="):]
    if len(hex_part) != 64 or any(c not in "0123456789abcdefABCDEF" for c in hex_part):
        return False

    expected = hmac.new(secret.encode("utf-8"), bytes(body), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, hex_part.lower())
