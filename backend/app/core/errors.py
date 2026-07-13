"""Transient upstream-error classification.

Supabase/PostgREST occasionally answers with a Cloudflare 5xx (most often
``522 Connection timed out``) whose body is a multi-kilobyte HTML page. The
Python client surfaces that as a ``postgrest.exceptions.APIError`` whose string
form embeds the whole page. Two bad things follow if it is treated like any
other exception:

1. Logging it verbatim on every failed request floods the log pipeline — on
   Railway anything past 500 logs/sec is dropped (observed 2026-07-07, a
   transient Supabase blip on ``GET /verify/{hash}`` dropped 288 messages).
2. A retriable upstream blip is reported to callers as a ``500`` instead of a
   ``503`` (so CDNs/clients do not know to retry).

``is_transient_upstream_error`` lets the API map these to a bounded log line
and a ``503``, while genuine bugs keep their full traceback and ``500``.
"""
from __future__ import annotations

# httpx / network exception class names. Matched by name so this module does
# not import httpx (and stays decoupled from its version).
_TRANSIENT_EXC_NAMES = frozenset({
    "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout",
    "PoolTimeout", "ReadError", "WriteError", "RemoteProtocolError",
    "ProtocolError", "ConnectionError", "TimeoutError",
})

# Upstream/CDN status codes that mean "temporarily unavailable, retry". Kept
# deliberately narrow to gateway/CDN failures so genuine application errors
# (e.g. a PostgREST SQLSTATE like 42883) are never misread as transient.
_TRANSIENT_CODES = frozenset({
    "502", "503", "504", "520", "521", "522", "523", "524", "525", "527", "530",
})

_TRANSIENT_MSG_MARKERS = (
    "timed out", "connection reset", "connection refused", "connection aborted",
    "temporarily unavailable", "could not be generated", "bad gateway",
    "gateway time-out", "service unavailable", "server disconnected",
)


def is_transient_upstream_error(exc: BaseException) -> bool:
    """True if *exc* looks like a transient DB/CDN/network blip (retriable)."""
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    if type(exc).__name__ in _TRANSIENT_EXC_NAMES:
        return True
    code = getattr(exc, "code", None)
    if code is not None and str(code).strip() in _TRANSIENT_CODES:
        return True
    # Slice BEFORE lower(): APIError.__str__ can be multiple kilobytes of HTML.
    text = getattr(exc, "message", None)
    if not isinstance(text, str) or not text:
        text = str(exc)
    text = text[:400].lower()
    return any(marker in text for marker in _TRANSIENT_MSG_MARKERS)


def bounded_error_text(exc: BaseException, limit: int = 200) -> str:
    """A short, single-line, log-safe description of *exc*.

    Guards against multi-kilobyte error bodies (e.g. a Cloudflare HTML page
    wrapped in a PostgREST ``APIError``) landing in the logs unbounded.
    """
    text = getattr(exc, "message", None)
    if not isinstance(text, str) or not text:
        text = str(exc)
    return text.replace("\n", " ").replace("\r", " ")[:limit]
