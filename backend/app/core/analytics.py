"""Fire-and-forget server-side product analytics to PostHog (GARL project).

Captures the agentic + on-chain product events (agent registrations, receipts,
capability tokens, on-chain anchors, trace verifications) so the PostHog
dashboard reflects REAL product usage, not just website visits. Sent in a
daemon thread with a short timeout and swallowed exceptions — it can never add
latency to, or break, a request.
"""
from __future__ import annotations

import os
import threading
import logging

import httpx

logger = logging.getLogger(__name__)

# Public/publishable PostHog project key (GARL, project 454265). phc_ keys are
# client-side by design; env override wins. Empty disables capture.
_PH_KEY = os.environ.get(
    "POSTHOG_PROJECT_KEY", "phc_vMqXQjidaEWRxNHrPQRatAfpxd9SkcEPD3rCvJYZESXb"
)
_PH_URL = "https://us.i.posthog.com/i/v0/e/"


def _analytics_disabled() -> bool:
    # Never emit analytics from tests or CI — otherwise fixture identifiers
    # (e.g. 11111111-...) pollute the real PostHog project, which happened on
    # 2026-06-09. Railway/prod sets none of these, so production is unaffected.
    return bool(
        os.environ.get("PYTEST_CURRENT_TEST")
        or os.environ.get("CI")
        or os.environ.get("GARL_DISABLE_ANALYTICS")
    )


def capture(event: str, distinct_id: str | None = None, properties: dict | None = None) -> None:
    """Best-effort PostHog capture. Never raises, never blocks the caller."""
    if not _PH_KEY or _analytics_disabled():
        return

    def _send() -> None:
        try:
            httpx.post(
                _PH_URL,
                json={
                    "api_key": _PH_KEY,
                    "event": event,
                    "distinct_id": distinct_id or "garl-backend",
                    "properties": {**(properties or {}), "$lib": "garl-backend"},
                },
                timeout=3.0,
            )
        except Exception:
            pass  # analytics must never affect the request

    try:
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass
