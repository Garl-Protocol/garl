import re
import time
import hashlib
import threading
import contextvars
from collections import defaultdict
from html import escape as html_escape

from fastapi import APIRouter, HTTPException, Header, Request, Response
from fastapi.responses import HTMLResponse

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
    generate_scorecard,
)
from app.services.traces import submit_trace
from app.core.signing import verify_signature, get_public_key_hex, sign_payload

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
rate_limit_info: contextvars.ContextVar[dict | None] = contextvars.ContextVar("rate_limit_info", default=None)

RATE_LIMITS = {
    "default": (120, 60),
    "write": (20, 60),
    "batch": (10, 60),
    "register": (5, 60),
    "auto_register": (3, 300),
}


def _check_rate_limit(key: str, tier: str = "default", request: Request | None = None):
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
        current_count = len(_rate_store[bucket])
        if current_count >= limit:
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
        remaining = limit - current_count - 1
        oldest = min(_rate_store[bucket]) if _rate_store[bucket] else now
        reset_at = int(oldest + window)
        rl_headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(remaining, 0)),
            "X-RateLimit-Reset": str(reset_at),
        }
        rate_limit_info.set(rl_headers)
        if request is not None:
            request.state.rate_limit_headers = rl_headers


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
    _check_rate_limit(_get_client_ip(request), "register", request)
    req.name = _sanitize_agent_name(req.name)
    if req.description:
        req.description = _strip_html(req.description, 500)
    try:
        agent = register_agent(req)
        return agent
    except ValueError as e:
        code = 409 if "already taken" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/agents/auto-register")
async def auto_register_agent(request: Request, req: AutoRegisterRequest):
    """Streamlined registration for autonomous agents: minimal fields, machine-readable instructions."""
    _check_rate_limit(_get_client_ip(request), "auto_register", request)
    req.name = _sanitize_agent_name(req.name)
    if req.description:
        req.description = _strip_html(req.description, 500)

    full_req = AgentRegisterRequest(
        name=req.name,
        framework=req.framework,
        category=req.category,
        description=req.description or f"Auto-registered {req.framework} agent",
    )
    try:
        agent = register_agent(full_req)
    except ValueError as e:
        code = 409 if "already taken" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
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
        .select("id,agent_id,task_description,status,duration_ms,category,trust_delta,created_at")
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


# --- Portable Trust Passport ---

@router.get("/agents/{agent_id}/passport")
async def agent_passport(agent_id: str, request: Request):
    """ECDSA-signed trust snapshot verifiable offline against GARL's public key."""
    _validate_uuid(agent_id, "agent_id")
    _check_rate_limit(_get_client_ip(request), "default", request)
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    now = int(time.time())
    payload = {
        "version": "1.0",
        "agent_id": str(agent["id"]),
        "agent_name": agent["name"],
        "trust_score": round(float(agent.get("trust_score", 50)), 2),
        "certification_tier": agent.get("certification_tier", "bronze"),
        "total_traces": int(agent.get("total_traces", 0)),
        "success_rate": round(float(agent.get("success_rate", 0)), 2),
        "sovereign_id": agent.get("sovereign_id", ""),
        "issued_at": now,
        "expires_at": now + 3600,
        "issuer": "garl-protocol",
    }

    signature, content_hash = sign_payload(payload)

    return {
        "passport": payload,
        "signature": signature,
        "content_hash": content_hash,
        "verify_url": "https://api.garl.ai/api/v1/verify/check",
        "public_key": get_public_key_hex(),
    }


@router.get("/agents/{agent_id}/scorecard")
async def agent_scorecard(agent_id: str, request: Request):
    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return generate_scorecard(agent)


# --- ERC-8004 Compatibility ---

@router.get("/agents/{agent_id}/erc8004")
async def agent_erc8004_metadata(agent_id: str, request: Request):
    """Serve ERC-8004-compatible agent metadata (AgentURI format).
    Allows on-chain systems to read GARL agent data natively."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    trust_score = round(float(agent.get("trust_score", 50)), 2)
    tier = agent.get("certification_tier", "bronze")
    dims = {
        "reliability": round(float(agent.get("score_reliability", 50)), 2),
        "security": round(float(agent.get("score_security", 50)), 2),
        "speed": round(float(agent.get("score_speed", 50)), 2),
        "cost_efficiency": round(float(agent.get("score_cost_efficiency", 50)), 2),
        "consistency": round(float(agent.get("score_consistency", 50)), 2),
    }

    return {
        "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
        "name": agent.get("name", "Unknown"),
        "description": agent.get("description", ""),
        "active": True,
        "services": [
            {
                "name": "A2A",
                "endpoint": f"https://api.garl.ai/api/v1/agents/{agent_id}/card",
                "version": "1.0",
            },
            {
                "name": "MCP",
                "endpoint": "https://api.garl.ai/mcp",
                "version": "2024-11-05",
            },
            {
                "name": "GARL",
                "endpoint": f"https://api.garl.ai/api/v1/agents/{agent_id}/passport",
                "version": "1.0.0",
            },
        ],
        "supportedTrust": ["reputation"],
        "x402Support": False,
        "garl": {
            "sovereign_id": agent.get("sovereign_id", f"did:garl:{agent_id}"),
            "trust_score": trust_score,
            "certification_tier": tier,
            "dimensions": dims,
            "total_traces": int(agent.get("total_traces", 0)),
            "success_rate": round(float(agent.get("success_rate", 0)), 2),
            "framework": agent.get("framework", "custom"),
            "category": agent.get("category", "other"),
            "verified": int(agent.get("total_traces", 0)) >= 10,
        },
    }


@router.get("/agents/{agent_id}/erc8004/feedback")
async def agent_erc8004_feedback(agent_id: str, request: Request):
    """Return trust scores formatted as ERC-8004 Reputation Registry feedback records.
    Blockchain systems can consume these to bridge GARL scores on-chain."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    dim_map = {
        "reliability": float(agent.get("score_reliability", 50)),
        "security": float(agent.get("score_security", 50)),
        "speed": float(agent.get("score_speed", 50)),
        "cost_efficiency": float(agent.get("score_cost_efficiency", 50)),
        "consistency": float(agent.get("score_consistency", 50)),
    }

    feedbacks = []
    for dim_name, dim_value in dim_map.items():
        feedbacks.append({
            "agentId": agent_id,
            "clientAddress": "garl-protocol",
            "createdAt": now,
            "value": str(int(dim_value * 100)),
            "valueDecimals": 2,
            "tag1": dim_name,
            "tag2": "garl-trust-score",
            "endpoint": "https://api.garl.ai/api/v1",
            "reasoning": f"GARL protocol {dim_name} score based on EMA of {agent.get('total_traces', 0)} execution traces",
        })

    composite = round(float(agent.get("trust_score", 50)), 2)
    feedbacks.append({
        "agentId": agent_id,
        "clientAddress": "garl-protocol",
        "createdAt": now,
        "value": str(int(composite * 100)),
        "valueDecimals": 2,
        "tag1": "composite",
        "tag2": "garl-trust-score",
        "endpoint": "https://api.garl.ai/api/v1",
        "reasoning": f"GARL protocol composite trust score ({agent.get('certification_tier', 'bronze')} tier)",
    })

    return {
        "agent_id": agent_id,
        "sovereign_id": agent.get("sovereign_id", f"did:garl:{agent_id}"),
        "format": "erc8004-reputation-v1",
        "feedbacks": feedbacks,
    }


# --- Trace Verification ---

@router.post("/verify", response_model=TraceResponse)
async def verify_trace(request: Request, req: TraceSubmitRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16], "write", request)
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
    _check_rate_limit(x_api_key[:16], "batch", request)

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
async def leaderboard(request: Request, category: str | None = None, limit: int = 50, offset: int = 0):
    _check_rate_limit(_get_client_ip(request), "default", request)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    return get_leaderboard(category, limit, offset)


@router.get("/feed")
async def activity_feed(request: Request, limit: int = 20, offset: int = 0):
    _check_rate_limit(_get_client_ip(request), "default", request)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    return get_recent_traces(limit, offset)


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


@router.post("/trust/verify/batch")
async def bulk_trust_check(request: Request):
    """Batch trust check for up to 20 agents in a single call."""
    _check_rate_limit(_get_client_ip(request), "batch", request)
    body = await request.json()
    agent_ids = body.get("agent_ids", [])
    if not agent_ids or len(agent_ids) > 20:
        raise HTTPException(status_code=422, detail="agent_ids required, max 20")

    results = []
    for aid in agent_ids:
        try:
            _validate_uuid(aid, "agent_id")
            trust_data = get_a2a_trust(aid)
            if not trust_data:
                results.append({
                    "agent_id": aid,
                    "registered": False,
                    "trust_score": 0,
                    "risk_level": "unknown",
                    "recommendation": "unknown",
                    "message": "This agent is not registered on GARL Protocol.",
                })
            else:
                trust_data["registered"] = True
                results.append(trust_data)
        except HTTPException:
            results.append({"agent_id": aid, "error": "Invalid agent ID format"})
        except Exception:
            results.append({"agent_id": aid, "error": "Agent not found"})

    return {"results": results, "total": len(results)}


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


@router.get("/badge/embed/{agent_id}")
async def badge_embed(agent_id: str, request: Request):
    """Embeddable iframe trust card widget."""
    _check_rate_limit(_get_client_ip(request), request=request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    name = html_escape(agent.get("name", "Unknown"))
    score = round(float(agent.get("trust_score", 50)), 1)
    tier = agent.get("certification_tier", "bronze")
    traces = int(agent.get("total_traces", 0))
    verified = traces >= 10

    score_color = "#00ff88" if score >= 70 else "#ffaa00" if score >= 40 else "#ff4444"
    tier_colors = {"enterprise": "#a855f7", "gold": "#eab308", "silver": "#94a3b8", "bronze": "#d97706"}
    tier_color = tier_colors.get(tier, "#d97706")

    verified_html = '<span class="verified">&#10003; verified</span>' if verified else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} — GARL Trust</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0a0a1a;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;color:#e0e0ff;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:12px}}
.card{{background:#12122a;border:1px solid #2a2a3a;border-radius:12px;padding:20px 24px;max-width:320px;width:100%}}
.header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}}
.name{{font-size:14px;font-weight:600;color:#e0e0ff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px}}
.tier{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;padding:2px 8px;border-radius:4px;background:rgba(255,255,255,0.05);color:{tier_color}}}
.score-row{{display:flex;align-items:baseline;gap:6px;margin-bottom:8px}}
.score{{font-size:36px;font-weight:700;color:{score_color};line-height:1}}
.max{{font-size:14px;color:#4a4a6a}}
.bar{{height:4px;border-radius:2px;background:#1a1a2e;overflow:hidden;margin-bottom:12px}}
.bar-fill{{height:100%;border-radius:2px;background:{score_color};width:{min(score, 100)}%}}
.meta{{display:flex;justify-content:space-between;font-size:11px;color:#8b8ba7}}
.meta a{{color:#3b82f6;text-decoration:none}}
.meta a:hover{{text-decoration:underline}}
.verified{{color:#00ff88}}
.garl{{margin-top:10px;text-align:center;font-size:9px;color:#4a4a6a}}
.garl a{{color:#4a4a6a;text-decoration:none}}
.garl a:hover{{color:#8b8ba7}}
</style>
</head>
<body>
<div class="card">
<div class="header">
<span class="name">{name}</span>
<span class="tier">{tier}</span>
</div>
<div class="score-row">
<span class="score">{score}</span>
<span class="max">/100</span>
</div>
<div class="bar"><div class="bar-fill"></div></div>
<div class="meta">
<span>{traces} traces {verified_html}</span>
<a href="https://garl.ai/agent/{agent_id}" target="_blank" rel="noopener">View Profile &#8594;</a>
</div>
<div class="garl"><a href="https://garl.ai" target="_blank" rel="noopener">Powered by GARL Protocol</a></div>
</div>
</body>
</html>"""

    return HTMLResponse(
        content=html,
        headers={
            "Content-Security-Policy": "frame-ancestors *",
            "Cache-Control": "public, max-age=300",
        },
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
async def endorse_agent(request: Request, req: EndorsementRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16], "default", request)
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
    _check_rate_limit(x_api_key[:16], "default", request)

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
async def search_agents_endpoint(q: str = "", category: str | None = None, limit: int = 10, offset: int = 0):
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    return search_agents(q, category, max(1, min(limit, 50)), max(0, offset))
