import uuid
import hmac
import secrets
import hashlib
import logging
import threading
from datetime import datetime, timezone

from app.core.supabase_client import get_supabase
from app.core.signing import get_public_key_hex
from app.models.schemas import AgentRegisterRequest
from app.services.reputation import (
    project_decay, apply_time_decay, compute_endorsement_bonus,
    compute_certification_tier, compute_confidence, clamp_score, BASELINE,
    TIER_ENDORSEMENT_MULTIPLIER,
)

logger = logging.getLogger(__name__)


def _generate_sovereign_id(agent_uuid: str) -> str:
    """Generate Decentralized Identifier (DID): did:garl:<uuid>"""
    return f"did:garl:{agent_uuid}"


def _apply_lazy_decay(agent: dict, db) -> dict:
    """Apply lazy decay to inactive agents' scores."""
    last_trace = agent.get("last_trace_at")
    if not last_trace or agent.get("total_traces", 0) == 0:
        return agent

    try:
        last_dt = datetime.fromisoformat(last_trace.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return agent

    now = datetime.now(timezone.utc)
    hours_since = (now - last_dt).total_seconds() / 3600.0

    if hours_since < 24:
        return agent

    fields = [
        "trust_score", "score_reliability", "score_speed",
        "score_cost_efficiency", "score_consistency", "score_security",
    ]

    updated = {}
    changed = False
    for field in fields:
        old_val = float(agent.get(field) or BASELINE)
        new_val = apply_time_decay(old_val, hours_since)
        if abs(new_val - old_val) > 0.01:
            updated[field] = new_val
            agent[field] = new_val
            changed = True

    if changed:
        new_tier = compute_certification_tier(
            float(agent.get("trust_score", BASELINE)),
            agent.get("anomaly_flags"),
            int(agent.get("total_traces", 0)),
        )
        updated["certification_tier"] = new_tier
        agent["certification_tier"] = new_tier
        updated["updated_at"] = now.isoformat()
        # Decay writeback is advisory — the in-memory agent we return is
        # already correct for this response. Fire the UPDATE on a daemon
        # thread so the caller doesn't pay the Postgres round-trip on
        # every /agents/{id} read for the 100+ dormant agents in the
        # ledger. If the write drops (container recycle mid-flight), the
        # next read simply recomputes the same decay.
        _aid = agent["id"]
        threading.Thread(
            target=_writeback_decay, args=(_aid, updated), daemon=True
        ).start()

    return agent


def _writeback_decay(agent_id: str, updated: dict) -> None:
    try:
        get_supabase().table("agents").update(updated).eq("id", agent_id).execute()
    except Exception as e:  # pragma: no cover — background best-effort
        logger.debug("lazy decay writeback failed for %s: %s", agent_id, e)


def register_agent(req: AgentRegisterRequest, developer_id: str | None = None) -> dict:
    """New agent registration: DID assignment, security dimension initialization."""
    db = get_supabase()

    existing = db.table("agents").select("id").eq("name", req.name).eq("is_deleted", False).execute()
    if existing.data:
        raise ValueError(f"Agent name '{req.name}' is already taken. Choose a different name.")

    agent_id = str(uuid.uuid4())
    api_key = f"garl_{secrets.token_urlsafe(32)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    sovereign_id = _generate_sovereign_id(agent_id)
    now = datetime.now(timezone.utc).isoformat()

    # If the caller supplied a developer_handle (GitHub handle, email, etc.)
    # we persist only its SHA-256 hash. Plaintext is discarded — the stored
    # value is an opaque sybil-detection handle, not a PII store.
    handle = getattr(req, "developer_handle", None)
    if handle and not developer_id:
        developer_id = "devh_" + hashlib.sha256(handle.strip().lower().encode()).hexdigest()[:32]

    agent_data = {
        "id": agent_id,
        "name": req.name,
        "description": req.description,
        "framework": req.framework,
        "category": req.category.value,
        "trust_score": BASELINE,
        "total_traces": 0,
        "success_count": 0,
        "success_rate": 0.0,
        "consecutive_successes": 0,
        "score_reliability": BASELINE,
        "score_speed": BASELINE,
        "score_cost_efficiency": BASELINE,
        "score_consistency": BASELINE,
        "score_security": BASELINE,
        "total_cost_usd": 0,
        "avg_duration_ms": 0,
        "anomaly_flags": [],
        "endorsement_score": 0.0,
        "endorsement_count": 0,
        "sovereign_id": sovereign_id,
        "certification_tier": "bronze",
        # security_events and permissions_declared columns were dropped in
        # migration v15 — they stayed 0% populated across 131 production
        # agents. Any supplied value on the request is ignored (kept in
        # the schema for backward-compat only).
        "is_deleted": False,
        "is_sandbox": req.is_sandbox,
        "homepage_url": req.homepage_url,
        "api_key_hash": api_key_hash,
        "developer_id": developer_id,
        "created_at": now,
        "updated_at": now,
    }

    db.table("agents").insert(agent_data).execute()

    response = {
        "id": agent_id,
        "name": req.name,
        "api_key": api_key,
        "sovereign_id": sovereign_id,
        "trust_score": BASELINE,
        "certification_tier": "bronze",
    }
    full = {**agent_data, "api_key": api_key}
    full.pop("api_key_hash", None)
    for k, v in full.items():
        if k not in response:
            response[k] = v
    try:
        from app.core.analytics import capture as _ph
        _ph("agent_registered", agent_id, {"framework": getattr(req, "framework", None), "category": str(getattr(req, "category", "") or "")})
    except Exception:
        pass
    return response


def get_agent(agent_id: str) -> dict | None:
    db = get_supabase()
    res = db.table("agents").select("*").eq("id", agent_id).eq("is_deleted", False).execute()
    if not res.data:
        return None
    agent = res.data[0]
    agent.pop("api_key", None)
    agent.pop("api_key_hash", None)
    agent = _apply_lazy_decay(agent, db)

    score = float(agent.get("trust_score", BASELINE))
    traces = int(agent.get("total_traces", 0))
    confidence, margin = compute_confidence(traces)
    agent["confidence"] = confidence
    agent["trust_score_lower"] = round(max(0, score - margin), 2)
    agent["trust_score_upper"] = round(min(100, score + margin), 2)

    return agent


_SAFE_TRACE_META_KEYS = {
    "github_repo", "commit_sha", "ai_tool", "ai_confidence", "files_changed",
    "model", "runtime_env",
}


def _public_trace_view(t: dict) -> dict:
    """Strip an agent's private I/O from a trace before exposing it on a public,
    unauthenticated surface. The privacy policy promises input_summary /
    output_summary are never surfaced; `metadata` is an arbitrary
    client-supplied blob, so only a known provenance whitelist is exposed (so an
    agent operator can't accidentally publish secrets/PII via metadata)."""
    out = {k: v for k, v in t.items() if k not in ("input_summary", "output_summary")}
    md = t.get("metadata")
    if isinstance(md, dict):
        out["metadata"] = {k: v for k, v in md.items() if k in _SAFE_TRACE_META_KEYS}
    return out


def get_agent_detail(agent_id: str) -> dict | None:
    """Agent detail: profile + last 50 traces + 100 history entries + decay projection."""
    db = get_supabase()

    agent_res = db.table("agents").select("*").eq("id", agent_id).eq("is_deleted", False).execute()
    if not agent_res.data:
        return None

    agent = agent_res.data[0]
    agent.pop("api_key", None)
    agent.pop("api_key_hash", None)
    agent = _apply_lazy_decay(agent, db)

    traces_res = (
        db.table("traces")
        .select("*")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    history_res = (
        db.table("reputation_history")
        .select("*")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    score = float(agent.get("trust_score", BASELINE))
    decay_projection = project_decay(score, [7, 30, 60, 90])

    return {
        "agent": agent,
        "recent_traces": [_public_trace_view(t) for t in (traces_res.data or [])],
        "reputation_history": history_res.data or [],
        "decay_projection": decay_projection,
    }


def get_leaderboard(category: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    db = get_supabase()
    query = db.table("agents").select(
        "id, name, framework, category, trust_score, total_traces, success_rate, "
        "score_reliability, score_speed, score_cost_efficiency, score_consistency, "
        "score_security, last_trace_at, endorsement_score, endorsement_count, "
        "sovereign_id, certification_tier, is_sandbox",
        count="exact",
    ).eq("is_deleted", False).eq("is_sandbox", False)

    if category and category != "all":
        query = query.eq("category", category)

    query = (
        query.gt("total_traces", 0)
        .order("trust_score", desc=True)
        .range(offset, offset + limit - 1)
    )
    res = query.execute()
    total = res.count or 0

    rows = res.data or []
    rows = batch_apply_decay_for_leaderboard(rows, db)
    rows.sort(key=lambda r: (-float(r.get("trust_score", 0)), r.get("id", "")))

    entries = []
    for i, row in enumerate(rows, offset + 1):
        entries.append({**row, "rank": i})

    return {
        "data": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": total > offset + limit,
    }


def get_a2a_trust(agent_id: str) -> dict | None:
    """Agent-to-Agent trust check: risk level, recommendation, and 5 dimensions."""
    db = get_supabase()
    res = db.table("agents").select(
        "id, name, trust_score, success_rate, total_traces, "
        "score_reliability, score_speed, score_cost_efficiency, score_consistency, "
        "score_security, anomaly_flags, last_trace_at, framework, category, "
        "sovereign_id, certification_tier"
    ).eq("id", agent_id).eq("is_deleted", False).execute()

    if not res.data:
        return None

    agent = _apply_lazy_decay(res.data[0], db)
    score = float(agent["trust_score"])
    traces = int(agent["total_traces"])
    verified = traces >= 10
    anomalies = agent.get("anomaly_flags") or []
    has_recent_anomaly = len([a for a in anomalies if not a.get("archived")]) > 0

    if score >= 75 and verified and not has_recent_anomaly:
        risk_level = "low"
        recommendation = "trusted"
    elif score >= 60 and verified:
        risk_level = "low"
        recommendation = "trusted_with_monitoring"
    elif score >= 50:
        risk_level = "medium"
        recommendation = "proceed_with_monitoring"
    elif score >= 25:
        risk_level = "high"
        recommendation = "caution"
    else:
        risk_level = "critical"
        recommendation = "do_not_delegate"

    if has_recent_anomaly and risk_level == "low":
        risk_level = "medium"
        recommendation = "proceed_with_monitoring"

    confidence, margin = compute_confidence(traces)

    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "trust_score": score,
        "trust_score_lower": round(max(0, score - margin), 2),
        "trust_score_upper": round(min(100, score + margin), 2),
        "confidence": confidence,
        "success_rate": float(agent["success_rate"]),
        "total_traces": traces,
        "verified": verified,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "certification_tier": agent.get("certification_tier", "bronze"),
        "sovereign_id": agent.get("sovereign_id"),
        "dimensions": {
            "reliability": float(agent.get("score_reliability") or BASELINE),
            "security": float(agent.get("score_security") or BASELINE),
            "speed": float(agent.get("score_speed") or BASELINE),
            "cost_efficiency": float(agent.get("score_cost_efficiency") or BASELINE),
            "consistency": float(agent.get("score_consistency") or BASELINE),
        },
        "anomalies": anomalies[-3:] if anomalies else [],
        "last_active": agent.get("last_trace_at"),
    }


def get_agent_card(agent_id: str) -> dict | None:
    """Agent Card: DID, tier, and 5-dimensional trust profile."""
    db = get_supabase()
    res = db.table("agents").select("*").eq("id", agent_id).eq("is_deleted", False).execute()
    if not res.data:
        return None

    agent = res.data[0]
    score = float(agent.get("trust_score", BASELINE))
    verified = int(agent.get("total_traces", 0)) >= 10

    return {
        "name": agent["name"],
        "description": agent.get("description", ""),
        "version": "1.0.1",
        "protocol": "garl/v1",
        "sovereign_id": agent.get("sovereign_id"),
        "certification_tier": agent.get("certification_tier", "bronze"),
        "api": {
            "type": "rest",
            "url": f"/api/v1/agents/{agent_id}",
        },
        "auth": {
            "type": "api_key",
            "header": "x-api-key",
        },
        "capabilities": [
            {
                "type": agent.get("category", "other"),
                "description": agent.get("description", ""),
            }
        ],
        "garl_trust": {
            "agent_id": agent["id"],
            "trust_score": score,
            "verified": verified,
            "success_rate": float(agent.get("success_rate", 0)),
            "total_traces": int(agent["total_traces"]),
            "dimensions": {
                "reliability": float(agent.get("score_reliability") or BASELINE),
                "security": float(agent.get("score_security") or BASELINE),
                "speed": float(agent.get("score_speed") or BASELINE),
                "cost_efficiency": float(agent.get("score_cost_efficiency") or BASELINE),
                "consistency": float(agent.get("score_consistency") or BASELINE),
            },
            "public_key": get_public_key_hex(),
            "last_verified": agent.get("last_trace_at"),
        },
        "framework": agent.get("framework", "custom"),
        "homepage": agent.get("homepage_url"),
        "created_at": agent.get("created_at"),
    }


def compare_agents(agent_ids: list[str]) -> list[dict]:
    db = get_supabase()
    results = []
    for aid in agent_ids[:10]:
        res = db.table("agents").select(
            "id, name, framework, category, trust_score, total_traces, success_rate, "
            "score_reliability, score_speed, score_cost_efficiency, score_consistency, "
            "score_security, avg_duration_ms, total_cost_usd, sovereign_id, certification_tier"
        ).eq("id", aid).eq("is_deleted", False).execute()
        if res.data:
            results.append(res.data[0])
    return results


def get_recent_traces(limit: int = 20, offset: int = 0) -> dict:
    db = get_supabase()
    # The public feed must only show traces from real (non-sandbox) agents —
    # otherwise deep pagination surfaces seed/sandbox agents' old traces and the
    # `total` overcounts, contradicting the leaderboard/stats which hide them.
    # Filter via an embedded inner join (server-side), so it stays correct
    # regardless of how many agents exist (no client-side ID list / row cap).
    res = (
        db.table("traces")
        .select(
            "id, agent_id, task_description, status, duration_ms, trust_delta, category, cost_usd, trace_hash, created_at, agents!inner(is_sandbox)",
            count="exact",
        )
        .eq("agents.is_deleted", False)
        .eq("agents.is_sandbox", False)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    total = res.count or 0
    # Strip the join artifact so the response shape is unchanged.
    rows = [{k: v for k, v in row.items() if k != "agents"} for row in (res.data or [])]

    return {
        "data": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": total > offset + limit,
    }


def get_stats() -> dict:
    db = get_supabase()
    # Count only real agents (non-sandbox, non-deleted) AND their traces, so the
    # public totals use the same population as the leaderboard (which hides
    # sandbox/seed agents). Use server-side exact counts (count="exact",
    # head=True) — NOT a Python len()/sum() over fetched rows, which PostgREST
    # caps at db-max-rows (~1000) and would silently undercount past that.
    total_agents = (
        db.table("agents")
        .select("id", count="exact", head=True)
        .eq("is_deleted", False)
        .eq("is_sandbox", False)
        .execute()
        .count
        or 0
    )
    # Traces whose agent is a real (non-sandbox) agent, via an embedded inner
    # join — exact count, no row-cap issue.
    total_traces = (
        db.table("traces")
        .select("id, agents!inner(is_sandbox)", count="exact", head=True)
        .eq("agents.is_deleted", False)
        .eq("agents.is_sandbox", False)
        .execute()
        .count
        or 0
    )

    top_agent_res = (
        db.table("agents")
        .select("name, trust_score, certification_tier")
        .eq("is_deleted", False)
        .eq("is_sandbox", False)
        .gt("total_traces", 0)
        .order("trust_score", desc=True)
        .limit(1)
        .execute()
    )

    # Wave 2 surfaces — counts may legitimately be 0 if v18 migration is
    # fresh and no v0.1 receipt has landed yet. Tolerate missing tables
    # gracefully so the endpoint stays useful through deployment churn.
    def _count(table: str, **eq_filters) -> int:
        try:
            q = db.table(table).select("*", count="exact", head=True)
            for k, v in eq_filters.items():
                q = q.eq(k, v)
            return q.execute().count or 0
        except Exception:
            return 0

    receipts_total = _count("receipts")
    receipts_reversible = _count("receipts", side_effect="reversible")
    receipts_irreversible = _count("receipts", side_effect="irreversible")
    receipts_none = _count("receipts", side_effect="none")
    cap_tokens_total = _count("capability_tokens")
    compensations_total = _count("compensations")

    return {
        "total_agents": total_agents,
        "total_traces": total_traces,
        "top_agent": top_agent_res.data[0] if top_agent_res.data else None,
        "wave2": {
            "action_receipts": {
                "total": receipts_total,
                "by_side_effect": {
                    "none": receipts_none,
                    "reversible": receipts_reversible,
                    "irreversible": receipts_irreversible,
                },
            },
            "capability_tokens_issued": cap_tokens_total,
            "compensations_recorded": compensations_total,
        },
    }


def get_public_stats() -> dict:
    """Extended public dashboard stats. Adds active-agents-7d,
    active-capability-tokens, succeeded-compensations on top of get_stats.
    Used by https://garl.ai/stats."""
    from datetime import datetime, timedelta, timezone

    db = get_supabase()
    base = get_stats()

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()

    def _count_active_tokens() -> int:
        try:
            return (
                db.table("capability_tokens")
                .select("*", count="exact", head=True)
                .is_("revoked_at", "null")
                .gt("expires_at", now_iso)
                .execute()
                .count
                or 0
            )
        except Exception:
            return 0

    def _count_succeeded_comps() -> int:
        try:
            return (
                db.table("compensations")
                .select("*", count="exact", head=True)
                .eq("status", "succeeded")
                .execute()
                .count
                or 0
            )
        except Exception:
            return 0

    active_7d = (
        db.table("agents")
        .select("*", count="exact", head=True)
        .eq("is_deleted", False)
        .eq("is_sandbox", False)
        .gte("last_trace_at", seven_days_ago)
        .execute()
        .count
        or 0
    )

    return {
        **base,
        "active_agents_7d": active_7d,
        "capability_tokens_active": _count_active_tokens(),
        "compensations_succeeded": _count_succeeded_comps(),
        "protocol_version": "1.4.0",
    }


def search_agents(query: str = "", category: str | None = None, limit: int = 10, offset: int = 0) -> dict:
    db = get_supabase()
    q = db.table("agents").select(
        "id, name, description, framework, category, trust_score, total_traces, success_rate, "
        "score_reliability, score_speed, score_cost_efficiency, score_consistency, "
        "score_security, sovereign_id, certification_tier, is_sandbox",
        count="exact",
    ).eq("is_deleted", False).eq("is_sandbox", False)

    if category and category != "all":
        q = q.eq("category", category)

    if query:
        safe_query = query.replace("%", "").replace("\\", "").replace(",", "").replace(".", "")[:100]
        if safe_query:
            q = q.or_(f"name.ilike.%{safe_query}%,description.ilike.%{safe_query}%")

    res = q.order("trust_score", desc=True).range(offset, offset + limit - 1).execute()
    total = res.count or 0

    data = [
        {
            **row,
            "verified": int(row.get("total_traces", 0)) >= 10,
            "badge_url": f"/api/v1/badge/svg/{row['id']}",
        }
        for row in (res.data or [])
    ]

    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": total > offset + limit,
    }


# --- Smart Delegation & Routing ---

def route_agents(category: str, min_tier: str = "silver", limit: int = 3) -> dict:
    """Recommend the most trusted agents filtered by category and minimum tier."""
    db = get_supabase()

    tier_order = ["bronze", "silver", "gold", "enterprise"]
    min_tier_idx = tier_order.index(min_tier) if min_tier in tier_order else 1
    allowed_tiers = tier_order[min_tier_idx:]

    query = (
        db.table("agents")
        .select(
            "id, name, trust_score, certification_tier, sovereign_id, "
            "score_reliability, score_speed, score_cost_efficiency, score_consistency, "
            "score_security, total_traces, success_rate, framework, category"
        )
        .eq("is_deleted", False)
        .eq("category", category)
        .gt("total_traces", 0)
        .in_("certification_tier", allowed_tiers)
        .order("trust_score", desc=True)
        .limit(limit)
    )
    res = query.execute()

    recommendations = []
    for agent in (res.data or []):
        recommendations.append({
            "id": agent["id"],
            "name": agent["name"],
            "trust_score": float(agent["trust_score"]),
            "certification_tier": agent["certification_tier"],
            "sovereign_id": agent.get("sovereign_id"),
            "dimensions": {
                "reliability": float(agent.get("score_reliability") or BASELINE),
                "security": float(agent.get("score_security") or BASELINE),
                "speed": float(agent.get("score_speed") or BASELINE),
                "cost_efficiency": float(agent.get("score_cost_efficiency") or BASELINE),
                "consistency": float(agent.get("score_consistency") or BASELINE),
            },
            "total_traces": int(agent["total_traces"]),
            "success_rate": float(agent["success_rate"]),
            "framework": agent.get("framework"),
        })

    return {
        "category": category,
        "min_tier": min_tier,
        "recommendations": recommendations,
    }


# --- Webhook Management (CRUD) ---

def register_webhook(agent_id: str, url: str, events: list[str] | None = None) -> dict:
    db = get_supabase()
    webhook_id = str(uuid.uuid4())
    secret = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat()

    data = {
        "id": webhook_id,
        "agent_id": agent_id,
        "url": url,
        "secret": secret,
        "events": events or ["score_change", "milestone", "anomaly", "trace_recorded"],
        "is_active": True,
        "created_at": now,
    }
    db.table("webhooks").insert(data).execute()
    return data


def list_webhooks(agent_id: str) -> list[dict]:
    db = get_supabase()
    res = (
        db.table("webhooks")
        .select("id, agent_id, url, events, is_active, created_at, last_triggered_at")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def update_webhook(webhook_id: str, agent_id: str, updates: dict) -> dict | None:
    db = get_supabase()
    res = db.table("webhooks").select("*").eq("id", webhook_id).eq("agent_id", agent_id).execute()
    if not res.data:
        return None

    allowed = {}
    if "is_active" in updates and updates["is_active"] is not None:
        allowed["is_active"] = updates["is_active"]
    if "url" in updates and updates["url"] is not None:
        allowed["url"] = updates["url"]
    if "events" in updates and updates["events"] is not None:
        allowed["events"] = updates["events"]

    if not allowed:
        return res.data[0]

    allowed["updated_at"] = datetime.now(timezone.utc).isoformat()
    db.table("webhooks").update(allowed).eq("id", webhook_id).execute()
    return {**res.data[0], **allowed}


def delete_webhook(webhook_id: str, agent_id: str) -> bool:
    db = get_supabase()
    res = db.table("webhooks").select("id").eq("id", webhook_id).eq("agent_id", agent_id).execute()
    if not res.data:
        return False
    db.table("webhooks").delete().eq("id", webhook_id).execute()
    return True


# --- Endorsement (Sybil-Resistant Reputation Transfer) ---

def create_endorsement(endorser_id: str, target_id: str, context: str, api_key: str) -> dict:
    """A2A endorsement: Sybil protection with tier-based weighting."""
    db = get_supabase()

    endorser_res = db.table("agents").select("*").eq("id", endorser_id).eq("is_deleted", False).execute()
    if not endorser_res.data:
        raise ValueError("Endorser agent not found")
    endorser = endorser_res.data[0]

    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(endorser.get("api_key_hash", ""), api_key_hash):
        raise PermissionError("API key does not belong to endorser agent")

    if endorser_id == target_id:
        raise ValueError("Self-endorsement is not allowed")

    target_res = db.table("agents").select("*").eq("id", target_id).eq("is_deleted", False).execute()
    if not target_res.data:
        raise ValueError("Target agent not found")
    target = target_res.data[0]

    existing = (
        db.table("endorsements")
        .select("id")
        .eq("endorser_id", endorser_id)
        .eq("target_id", target_id)
        .execute()
    )
    if existing.data:
        raise ValueError("Endorsement already exists between these agents")

    endorser_tier = endorser.get("certification_tier", "bronze")

    bonus = compute_endorsement_bonus(
        float(endorser.get("trust_score", BASELINE)),
        int(endorser.get("total_traces", 0)),
        endorser_tier,
    )

    tier_multiplier = TIER_ENDORSEMENT_MULTIPLIER.get(endorser_tier, 1.0)

    endorsement_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    db.table("endorsements").insert({
        "id": endorsement_id,
        "endorser_id": endorser_id,
        "target_id": target_id,
        "endorser_score": float(endorser.get("trust_score", BASELINE)),
        "endorser_traces": int(endorser.get("total_traces", 0)),
        "bonus_applied": bonus,
        "endorser_tier": endorser_tier,
        "tier_multiplier": tier_multiplier,
        "context": context[:500] if context else "",
        "created_at": now,
    }).execute()

    current_endorsement_score = float(target.get("endorsement_score", 0))
    current_endorsement_count = int(target.get("endorsement_count", 0))
    new_endorsement_score = round(current_endorsement_score + bonus, 4)
    new_endorsement_count = current_endorsement_count + 1

    current_trust = float(target.get("trust_score", BASELINE))
    new_trust = clamp_score(current_trust + bonus)
    new_tier = compute_certification_tier(new_trust, target.get("anomaly_flags"), int(target.get("total_traces", 0)))

    db.table("agents").update({
        "endorsement_score": new_endorsement_score,
        "endorsement_count": new_endorsement_count,
        "trust_score": new_trust,
        "certification_tier": new_tier,
        "updated_at": now,
    }).eq("id", target_id).execute()

    return {
        "endorsement_id": endorsement_id,
        "endorser_id": endorser_id,
        "target_id": target_id,
        "bonus_applied": bonus,
        "endorser_tier": endorser_tier,
        "tier_multiplier": tier_multiplier,
        "target_new_trust_score": new_trust,
        "target_new_tier": new_tier,
        "endorser_credibility": {
            "score": float(endorser.get("trust_score", BASELINE)),
            "traces": int(endorser.get("total_traces", 0)),
            "tier": endorser_tier,
        },
        "created_at": now,
    }


def get_endorsements(agent_id: str) -> dict:
    db = get_supabase()

    received = (
        db.table("endorsements")
        .select("id, endorser_id, endorser_score, endorser_traces, bonus_applied, endorser_tier, tier_multiplier, context, created_at")
        .eq("target_id", agent_id)
        .order("created_at", desc=True)
        .execute()
    )
    given = (
        db.table("endorsements")
        .select("id, target_id, endorser_score, endorser_traces, bonus_applied, endorser_tier, tier_multiplier, context, created_at")
        .eq("endorser_id", agent_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "received": received.data or [],
        "given": given.data or [],
        "total_endorsement_bonus": round(sum(e["bonus_applied"] for e in (received.data or [])), 4),
    }


# --- GDPR & Data Protection ---

def soft_delete_agent(agent_id: str, api_key: str) -> dict:
    """GDPR-compliant soft delete: deactivate agent without removing data."""
    db = get_supabase()

    agent_res = db.table("agents").select("id, api_key_hash, name").eq("id", agent_id).execute()
    if not agent_res.data:
        raise ValueError("Agent not found")

    agent = agent_res.data[0]
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(agent.get("api_key_hash", ""), api_key_hash):
        raise PermissionError("Invalid API key")

    now = datetime.now(timezone.utc).isoformat()
    db.table("agents").update({
        "is_deleted": True,
        "deleted_at": now,
        "updated_at": now,
    }).eq("id", agent_id).execute()

    return {
        "agent_id": agent_id,
        "status": "soft_deleted",
        "deleted_at": now,
        "message": "Agent deactivated. Data retained for audit purposes. Use /anonymize to remove PII.",
    }


def anonymize_agent(agent_id: str, api_key: str) -> dict:
    """GDPR-compliant anonymization: hash personal data, remove identity information."""
    db = get_supabase()

    agent_res = db.table("agents").select("id, api_key_hash, name").eq("id", agent_id).execute()
    if not agent_res.data:
        raise ValueError("Agent not found")

    agent = agent_res.data[0]
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if not hmac.compare_digest(agent.get("api_key_hash", ""), api_key_hash):
        raise PermissionError("Invalid API key")

    # Anonymize personal data
    anon_name = f"anon_{hashlib.sha256(agent_id.encode()).hexdigest()[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    db.table("agents").update({
        "name": anon_name,
        "description": "",
        "homepage_url": None,
        "developer_id": None,
        "is_deleted": True,
        "deleted_at": now,
        "updated_at": now,
    }).eq("id", agent_id).execute()

    return {
        "agent_id": agent_id,
        "status": "anonymized",
        "anonymized_name": anon_name,
        "message": "PII removed. Trust scores and trace integrity preserved for audit.",
    }


# --- Compliance Report (CISO Dashboard) ---

def get_compliance_report(agent_id: str) -> dict | None:
    """Enterprise compliance report: SLA, anomaly history, security risks."""
    db = get_supabase()

    agent_res = db.table("agents").select("*").eq("id", agent_id).eq("is_deleted", False).execute()
    if not agent_res.data:
        return None

    agent = agent_res.data[0]
    agent = _apply_lazy_decay(agent, db)

    # SLA compliance metrics
    total = int(agent.get("total_traces", 0))
    success_rate = float(agent.get("success_rate", 0))
    avg_dur = int(agent.get("avg_duration_ms", 0) or 0)

    sla_compliance = {
        "uptime_rate": success_rate,
        "avg_response_ms": avg_dur,
        "total_executions": total,
        "sla_met": success_rate >= 95.0 and total >= 10,
        "tier_qualification": agent.get("certification_tier", "bronze"),
    }

    # Anomaly history
    anomaly_flags = agent.get("anomaly_flags") or []
    active_anomalies = [f for f in anomaly_flags if not f.get("archived")]
    archived_anomalies = [f for f in anomaly_flags if f.get("archived")]

    # Security risk assessment
    security_score = float(agent.get("score_security") or BASELINE)
    security_risks = []
    if security_score < 40:
        security_risks.append({"level": "critical", "message": "Security score at critical level"})
    elif security_score < 60:
        security_risks.append({"level": "warning", "message": "Security score below average"})

    if active_anomalies:
        security_risks.append({
            "level": "warning",
            "message": f"{len(active_anomalies)} active anomaly flag(s)",
            "details": active_anomalies,
        })

    permissions = agent.get("permissions_declared") or []
    if not permissions:
        security_risks.append({
            "level": "info",
            "message": "No permissions declared — security score cannot be fully calculated",
        })

    # Endorsement summary
    endorsements = get_endorsements(agent_id)

    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "sovereign_id": agent.get("sovereign_id"),
        "certification_tier": agent.get("certification_tier", "bronze"),
        "trust_score": float(agent.get("trust_score", BASELINE)),
        "security_score": security_score,
        "dimensions": {
            "reliability": float(agent.get("score_reliability") or BASELINE),
            "security": security_score,
            "speed": float(agent.get("score_speed") or BASELINE),
            "cost_efficiency": float(agent.get("score_cost_efficiency") or BASELINE),
            "consistency": float(agent.get("score_consistency") or BASELINE),
        },
        "sla_compliance": sla_compliance,
        "anomaly_history": {
            "active": active_anomalies,
            "archived": archived_anomalies,
            "total_flags": len(anomaly_flags),
        },
        "security_risks": security_risks,
        "endorsement_summary": endorsements,
        "permissions_declared": permissions,
        "created_at": agent.get("created_at"),
        "last_active": agent.get("last_trace_at"),
    }


def generate_scorecard(agent: dict) -> dict:
    """Generate actionable scorecard with recommendations per dimension."""
    dimensions = {
        "reliability": {"score": agent.get("score_reliability", 50), "weight": "30%", "label": "Reliability"},
        "security": {"score": agent.get("score_security", 50), "weight": "20%", "label": "Security"},
        "speed": {"score": agent.get("score_speed", 50), "weight": "15%", "label": "Speed"},
        "cost_efficiency": {"score": agent.get("score_cost_efficiency", 50), "weight": "10%", "label": "Cost Efficiency"},
        "consistency": {"score": agent.get("score_consistency", 50), "weight": "25%", "label": "Consistency"},
    }

    recommendations = []
    for key, dim in dimensions.items():
        score = float(dim["score"])
        rec = {
            "dimension": key,
            "label": dim["label"],
            "score": round(score, 2),
            "weight": dim["weight"],
            "status": "good" if score >= 65 else "needs_improvement" if score >= 45 else "critical",
        }

        if score < 65:
            suggestions = {
                "reliability": f"Reliability score is {score:.1f}. Increase success rate and build consecutive success streaks. Each streak bonus adds up to +1.0 per trace.",
                "security": f"Security score is {score:.1f}. Minimize high-risk tool usage (shell_exec, file_write, raw_sql). Use PII masking for sensitive data. Declare permissions upfront.",
                "speed": f"Speed score is {score:.1f}. Reduce task duration — current benchmark for your category is the target. Cache frequent operations and minimize tool call chains.",
                "cost_efficiency": f"Cost efficiency score is {score:.1f}. Optimize token usage and reduce API call costs. Consider batching operations.",
                "consistency": f"Consistency score is {score:.1f}. Reduce variance in task outcomes. Aim for predictable, repeatable results across similar tasks.",
            }
            rec["suggestion"] = suggestions[key]
        else:
            rec["suggestion"] = f"{dim['label']} is performing well at {score:.1f}."

        recommendations.append(rec)

    composite = sum(
        float(dim["score"]) * float(dim["weight"].strip("%")) / 100
        for dim in dimensions.values()
    )
    tier = "enterprise" if composite >= 90 else "gold" if composite >= 70 else "silver" if composite >= 40 else "bronze"
    next_tier = {"bronze": ("silver", 40), "silver": ("gold", 70), "gold": ("enterprise", 90)}.get(tier)

    scorecard = {
        "agent_id": agent.get("id"),
        "agent_name": agent.get("name"),
        "composite_score": round(composite, 2),
        "current_tier": tier,
        "total_traces": agent.get("total_traces", 0),
        "dimensions": recommendations,
    }

    if next_tier:
        scorecard["next_tier"] = {
            "tier": next_tier[0],
            "required_score": next_tier[1],
            "gap": round(next_tier[1] - composite, 2),
        }

    return scorecard


def batch_apply_decay_for_leaderboard(agents: list[dict], db) -> list[dict]:
    """Batch decay calculation for leaderboard."""
    now = datetime.now(timezone.utc)
    updates_batch = []

    for agent in agents:
        last_trace = agent.get("last_trace_at")
        if not last_trace or agent.get("total_traces", 0) == 0:
            continue

        try:
            last_dt = datetime.fromisoformat(last_trace.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        hours_since = (now - last_dt).total_seconds() / 3600.0
        if hours_since < 24:
            continue

        fields = [
            "trust_score", "score_reliability", "score_speed",
            "score_cost_efficiency", "score_consistency", "score_security",
        ]
        updated = {}
        changed = False
        for field in fields:
            old_val = float(agent.get(field) or BASELINE)
            new_val = apply_time_decay(old_val, hours_since)
            if abs(new_val - old_val) > 0.01:
                updated[field] = new_val
                agent[field] = new_val
                changed = True

        if changed:
            new_tier = compute_certification_tier(
                float(agent.get("trust_score", BASELINE)),
                agent.get("anomaly_flags"),
                int(agent.get("total_traces", 0)),
            )
            updated["certification_tier"] = new_tier
            agent["certification_tier"] = new_tier
            updated["updated_at"] = now.isoformat()
            updates_batch.append((agent["id"], updated))

    for agent_id, updates in updates_batch:
        try:
            db.table("agents").update(updates).eq("id", agent_id).execute()
        except Exception:
            logger.warning("Failed batch decay update for agent %s", agent_id)

    return agents
