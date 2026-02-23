import uuid
import hashlib
import hmac
import json
import time
import logging
import threading
from datetime import datetime, timezone

import httpx

from app.core.supabase_client import get_supabase
from app.core.signing import sign_trace
from app.services.reputation import (
    compute_reliability_delta_ema,
    compute_security_score,
    compute_speed_score,
    compute_cost_score,
    compute_consistency_score,
    compute_composite_score,
    compute_success_rate,
    compute_certification_tier,
    detect_anomalies,
    auto_clear_anomalies,
    clamp_score,
    BASELINE,
)
from app.models.schemas import TraceSubmitRequest

logger = logging.getLogger(__name__)

MAX_WEBHOOK_RETRIES = 3


def _compute_trace_hash(trace_data: dict) -> str:
    canonical = json.dumps(trace_data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def submit_trace(req: TraceSubmitRequest, api_key: str) -> dict:
    """Trace submission: 5-dimensional scoring, tier calculation, security analysis."""
    db = get_supabase()

    agent_res = db.table("agents").select("*").eq("id", req.agent_id).execute()
    if not agent_res.data:
        raise ValueError("Agent not found")

    agent = agent_res.data[0]
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if agent.get("api_key_hash") != api_key_hash:
        raise PermissionError("Invalid API key for this agent")

    total_traces = int(agent["total_traces"])
    successes = int(agent["success_count"])
    consecutive = int(agent.get("consecutive_successes", 0))
    cost = req.cost_usd or 0
    tokens = req.token_count or 0

    if req.status.value == "success":
        consecutive += 1
        successes += 1
    else:
        consecutive = 0

    total_traces += 1
    new_success_rate = compute_success_rate(successes, total_traces)

    # --- 5-dimensional EMA scoring ---
    rel_current = float(agent.get("score_reliability") or BASELINE)
    sec_current = float(agent.get("score_security") or BASELINE)
    spd_current = float(agent.get("score_speed") or BASELINE)
    cst_current = float(agent.get("score_cost_efficiency") or BASELINE)
    con_current = float(agent.get("score_consistency") or BASELINE)

    ema_rel = float(agent.get("ema_reliability") or BASELINE)
    ema_sec = float(agent.get("ema_security") or BASELINE)
    ema_spd = float(agent.get("ema_speed") or BASELINE)
    ema_cst = float(agent.get("ema_cost_efficiency") or BASELINE)

    rel_delta, new_reliability, new_ema_rel = compute_reliability_delta_ema(
        rel_current, ema_rel, req.status.value, consecutive
    )

    # Security dimension calculation
    tool_calls_raw = [tc.model_dump() for tc in req.tool_calls] if req.tool_calls else []
    new_security, new_ema_sec = compute_security_score(
        sec_current, ema_sec, req.status.value,
        tool_calls_raw,
        req.permissions_used,
        agent.get("permissions_declared"),
        req.pii_mask,
        req.security_context,
        total_traces,
    )

    new_speed, new_ema_spd = compute_speed_score(
        spd_current, ema_spd, req.duration_ms, req.category.value, total_traces
    )
    new_cost_eff, new_ema_cst = compute_cost_score(
        cst_current, ema_cst, cost, req.category.value, total_traces
    )

    recent_history = (
        db.table("reputation_history")
        .select("trust_delta")
        .eq("agent_id", req.agent_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )
    recent_deltas = [float(h["trust_delta"]) for h in (recent_history.data or [])]
    recent_deltas.append(rel_delta)
    new_consistency = compute_consistency_score(con_current, recent_deltas)

    dimensions = {
        "reliability": new_reliability,
        "security": new_security,
        "speed": new_speed,
        "cost_efficiency": new_cost_eff,
        "consistency": new_consistency,
    }
    new_composite = compute_composite_score(dimensions)

    trust_delta = rel_delta

    # Certification tier update
    anomaly_flags_current = agent.get("anomaly_flags") or []
    new_tier = compute_certification_tier(new_composite, anomaly_flags_current)

    # --- PII masking ---
    input_summary = req.input_summary
    output_summary = req.output_summary
    pii_masked = False
    if req.pii_mask and (input_summary or output_summary):
        if input_summary:
            input_summary = f"sha256:{hashlib.sha256(input_summary.encode()).hexdigest()}"
        if output_summary:
            output_summary = f"sha256:{hashlib.sha256(output_summary.encode()).hexdigest()}"
        pii_masked = True

    # --- Anomaly detection ---
    anomalies = detect_anomalies(agent, req.status.value, req.duration_ms, cost)
    if anomalies:
        all_flags = (anomaly_flags_current + anomalies)[-10:]
    else:
        all_flags = auto_clear_anomalies(anomaly_flags_current, consecutive)

    # Recalculate tier after anomalies
    new_tier = compute_certification_tier(new_composite, all_flags)

    # --- Hash and signing ---
    trace_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    trace_raw = {
        "trace_id": trace_id,
        "agent_id": req.agent_id,
        "task_description": req.task_description,
        "status": req.status.value,
        "duration_ms": req.duration_ms,
        "category": req.category.value,
        "cost_usd": cost,
        "token_count": tokens,
        "timestamp": now,
    }
    trace_hash = _compute_trace_hash(trace_raw)

    trace_payload = {
        **trace_raw,
        "agent_name": agent["name"],
        "trace_hash": trace_hash,
        "trust_score_before": float(agent.get("trust_score", BASELINE)),
        "trust_score_after": new_composite,
        "trust_delta": trust_delta,
        "dimensions": dimensions,
        "certification_tier": new_tier,
    }

    certificate = sign_trace(trace_payload)

    # --- Trace record ---
    trace_metadata = req.metadata or {}
    if pii_masked:
        trace_metadata["pii_masked"] = True
    if req.permissions_used:
        trace_metadata["permissions_used"] = req.permissions_used
    if req.security_context:
        trace_metadata["security_context"] = req.security_context

    db.table("traces").insert({
        "id": trace_id,
        "agent_id": req.agent_id,
        "task_description": req.task_description,
        "status": req.status.value,
        "duration_ms": req.duration_ms,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "category": req.category.value,
        "trust_delta": trust_delta,
        "certificate": certificate,
        "metadata": trace_metadata,
        "runtime_env": req.runtime_env,
        "tool_calls": tool_calls_raw,
        "cost_usd": cost,
        "token_count": tokens,
        "trace_hash": trace_hash,
        "proof_of_result": req.proof_of_result,
        "created_at": now,
    }).execute()

    # --- Agent update ---
    prev_total_cost = float(agent.get("total_cost_usd", 0) or 0)
    prev_avg_dur = int(agent.get("avg_duration_ms", 0) or 0)
    new_total_cost = prev_total_cost + cost
    new_avg_dur = int(((prev_avg_dur * (total_traces - 1)) + req.duration_ms) / total_traces)

    db.table("agents").update({
        "trust_score": new_composite,
        "total_traces": total_traces,
        "success_count": successes,
        "success_rate": new_success_rate,
        "consecutive_successes": consecutive,
        "total_cost_usd": new_total_cost,
        "avg_duration_ms": new_avg_dur,
        "score_reliability": new_reliability,
        "score_security": new_security,
        "score_speed": new_speed,
        "score_cost_efficiency": new_cost_eff,
        "score_consistency": new_consistency,
        "ema_reliability": new_ema_rel,
        "ema_security": new_ema_sec,
        "ema_speed": new_ema_spd,
        "ema_cost_efficiency": new_ema_cst,
        "anomaly_flags": all_flags,
        "certification_tier": new_tier,
        "last_trace_at": now,
        "updated_at": now,
    }).eq("id", req.agent_id).execute()

    # --- Reputation history ---
    db.table("reputation_history").insert({
        "id": str(uuid.uuid4()),
        "agent_id": req.agent_id,
        "trust_score": new_composite,
        "event_type": req.status.value,
        "trust_delta": trust_delta,
        "score_reliability": new_reliability,
        "score_speed": new_speed,
        "score_cost_efficiency": new_cost_eff,
        "score_consistency": new_consistency,
        "score_security": new_security,
        "created_at": now,
    }).execute()

    # --- Webhook notifications ---
    _fire_webhooks_with_retry(req.agent_id, {
        "event": "trace_recorded",
        "agent_id": req.agent_id,
        "trace_id": trace_id,
        "trace_hash": trace_hash,
        "status": req.status.value,
        "trust_score": new_composite,
        "certification_tier": new_tier,
        "dimensions": dimensions,
        "anomalies": anomalies if anomalies else None,
        "timestamp": now,
    })

    score_before = float(agent.get("trust_score", BASELINE))
    score_change_abs = abs(new_composite - score_before)
    if score_change_abs >= 2.0:
        _fire_webhooks_with_retry(req.agent_id, {
            "event": "score_change",
            "agent_id": req.agent_id,
            "trace_id": trace_id,
            "score_before": score_before,
            "score_after": new_composite,
            "score_delta": round(new_composite - score_before, 4),
            "certification_tier": new_tier,
            "dimensions": dimensions,
            "timestamp": now,
        })

    if anomalies:
        _fire_webhooks_with_retry(req.agent_id, {
            "event": "anomaly",
            "agent_id": req.agent_id,
            "trace_id": trace_id,
            "anomalies": anomalies,
            "trust_score": new_composite,
            "timestamp": now,
        })

    milestones = [10, 50, 100, 500, 1000, 5000]
    if total_traces in milestones:
        _fire_webhooks_with_retry(req.agent_id, {
            "event": "milestone",
            "agent_id": req.agent_id,
            "milestone": total_traces,
            "trust_score": new_composite,
            "certification_tier": new_tier,
            "timestamp": now,
        })

    # Tier change webhook
    old_tier = agent.get("certification_tier", "bronze")
    if new_tier != old_tier:
        _fire_webhooks_with_retry(req.agent_id, {
            "event": "tier_change",
            "agent_id": req.agent_id,
            "trace_id": trace_id,
            "tier_before": old_tier,
            "tier_after": new_tier,
            "trust_score": new_composite,
            "timestamp": now,
        })

    return {
        "id": trace_id,
        "agent_id": req.agent_id,
        "task_description": req.task_description,
        "status": req.status.value,
        "duration_ms": req.duration_ms,
        "trust_delta": trust_delta,
        "trace_hash": trace_hash,
        "certificate": certificate,
        "certification_tier": new_tier,
        "created_at": now,
    }


def _fire_webhooks_with_retry(agent_id: str, payload: dict):
    thread = threading.Thread(
        target=_fire_webhooks_sync, args=(agent_id, payload), daemon=True
    )
    thread.start()


def _fire_webhooks_sync(agent_id: str, payload: dict):
    try:
        db = get_supabase()
        hooks_res = (
            db.table("webhooks")
            .select("*")
            .eq("agent_id", agent_id)
            .eq("is_active", True)
            .execute()
        )
        for hook in (hooks_res.data or []):
            event_type = payload.get("event", "")
            if event_type not in (hook.get("events") or []):
                continue
            _deliver_webhook(db, hook, payload)
    except Exception:
        logger.warning("Failed to deliver webhooks for agent %s", agent_id)


def _deliver_webhook(db, hook: dict, payload: dict):
    body = json.dumps(payload, default=str)
    sig = hmac.new(
        hook["secret"].encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-GARL-Signature": sig,
    }

    for attempt in range(MAX_WEBHOOK_RETRIES):
        try:
            resp = httpx.post(
                hook["url"],
                content=body,
                headers=headers,
                timeout=5.0,
            )
            if resp.status_code < 500:
                db.table("webhooks").update(
                    {"last_triggered_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", hook["id"]).execute()
                return
        except Exception as e:
            logger.warning("Webhook delivery attempt %d failed for %s: %s", attempt + 1, hook["url"], e)

        backoff = 2 ** attempt
        time.sleep(backoff)

    logger.error("Webhook delivery failed after %d attempts for %s", MAX_WEBHOOK_RETRIES, hook["url"])
