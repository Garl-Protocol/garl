"""
Per-agent monthly receipt cap — silent abuse protection.

A single agent_id producing >10K signed receipts/month is almost certainly
abusing the canonical registry (or running an unintended loop). The cap
gives operators a fail-closed guardrail without per-IP rate limiting,
which is bypassable by a determined caller.

Implementation:
  - The cap is a process-wide constant. Per-agent overrides can be added
    later via a column on `agents`; we don't add it pre-emptively because
    no agent has ever come close to 10K/month in production.
  - Counting spans both `traces` (legacy) and `receipts` (Wave 2). The
    cap is for the agent, not per-table.
  - "Month" is the current UTC calendar month. Resets at the first second
    of the next month. Retry-After is computed against that reset.

Wired into:
  - app/services/traces.py (legacy /verify path)
  - app/services/action_receipts.py (new /receipts path)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

# Free-tier default. Sufficient for any realistic dev/agent workflow;
# integration tests + CI won't approach this. Operators can raise via
# env var GARL_MONTHLY_RECEIPT_CAP if a workflow legitimately needs more.
import os
DEFAULT_MONTHLY_CAP = int(os.environ.get("GARL_MONTHLY_RECEIPT_CAP", "10000"))


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_end(now: datetime) -> datetime:
    """First second of the next calendar month — the reset boundary."""
    start = _month_start(now)
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


def get_monthly_usage(agent_id: str) -> dict:
    """Return {used, cap, period_end_iso, remaining}.

    used = receipts in `traces` + `receipts` for this agent during the
    current UTC calendar month."""
    sb = _get_supabase()
    now = datetime.now(timezone.utc)
    start = _month_start(now)
    end = _month_end(now)
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    used_traces = (
        sb.table("traces")
        .select("id", count="exact")
        .eq("agent_id", agent_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
        .execute()
        .count
        or 0
    )
    used_receipts = (
        sb.table("receipts")
        .select("id", count="exact")
        .eq("agent_id", agent_id)
        .gte("created_at", start_iso)
        .lt("created_at", end_iso)
        .execute()
        .count
        or 0
    )
    used = int(used_traces) + int(used_receipts)
    return {
        "used": used,
        "cap": DEFAULT_MONTHLY_CAP,
        "remaining": max(0, DEFAULT_MONTHLY_CAP - used),
        "period_end": end_iso,
    }


def enforce_monthly_cap(agent_id: str) -> None:
    """Raise HTTPException(429) if the agent has hit its monthly cap.

    Headers include Retry-After (seconds until the cap resets) and
    X-RateLimit-* for compatibility with the per-IP limiter.
    """
    usage = get_monthly_usage(agent_id)
    if usage["used"] >= usage["cap"]:
        now = datetime.now(timezone.utc)
        end = _month_end(now)
        retry_after = max(1, int((end - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail=(
                f"Monthly receipt cap reached "
                f"({usage['used']}/{usage['cap']}). "
                f"Resets {usage['period_end']}."
            ),
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(usage["cap"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(end.timestamp())),
                "X-RateLimit-Scope": "monthly-receipts",
            },
        )
