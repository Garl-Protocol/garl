"""
Session-alert API surface (session-level behavioral layer v0).

Read endpoints are public (the alerts table is public-read evidence, like
receipts); the on-demand scan endpoint is owner-only via the same x-api-key
ownership check the rest of the API uses.

Kept in its own router (mounted from app.main) so the heavily-owned
app/api/routes.py stays untouched.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request

# Reuse the existing helpers rather than replicating them. routes.py does not
# import this module, so there is no circular-import risk.
from app.api.routes import (
    _check_rate_limit,
    _get_client_ip,
    _validate_uuid,
    _verify_agent_ownership,
)
from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

alert_router = APIRouter(prefix="/api/v1", tags=["Session Alerts"])

_MAX_ALERT_LIMIT = 100


def _clamp_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_ALERT_LIMIT))


@alert_router.get(
    "/agents/{agent_id}/alerts",
    summary="Signed session alerts for one agent (public, newest first)",
)
async def list_agent_alerts(
    agent_id: str,
    request: Request,
    limit: int = Query(default=20, description="Max alerts to return (<=100)"),
    offset: int = Query(default=0, description="Pagination offset"),
):
    """Session-level behavioral alerts (garl/session-alert/v0.1 envelopes)
    for one agent, newest first. Public read — alerts are append-only signed
    evidence, same disclosure model as receipts."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent ID")
    limit = _clamp_limit(limit)
    offset = max(0, offset)

    sb = _get_supabase()
    res = (
        sb.table("session_alerts")
        .select("envelope_json, created_at", count="exact")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = res.data or []
    total = res.count if getattr(res, "count", None) is not None else len(rows)
    return {
        "agent_id": agent_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "alerts": [r["envelope_json"] for r in rows],
    }


@alert_router.get(
    "/alerts",
    summary="Recent session alerts across all agents (public, newest first)",
)
async def list_recent_alerts(
    request: Request,
    limit: int = Query(default=50, description="Max alerts to return (<=100)"),
):
    _check_rate_limit(_get_client_ip(request), "default", request)
    limit = _clamp_limit(limit)

    sb = _get_supabase()
    res = (
        sb.table("session_alerts")
        .select("envelope_json, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    return {
        "limit": limit,
        "count": len(rows),
        "alerts": [r["envelope_json"] for r in rows],
    }


@alert_router.post(
    "/agents/{agent_id}/scan",
    summary="Run the session-level behavioral scan for an agent (owner only)",
)
async def scan_agent_session(
    agent_id: str,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    """Runs the rules-based session scan (spend_velocity, delegation_depth,
    novel_target, receipt_rate) over the last 24h for this agent. Requires
    the agent's own API key. Returns any alerts minted by this run; alerts
    already emitted in the last 6h are dedupe-suppressed."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="x-api-key header required")
    _check_rate_limit(x_api_key[:16], "write", request)
    _validate_uuid(agent_id, "agent ID")
    _verify_agent_ownership(agent_id, x_api_key)

    from app.services.session_anomaly import run_session_scan

    result = run_session_scan(agent_id)
    return result
