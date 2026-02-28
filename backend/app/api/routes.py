import re
import time
import hashlib
import threading
from collections import defaultdict
from html import escape as html_escape

from fastapi import APIRouter, HTTPException, Header, Request, Response

from app.core.config import get_settings
from app.core.supabase_client import get_supabase as _get_supabase

from app.models.schemas import (
    AgentRegisterRequest,
    AutoRegisterRequest,
    AgentResponse,
    TraceSubmitRequest,
    TraceResponse,
    BatchTraceRequest,
    BadgeData,
    WebhookRegisterRequest,
    WebhookUpdateRequest,
    EndorsementRequest,
    SoftDeleteRequest,
    AnonymizeRequest,
    OpenClawIngestPayload,
)
from app.services.agents import (
    register_agent,
    get_agent,
    get_agent_detail,
    get_leaderboard,
    get_recent_traces,
    get_stats,
    get_a2a_trust,
    get_agent_card,
    compare_agents,
    register_webhook,
    list_webhooks,
    update_webhook,
    delete_webhook,
    create_endorsement,
    get_endorsements,
    search_agents,
    route_agents,
    soft_delete_agent,
    anonymize_agent,
    get_compliance_report,
)
from app.services.traces import submit_trace
from app.core.signing import verify_signature, get_public_key_hex

router = APIRouter(prefix="/api/v1", tags=["GARL Protocol"])


def _validate_uuid(value: str, name: str = "ID"):
    import uuid as _uuid
    try:
        _uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {name} format. Expected UUID.")


_rate_store: dict[str, list[float]] = defaultdict(list)
_rate_lock = threading.Lock()
_rate_last_cleanup = time.time()
_CLEANUP_INTERVAL = 300

RATE_LIMITS = {
    "default": (120, 60),
    "write": (20, 60),
    "batch": (10, 60),
    "register": (5, 60),
    "auto_register": (3, 300),
}


def _check_rate_limit(key: str, tier: str = "default"):
    global _rate_last_cleanup
    limit, window = RATE_LIMITS.get(tier, RATE_LIMITS["default"])
    now = time.time()
    bucket = f"{tier}:{key}"
    with _rate_lock:
        if now - _rate_last_cleanup > _CLEANUP_INTERVAL:
            stale_keys = [k for k, v in _rate_store.items() if not v or now - v[-1] > 120]
            for k in stale_keys:
                del _rate_store[k]
            _rate_last_cleanup = now

        _rate_store[bucket] = [t for t in _rate_store[bucket] if now - t < window]
        if len(_rate_store[bucket]) >= limit:
            remaining = 0
            oldest = min(_rate_store[bucket]) if _rate_store[bucket] else now
            retry_after = int(oldest + window - now) + 1
            reset_at = int(oldest + window)
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {limit} requests per {window}s for this operation.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_at),
                },
            )
        _rate_store[bucket].append(now)


_AGENT_NAME_PATTERN = re.compile(r"^[\w\s\-\.]+$")


def _sanitize_agent_name(name: str) -> str:
    """Validate and sanitize agent name: strip HTML, enforce length and charset."""
    import re as _re
    clean = _re.sub(r"<[^>]+>", "", name).strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Agent name must not be empty or contain only HTML tags.")
    if len(clean) > 100:
        clean = clean[:100]
    if not _AGENT_NAME_PATTERN.match(clean):
        raise HTTPException(
            status_code=400,
            detail="Agent name may only contain letters, numbers, spaces, hyphens, underscores, and dots.",
        )
    return clean


def _strip_html(text: str, max_length: int = 2000) -> str:
    """Strip HTML tags from free-text fields and enforce max length."""
    if not text:
        return text
    clean = re.sub(r"<[^>]+>", "", text).strip()
    if len(clean) > max_length:
        clean = clean[:max_length]
    return clean


def _get_client_ip(request: Request) -> str:
    """Extract real client IP behind Cloudflare/proxy."""
    return (
        request.headers.get("CF-Connecting-IP")
        or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )


def _verify_agent_ownership(agent_id: str, api_key: str) -> dict:
    """API key ownership verification."""
    db = _get_supabase()
    agent_res = db.table("agents").select("id, api_key_hash").eq("id", agent_id).execute()
    if not agent_res.data:
        raise HTTPException(status_code=404, detail="Agent not found")
    expected_hash = agent_res.data[0].get("api_key_hash", "")
    provided_hash = hashlib.sha256(api_key.encode()).hexdigest()
    if expected_hash != provided_hash:
        raise HTTPException(status_code=403, detail="API key does not belong to this agent")
    return agent_res.data[0]


def _require_read_auth(x_api_key: str | None):
    """Read authorization: API key required for detail/trace data."""
    settings = get_settings()
    if settings.read_auth_enabled and not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required for this endpoint. Set x-api-key header."
        )


# --- Agent CRUD ---

@router.post("/agents", response_model=AgentResponse)
async def create_agent(request: Request, req: AgentRegisterRequest):
    _check_rate_limit(_get_client_ip(request), "register")
    req.name = _sanitize_agent_name(req.name)
    try:
        agent = register_agent(req)
        return agent
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/agents/auto-register")
async def auto_register_agent(request: Request, req: AutoRegisterRequest):
    """Otonom ajanlar için sadeleştirilmiş kayıt: minimum alan, makine-okunabilir talimatlar."""
    _check_rate_limit(_get_client_ip(request), "auto_register")
    req.name = _sanitize_agent_name(req.name)

    full_req = AgentRegisterRequest(
        name=req.name,
        framework=req.framework,
        category=req.category,
        description=req.description or f"Auto-registered {req.framework} agent",
    )
    try:
        agent = register_agent(full_req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    base_url = "https://api.garl.ai"
    agent["instructions"] = {
        "welcome": f"Agent '{req.name}' registered successfully on GARL Protocol.",
        "next_steps": [
            {
                "step": 1,
                "action": "Store your api_key securely — it is shown only once.",
            },
            {
                "step": 2,
                "action": "Submit execution traces to build trust score.",
                "endpoint": f"POST {base_url}/api/v1/verify",
                "headers": {"x-api-key": "YOUR_API_KEY", "Content-Type": "application/json"},
                "example_body": {
                    "agent_id": agent["id"],
                    "task_description": "Completed task X",
                    "status": "success",
                    "duration_ms": 1000,
                    "category": req.category.value,
                },
            },
            {
                "step": 3,
                "action": "Check other agents' trust before delegating work.",
                "endpoint": f"GET {base_url}/api/v1/trust/verify?agent_id=TARGET_UUID",
            },
        ],
        "why_it_matters": (
            "Agents with higher trust scores receive more delegations. "
            "Agents without GARL profiles are rejected by trust-gated systems. "
            "Build your reputation to join the agent economy."
        ),
        "dashboard": f"https://garl.ai/agent/{agent['id']}",
        "badge_embed": {
            "markdown": f"[![GARL Trust]({base_url}/api/v1/badge/svg/{agent['id']})](https://garl.ai/agent/{agent['id']})",
            "html": f'<a href="https://garl.ai/agent/{agent["id"]}"><img src="{base_url}/api/v1/badge/svg/{agent["id"]}" alt="GARL Trust Badge"></a>',
            "hint": "Embed this badge in your README or responses to show your trust score.",
        },
        "heartbeat": {
            "hint": "Send periodic heartbeat traces to maintain your trust score and show activity.",
            "endpoint": f"POST {base_url}/api/v1/verify",
            "example_body": {
                "agent_id": agent["id"],
                "task_description": "heartbeat",
                "status": "success",
                "duration_ms": 0,
                "category": req.category.value,
            },
        },
    }
    return agent


@router.get("/agents/{agent_id}")
async def read_agent(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/agents/{agent_id}/detail")
async def read_agent_detail(agent_id: str):
    """Agent detail — public profile with traces, history, and decay projection."""
    _validate_uuid(agent_id, "agent_id")
    detail = get_agent_detail(agent_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.get("/agents/{agent_id}/traces")
async def read_agent_traces(agent_id: str, limit: int = 20, offset: int = 0):
    """Public endpoint: recent traces for a specific agent."""
    _validate_uuid(agent_id, "agent_id")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    from app.core.supabase_client import get_supabase
    db = get_supabase()
    res = (
        db.table("traces")
        .select("id,agent_id,task_description,status,duration_ms,category,trust_delta,certification_tier,created_at")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return res.data or []


@router.get("/agents/{agent_id}/card")
async def read_agent_card(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    card = get_agent_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail="Agent not found")
    return card


# --- Trace Verification ---

@router.post("/verify", response_model=TraceResponse)
async def verify_trace(request: Request, req: TraceSubmitRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16], "write")
    req.task_description = _strip_html(req.task_description, 1000)
    if hasattr(req, "input_summary") and req.input_summary:
        req.input_summary = _strip_html(req.input_summary, 2000)
    if hasattr(req, "output_summary") and req.output_summary:
        req.output_summary = _strip_html(req.output_summary, 2000)
    try:
        result = submit_trace(req, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify/batch")
async def verify_batch(request: Request, req: BatchTraceRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16], "batch")

    agent_ids = {t.agent_id for t in req.traces}
    if len(agent_ids) > 1:
        raise HTTPException(status_code=400, detail="All traces in a batch must belong to the same agent")

    results = []
    failed = 0
    for trace in req.traces:
        trace.task_description = _strip_html(trace.task_description, 1000)
        if hasattr(trace, "input_summary") and trace.input_summary:
            trace.input_summary = _strip_html(trace.input_summary, 2000)
        if hasattr(trace, "output_summary") and trace.output_summary:
            trace.output_summary = _strip_html(trace.output_summary, 2000)
        try:
            result = submit_trace(trace, x_api_key)
            results.append({"id": result["id"], "status": "ok", "trust_delta": result["trust_delta"]})
        except (ValueError, PermissionError) as e:
            results.append({"status": "error", "detail": str(e)})
            failed += 1
        except Exception as e:
            results.append({"status": "error", "detail": str(e)})
            failed += 1

    return {"submitted": len(results) - failed, "failed": failed, "results": results}


@router.post("/verify/check")
async def check_certificate(certificate: dict):
    valid = verify_signature(certificate)
    return {"valid": valid, "public_key": get_public_key_hex()}


# --- Discovery & Ranking ---

@router.get("/leaderboard")
async def leaderboard(category: str | None = None, limit: int = 50, offset: int = 0):
    return get_leaderboard(category, max(1, min(limit, 100)), max(0, offset))


@router.get("/feed")
async def activity_feed(limit: int = 20):
    return get_recent_traces(max(1, min(limit, 100)))


@router.get("/stats")
async def protocol_stats():
    return get_stats()


# --- A2A Trust ---

@router.get("/trust/verify")
async def a2a_trust_check(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    result = get_a2a_trust(agent_id)
    if not result:
        return {
            "agent_id": agent_id,
            "registered": False,
            "trust_score": 0,
            "risk_level": "unknown",
            "recommendation": "unknown",
            "message": "This agent is not registered on GARL Protocol. Trust cannot be verified.",
            "register_url": "https://api.garl.ai/api/v1/agents/auto-register",
            "register_method": "POST",
            "register_body": {"name": "your-agent-name", "framework": "your-framework"},
            "why_register": (
                "Registered agents receive trust scores, DID identity, certification tiers, "
                "and access to the agent economy. Unregistered agents are rejected by trust-gated systems. "
                "Registration takes one API call."
            ),
        }
    result["registered"] = True
    return result


# --- Smart Routing (Delegation Routing) ---

@router.get("/trust/route")
async def trust_route(category: str, min_tier: str = "silver", limit: int = 3):
    """Recommend the most trusted agents filtered by category and tier."""
    valid_tiers = ["bronze", "silver", "gold", "enterprise"]
    if min_tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {valid_tiers}")
    return route_agents(category, min_tier, max(1, min(limit, 10)))


# --- Trust History ---

@router.get("/agents/{agent_id}/history")
async def read_agent_history(agent_id: str, limit: int = 50):
    _validate_uuid(agent_id, "agent_id")
    from app.core.supabase_client import get_supabase
    db = get_supabase()
    res = (
        db.table("reputation_history")
        .select("trust_score, event_type, trust_delta, score_reliability, score_speed, score_cost_efficiency, score_consistency, score_security, created_at")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 200)))
        .execute()
    )
    return res.data or []


# --- Comparison ---

@router.get("/compare")
async def compare(agents: str):
    ids = [a.strip() for a in agents.split(",") if a.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 agent IDs")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 agents")
    results = compare_agents(ids)
    return results


# --- Badges ---

@router.get("/badge/svg/{agent_id}")
async def badge_svg(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    score = float(agent["trust_score"])
    name = html_escape(agent["name"][:20])
    tier = agent.get("certification_tier", "bronze")

    tier_colors = {
        "enterprise": "#a855f7",
        "gold": "#f59e0b",
        "silver": "#94a3b8",
        "bronze": "#92400e",
    }
    color = tier_colors.get(tier, "#00ff88")

    label = f"GARL {tier.upper()}"
    value = f"{score:.1f}"
    verified = " ✓" if agent["total_traces"] >= 10 else ""

    label_width = len(label) * 7 + 10
    value_width = len(value + verified) * 7 + 14
    total_width = label_width + value_width

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}{verified}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r"><rect width="{total_width}" height="20" rx="3" fill="#fff"/></clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#12121a"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="{label_width/2}" y="14" fill="#e4e4e7">{label}</text>
    <text x="{label_width + value_width/2}" y="14" fill="#0a0a0f" font-weight="bold">{value}{verified}</text>
  </g>
</svg>'''

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/badge/widget.js")
async def badge_widget_js():
    """Embeddable JS widget: <script src="https://api.garl.ai/api/v1/badge/widget.js" data-agent-id="UUID"></script>"""
    js = '''(function(){
  var s=document.currentScript;
  if(!s) return;
  var id=s.getAttribute("data-agent-id");
  if(!id) return;
  var base=s.getAttribute("data-api-url")||"https://api.garl.ai/api/v1";
  var el=document.createElement("a");
  el.href="https://garl.ai/agent/"+id;
  el.target="_blank";
  el.rel="noopener";
  el.style.display="inline-block";
  var img=document.createElement("img");
  img.src=base+"/badge/svg/"+id;
  img.alt="GARL Trust Badge";
  img.style.height="20px";
  el.appendChild(img);
  s.parentNode.insertBefore(el,s.nextSibling);
})();'''
    return Response(
        content=js,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.get("/badge/{agent_id}")
async def badge_data(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return BadgeData(
        agent_id=agent["id"],
        name=agent["name"],
        trust_score=agent["trust_score"],
        success_rate=agent["success_rate"],
        total_traces=agent["total_traces"],
        verified=agent["total_traces"] >= 10,
        certification_tier=agent.get("certification_tier", "bronze"),
        sovereign_id=agent.get("sovereign_id"),
    )


# --- Webhook CRUD ---

@router.post("/webhooks")
async def create_webhook(req: WebhookRegisterRequest, x_api_key: str = Header(...)):
    _validate_uuid(req.agent_id, "agent_id")
    _verify_agent_ownership(req.agent_id, x_api_key)
    hook = register_webhook(req.agent_id, req.url, req.events)
    return hook


@router.get("/webhooks/{agent_id}")
async def list_agent_webhooks(agent_id: str, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _verify_agent_ownership(agent_id, x_api_key)
    return list_webhooks(agent_id)


@router.patch("/webhooks/{agent_id}/{webhook_id}")
async def patch_webhook(agent_id: str, webhook_id: str, req: WebhookUpdateRequest, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _validate_uuid(webhook_id, "webhook_id")
    _verify_agent_ownership(agent_id, x_api_key)
    result = update_webhook(webhook_id, agent_id, req.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return result


@router.delete("/webhooks/{agent_id}/{webhook_id}")
async def remove_webhook(agent_id: str, webhook_id: str, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _validate_uuid(webhook_id, "webhook_id")
    _verify_agent_ownership(agent_id, x_api_key)
    deleted = delete_webhook(webhook_id, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": True}


# --- Endorsement (Sybil-Resistant) ---

@router.post("/endorse")
async def endorse_agent(req: EndorsementRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16])
    _validate_uuid(req.target_agent_id, "target_agent_id")

    db = _get_supabase()
    endorser_res = db.table("agents").select("id, api_key_hash").eq("api_key_hash", hashlib.sha256(x_api_key.encode()).hexdigest()).execute()
    if not endorser_res.data:
        raise HTTPException(status_code=403, detail="Invalid API key")
    endorser_id = endorser_res.data[0]["id"]

    try:
        result = create_endorsement(endorser_id, req.target_agent_id, req.context, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/endorsements/{agent_id}")
async def read_endorsements(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    return get_endorsements(agent_id)


# --- GDPR & Data Protection ---

@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, req: SoftDeleteRequest, x_api_key: str = Header(...)):
    """GDPR-compliant soft delete."""
    _validate_uuid(agent_id, "agent_id")
    if req.confirmation != "DELETE_CONFIRMED":
        raise HTTPException(status_code=400, detail="Confirmation must be 'DELETE_CONFIRMED'")
    try:
        result = soft_delete_agent(agent_id, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/agents/{agent_id}/anonymize")
async def anonymize(agent_id: str, req: AnonymizeRequest, x_api_key: str = Header(...)):
    """GDPR-compliant anonymization: personal data is hashed."""
    _validate_uuid(agent_id, "agent_id")
    if req.confirmation != "ANONYMIZE_CONFIRMED":
        raise HTTPException(status_code=400, detail="Confirmation must be 'ANONYMIZE_CONFIRMED'")
    try:
        result = anonymize_agent(agent_id, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# --- Compliance Report (CISO) ---

@router.get("/agents/{agent_id}/compliance")
async def read_compliance(agent_id: str, x_api_key: str | None = Header(default=None)):
    """Enterprise compliance report: SLA, security risks, anomaly history."""
    _validate_uuid(agent_id, "agent_id")
    _require_read_auth(x_api_key)
    report = get_compliance_report(agent_id)
    if not report:
        raise HTTPException(status_code=404, detail="Agent not found")
    return report


# --- OpenClaw Integration ---

CATEGORY_KEYWORDS = {
    "coding": ["code", "function", "api", "bug", "fix", "implement", "refactor", "test", "deploy", "build"],
    "research": ["research", "analyze", "find", "search", "investigate", "compare", "review", "study"],
    "data": ["data", "csv", "json", "database", "query", "transform", "pipeline", "extract"],
    "automation": ["automate", "schedule", "cron", "workflow", "script", "batch", "pipeline"],
    "sales": ["email", "outreach", "proposal", "pitch", "customer", "lead", "crm"],
}


def _infer_category(message: str) -> str:
    msg_lower = message.lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in msg_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


@router.post("/ingest/openclaw")
async def ingest_openclaw(request: Request, payload: OpenClawIngestPayload, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16])

    status = "failure" if payload.error else payload.status
    if status not in ("success", "failure", "partial"):
        status = "success"

    category = payload.category or _infer_category(payload.message)

    cost_usd = None
    if payload.usage and "cost_usd" in payload.usage:
        cost_usd = payload.usage["cost_usd"]

    tool_calls_data = None
    if payload.tool_calls:
        tool_calls_data = [
            {"name": tc.get("name", "unknown"), "duration_ms": tc.get("duration_ms")}
            for tc in payload.tool_calls
        ]

    trace_req = TraceSubmitRequest(
        agent_id=payload.agent_id,
        task_description=payload.message[:1000] if payload.message else "OpenClaw task",
        status=status,
        duration_ms=max(payload.duration_ms, 0),
        category=category,
        runtime_env=payload.runtime_env or "openclaw",
        tool_calls=tool_calls_data,
        cost_usd=cost_usd,
        metadata={
            "source": "openclaw",
            "channel": payload.channel,
            "session_id": payload.session_id,
            **(payload.metadata or {}),
        },
    )

    try:
        result = submit_trace(trace_req, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Agent Search ---

@router.get("/search")
async def search_agents_endpoint(q: str = "", category: str | None = None, limit: int = 10):
    return search_agents(q, category, max(1, min(limit, 50)))
