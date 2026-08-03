"""
Session-level behavioral layer v0 — rules-based anomaly analysis over the
per-agent receipt stream and capability-token graph.

Why this layer exists (motivating case — Grok/Bankr, May 2026): an attacker
drained ~$150-175K through a sequence of transactions that were each
individually legitimate. Per-action checks (valid capability token, allowed
merchant, within per-action limits) all passed. The tell was only visible at
the SESSION level: spend velocity against the delegated budget, deepening
delegation chains, irreversible actions against never-before-seen targets,
and a receipt-rate burst. This module watches exactly those patterns.

v0 is deliberately rules-based (no ML), windowed at 24h, and honest about it
— see docs/session-alerts.md for the limitations list.

Rules
-----
- ``spend_velocity``        sum of receipt costs (24h) vs the agent's active
                            capability-token spend_limit_usd; warning >= 80%,
                            critical > 100%.
- ``scope_escalation_attempt``  push-based (not scan-based): minted by
                            :func:`record_escalation_attempt`, which
                            capability-token issuance calls when a child
                            token tries to WIDEN its parent (attenuation
                            violation). The token is still rejected exactly
                            as before — this only makes the attempt visible.
- ``delegation_depth``      longest parent_token_hash chain among tokens
                            issued in the window; warning >= 4, critical >= 6.
- ``novel_target``          irreversible action against a tool_server never
                            seen in the agent's prior 30d history -> warning.
- ``receipt_rate``          receipts in the last hour vs the agent's trailing
                            7d hourly average; > 10x AND >= 20 -> warning.

Every alert is a signed envelope (``garl/session-alert/v0.1``) using the same
canonical-JSON + ECDSA-secp256k1 (RFC 6979, low-S) pipeline as Action
Receipts, persisted append-only to ``session_alerts``, and delivered through
the existing per-agent webhook rail under event type ``"anomaly"``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.signing import get_active_key_id, sign_payload
from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

SESSION_ALERT_VERSION = "garl/session-alert/v0.1"

# Analysis window over the receipt stream.
WINDOW_HOURS = 24
# History horizon for the novel_target rule.
NOVEL_TARGET_HISTORY_DAYS = 30
# Don't re-emit the same (agent_id, rule) more than once per this many hours.
DEDUPE_HOURS = 6

# Rule thresholds (documented in docs/session-alerts.md — keep in sync).
SPEND_WARNING_RATIO = 0.80    # >= 80% of active spend limit
SPEND_CRITICAL_RATIO = 1.00   # > 100% of active spend limit
DELEGATION_WARNING_DEPTH = 4
DELEGATION_CRITICAL_DEPTH = 6
RECEIPT_RATE_MULTIPLIER = 10.0
RECEIPT_RATE_MIN_COUNT = 20
# Hard cap when walking a delegation chain — a cycle or absurdly deep chain
# stops here instead of looping.
MAX_CHAIN_WALK = 16

SEVERITIES = ("info", "warning", "critical")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_z(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# ──────────────────────────────────────────────────────────────────────
# Alert minting: envelope + signature + persistence + webhook
# ──────────────────────────────────────────────────────────────────────

def _recent_alert_exists(sb, agent_id: str, rule: str) -> bool:
    """Dedupe: has this (agent_id, rule) already alerted in the last
    DEDUPE_HOURS? Fail open on errors — better a duplicate alert than a
    silently swallowed one."""
    try:
        cutoff = _iso_z(_utcnow() - timedelta(hours=DEDUPE_HOURS))
        res = (
            sb.table("session_alerts")
            .select("id")
            .eq("agent_id", agent_id)
            .eq("rule", rule)
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except Exception:
        logger.warning("session-alert dedupe query failed for agent %s rule %s", agent_id, rule)
        return False


def _deliver_alert_webhooks(agent_id: str, envelope: dict) -> None:
    """Deliver through the EXISTING per-agent webhook rail (event type
    "anomaly") — HMAC signing, SSRF guard, retries all live in
    app.services.traces and are reused as-is, not reimplemented."""
    try:
        from app.services.traces import _fire_webhooks_with_retry

        _fire_webhooks_with_retry(
            agent_id,
            {
                "event": "anomaly",
                "type": "session_alert",
                "agent_id": agent_id,
                "rule": envelope["rule"],
                "severity": envelope["severity"],
                "summary": envelope["summary"],
                "alert": envelope,
                "timestamp": envelope["timestamp"],
            },
        )
    except Exception:
        logger.warning("session-alert webhook dispatch failed for agent %s", agent_id)


def mint_session_alert(
    *,
    agent_id: str,
    rule: str,
    severity: str,
    summary: str,
    evidence: dict,
    window: dict | None = None,
    dedupe: bool = True,
) -> dict | None:
    """Build, sign, persist, and webhook-deliver one session alert.

    Returns the signed envelope, or None when suppressed by the dedupe
    window. Signing follows the exact receipts pipeline: sign_payload over
    the envelope-without-signature, then attach signature +
    verification_key_id.
    """
    if severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {SEVERITIES}, got {severity!r}")

    sb = _get_supabase()
    if dedupe and _recent_alert_exists(sb, agent_id, rule):
        logger.info("session-alert deduped: agent=%s rule=%s", agent_id, rule)
        return None

    now = _utcnow()
    if window is None:
        window = {
            "start": _iso_z(now - timedelta(hours=WINDOW_HOURS)),
            "end": _iso_z(now),
            "hours": WINDOW_HOURS,
        }

    envelope: dict[str, Any] = {
        "alert_id": str(uuid.uuid4()),
        "version": SESSION_ALERT_VERSION,
        "issuer": "https://api.garl.ai",
        "agent_identity": f"did:garl:{agent_id}",
        "rule": rule,
        "severity": severity,
        "summary": summary,
        "evidence": evidence,
        "window": window,
        "timestamp": _iso_z(now),
    }
    signature, _digest = sign_payload(envelope)
    envelope["signature"] = signature
    envelope["verification_key_id"] = get_active_key_id()

    sb.table("session_alerts").insert(
        {
            "agent_id": agent_id,
            "rule": rule,
            "severity": severity,
            "summary": summary,
            "evidence": evidence,
            "signature": signature,
            "verification_key_id": envelope["verification_key_id"],
            "envelope_json": envelope,
        }
    ).execute()

    _deliver_alert_webhooks(agent_id, envelope)
    return envelope


# ──────────────────────────────────────────────────────────────────────
# Scope-escalation hook (called from capability-token issuance)
# ──────────────────────────────────────────────────────────────────────

def record_escalation_attempt(agent_id: str, parent_hash: str | None, reason: str) -> dict | None:
    """Record a capability-token attenuation violation at ISSUE time as a
    signed alert (rule = 'scope_escalation_attempt').

    Called by issue_capability_token() at the point where
    _enforce_attenuation raises. The issuance still fails with the identical
    ValueError — this hook only turns a silent rejection into visible,
    signed evidence (the Grok/Bankr escalation was exactly a rejected-but-
    unlogged class of event). NEVER raises: an alert-rail hiccup must not
    change issuance behavior.
    """
    try:
        return mint_session_alert(
            agent_id=agent_id,
            rule="scope_escalation_attempt",
            severity="critical",
            summary=(
                "Rejected capability-token issuance: child token attempted to "
                "widen its parent (attenuation violation)."
            ),
            evidence={
                "parent_token_hash": parent_hash,
                "reason": str(reason)[:500],
            },
        )
    except Exception:
        logger.warning("record_escalation_attempt failed for agent %s", agent_id)
        return None


# ──────────────────────────────────────────────────────────────────────
# Data fetch helpers
# ──────────────────────────────────────────────────────────────────────

def _fetch_window_receipts(sb, agent_id: str, since_iso: str) -> list[dict]:
    res = (
        sb.table("receipts")
        .select("receipt_id, action_type, side_effect, tool_server, cost, created_at")
        .eq("agent_id", agent_id)
        .gte("created_at", since_iso)
        .execute()
    )
    return res.data or []


def _sum_cost_usd(receipts: list[dict]) -> float:
    """Sum the usd component of receipt costs. The cost JSONB shape per the
    Action Receipt v0.1 spec is {usd, tokens_in, tokens_out, duration_ms}
    with every key optional; missing/None/malformed costs count as 0. A bare
    numeric cost is tolerated as usd."""
    total = 0.0
    for r in receipts:
        cost = r.get("cost")
        usd: Any = None
        if isinstance(cost, dict):
            usd = cost.get("usd")
        elif isinstance(cost, (int, float)) and not isinstance(cost, bool):
            usd = cost
        if isinstance(usd, bool) or not isinstance(usd, (int, float)):
            continue
        if usd != usd or usd in (float("inf"), float("-inf")):  # NaN / inf guard
            continue
        total += float(usd)
    return total


def _active_spend_limit(sb, agent_id: str, now_iso: str) -> float | None:
    """The agent's authorized session budget: the LARGEST spend_limit_usd
    among currently-active (non-revoked, non-expired) capability tokens.
    Max, not min, keeps v0 conservative on false positives — crossing 100%
    of the most generous active grant is unambiguously over-budget."""
    res = (
        sb.table("capability_tokens")
        .select("spend_limit_usd")
        .eq("agent_id", agent_id)
        .is_("revoked_at", "null")
        .gt("expires_at", now_iso)
        .execute()
    )
    limits = [
        float(row["spend_limit_usd"])
        for row in (res.data or [])
        if row.get("spend_limit_usd") is not None
    ]
    valid = [x for x in limits if x > 0]
    return max(valid) if valid else None


def _tokens_issued_in_window(sb, agent_id: str, since_iso: str) -> list[dict]:
    res = (
        sb.table("capability_tokens")
        .select("token_hash, parent_token_hash, issued_at")
        .eq("agent_id", agent_id)
        .gte("issued_at", since_iso)
        .execute()
    )
    return res.data or []


def _chain_depth(sb, token_row: dict, depth_cache: dict[str, int]) -> int:
    """Length of the delegation chain ending at this token (root token has
    depth 1). Cycle-safe and capped at MAX_CHAIN_WALK."""
    depth = 1
    seen = {token_row.get("token_hash")}
    parent = token_row.get("parent_token_hash")
    while parent and depth < MAX_CHAIN_WALK:
        if parent in depth_cache:
            return depth + depth_cache[parent]
        if parent in seen:
            break  # cycle — stop counting
        seen.add(parent)
        depth += 1
        res = (
            sb.table("capability_tokens")
            .select("token_hash, parent_token_hash")
            .eq("token_hash", parent)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        parent = row.get("parent_token_hash") if row else None
    depth_cache[token_row.get("token_hash") or ""] = depth
    return depth


def _count_receipts_since(sb, agent_id: str, since_iso: str) -> int:
    res = (
        sb.table("receipts")
        .select("receipt_id", count="exact")
        .eq("agent_id", agent_id)
        .gte("created_at", since_iso)
        .execute()
    )
    if getattr(res, "count", None) is not None:
        return int(res.count)
    return len(res.data or [])


# ──────────────────────────────────────────────────────────────────────
# Rules
# ──────────────────────────────────────────────────────────────────────

def _rule_spend_velocity(sb, agent_id: str, receipts: list[dict], now: datetime) -> dict | None:
    limit = _active_spend_limit(sb, agent_id, _iso_z(now))
    if limit is None:
        return None  # no active spend-limited token — nothing to measure against
    spent = _sum_cost_usd(receipts)
    if spent <= 0:
        return None
    ratio = spent / limit
    if ratio > SPEND_CRITICAL_RATIO:
        severity = "critical"
    elif ratio >= SPEND_WARNING_RATIO:
        severity = "warning"
    else:
        return None
    return mint_session_alert(
        agent_id=agent_id,
        rule="spend_velocity",
        severity=severity,
        summary=(
            f"Spend in the last {WINDOW_HOURS}h (${spent:.2f}) is "
            f"{ratio * 100:.0f}% of the active capability spend limit (${limit:.2f})."
        ),
        evidence={
            "window_spend_usd": round(spent, 6),
            "active_spend_limit_usd": round(limit, 6),
            "ratio": round(ratio, 4),
            "receipt_count": len(receipts),
        },
    )


def _rule_delegation_depth(sb, agent_id: str, now: datetime) -> dict | None:
    since = _iso_z(now - timedelta(hours=WINDOW_HOURS))
    tokens = _tokens_issued_in_window(sb, agent_id, since)
    if not tokens:
        return None
    depth_cache: dict[str, int] = {}
    max_depth = 0
    deepest_token = None
    for tok in tokens:
        d = _chain_depth(sb, tok, depth_cache)
        if d > max_depth:
            max_depth = d
            deepest_token = tok.get("token_hash")
    if max_depth >= DELEGATION_CRITICAL_DEPTH:
        severity = "critical"
    elif max_depth >= DELEGATION_WARNING_DEPTH:
        severity = "warning"
    else:
        return None
    return mint_session_alert(
        agent_id=agent_id,
        rule="delegation_depth",
        severity=severity,
        summary=(
            f"Capability delegation chain reached depth {max_depth} in the "
            f"last {WINDOW_HOURS}h."
        ),
        evidence={
            "max_depth": max_depth,
            "deepest_token_hash": deepest_token,
            "tokens_issued_in_window": len(tokens),
        },
    )


def _rule_novel_target(sb, agent_id: str, receipts: list[dict], now: datetime) -> dict | None:
    window_start = now - timedelta(hours=WINDOW_HOURS)
    irreversible_targets = {
        r["tool_server"]
        for r in receipts
        if r.get("side_effect") == "irreversible" and r.get("tool_server")
    }
    if not irreversible_targets:
        return None
    history_res = (
        sb.table("receipts")
        .select("tool_server")
        .eq("agent_id", agent_id)
        .gte("created_at", _iso_z(now - timedelta(days=NOVEL_TARGET_HISTORY_DAYS)))
        .lt("created_at", _iso_z(window_start))
        .execute()
    )
    known = {r["tool_server"] for r in (history_res.data or []) if r.get("tool_server")}
    novel = sorted(irreversible_targets - known)
    if not novel:
        return None
    return mint_session_alert(
        agent_id=agent_id,
        rule="novel_target",
        severity="warning",
        summary=(
            f"Irreversible action(s) against {len(novel)} target(s) not seen "
            f"in the agent's prior {NOVEL_TARGET_HISTORY_DAYS}d history: "
            + ", ".join(novel[:5])
            + ("…" if len(novel) > 5 else "")
        ),
        evidence={
            "novel_targets": novel,
            "known_target_count": len(known),
            "history_days": NOVEL_TARGET_HISTORY_DAYS,
        },
    )


def _rule_receipt_rate(sb, agent_id: str, now: datetime) -> dict | None:
    last_hour = _count_receipts_since(sb, agent_id, _iso_z(now - timedelta(hours=1)))
    if last_hour < RECEIPT_RATE_MIN_COUNT:
        return None
    week = _count_receipts_since(sb, agent_id, _iso_z(now - timedelta(days=7)))
    # Baseline excludes the current burst hour, so a brand-new agent's first
    # burst still registers (baseline 0) and a steady producer does not.
    prior = max(week - last_hour, 0)
    baseline_avg = prior / (7 * 24 - 1)
    if baseline_avg > 0 and last_hour <= RECEIPT_RATE_MULTIPLIER * baseline_avg:
        return None
    return mint_session_alert(
        agent_id=agent_id,
        rule="receipt_rate",
        severity="warning",
        summary=(
            f"{last_hour} receipts in the last hour vs a trailing 7d hourly "
            f"average of {baseline_avg:.2f} (>{RECEIPT_RATE_MULTIPLIER:.0f}x)."
        ),
        evidence={
            "receipts_last_hour": last_hour,
            "trailing_7d_hourly_avg": round(baseline_avg, 4),
            "multiplier_threshold": RECEIPT_RATE_MULTIPLIER,
            "min_count_threshold": RECEIPT_RATE_MIN_COUNT,
        },
    )


# ──────────────────────────────────────────────────────────────────────
# Scan entrypoints
# ──────────────────────────────────────────────────────────────────────

def scan_agent(agent_id: str) -> list[dict]:
    """Run every scan-based rule for one agent; return minted alert
    envelopes (dedupe-suppressed rules return nothing). Rules are isolated:
    one rule failing never blocks the others."""
    sb = _get_supabase()
    now = _utcnow()
    since = _iso_z(now - timedelta(hours=WINDOW_HOURS))
    try:
        receipts = _fetch_window_receipts(sb, agent_id, since)
    except Exception:
        logger.warning("session scan: window receipt fetch failed for agent %s", agent_id)
        receipts = []

    alerts: list[dict] = []
    rule_runs = (
        ("spend_velocity", lambda: _rule_spend_velocity(sb, agent_id, receipts, now)),
        ("delegation_depth", lambda: _rule_delegation_depth(sb, agent_id, now)),
        ("novel_target", lambda: _rule_novel_target(sb, agent_id, receipts, now)),
        ("receipt_rate", lambda: _rule_receipt_rate(sb, agent_id, now)),
    )
    for rule_name, run in rule_runs:
        try:
            alert = run()
            if alert:
                alerts.append(alert)
        except Exception:
            logger.warning("session scan rule %s failed for agent %s", rule_name, agent_id)
    return alerts


def run_session_scan(agent_id: str | None = None) -> dict:
    """Scan one agent, or every agent with activity (receipts submitted or
    capability tokens issued) inside the 24h window.

    Returns {"scanned": <agent count>, "alerts": [envelope, ...],
    "window_hours": 24}.
    """
    sb = _get_supabase()
    now = _utcnow()
    since = _iso_z(now - timedelta(hours=WINDOW_HOURS))

    if agent_id:
        agent_ids = [agent_id]
    else:
        active: set[str] = set()
        try:
            r = (
                sb.table("receipts").select("agent_id").gte("created_at", since).execute()
            )
            active.update(row["agent_id"] for row in (r.data or []) if row.get("agent_id"))
        except Exception:
            logger.warning("session scan: failed to list active receipt agents")
        try:
            t = (
                sb.table("capability_tokens").select("agent_id").gte("issued_at", since).execute()
            )
            active.update(row["agent_id"] for row in (t.data or []) if row.get("agent_id"))
        except Exception:
            logger.warning("session scan: failed to list active token agents")
        agent_ids = sorted(active)

    alerts: list[dict] = []
    for aid in agent_ids:
        alerts.extend(scan_agent(aid))

    return {"scanned": len(agent_ids), "alerts": alerts, "window_hours": WINDOW_HOURS}
