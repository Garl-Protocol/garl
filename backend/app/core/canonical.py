"""Canonical JSON for GARL signatures and hashes.

This is the SINGLE source of truth for the bytes that get signed or hashed.
The form is intentionally the one that has signed every historical receipt
and trace, so adopting it here changes nothing for existing data:

    json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

then UTF-8 encoded, then SHA-256'd by the caller.

It is deterministic and stable, but it is NOT RFC 8785 (JCS): JCS mandates
ensure_ascii=False (raw UTF-8) and ECMAScript number formatting. GARL predates
that need and cannot switch without invalidating every receipt already signed.
See protocol/spec/canonical-json-v0.1.md for the full, intentionally-frozen
specification.

The one hardening over a bare json.dumps: ``allow_nan=False``. NaN/Infinity are
not valid JSON, and a payload carrying them would otherwise be silently signed
as invalid bytes that no conformant parser could reproduce. We reject them.
"""
from __future__ import annotations

import json


def canonical_str(obj) -> str:
    """Return the canonical JSON string for ``obj``.

    Raises ValueError if ``obj`` contains NaN or Infinity.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def canonical_bytes(obj) -> bytes:
    """UTF-8 bytes of the canonical JSON string — the exact input to SHA-256."""
    return canonical_str(obj).encode("utf-8")
