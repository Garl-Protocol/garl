import re
import time
import json
import hmac
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
)
from app.services.agents import (
    register_agent,
    get_agent,
    get_agent_detail,
    get_leaderboard,
    get_recent_traces,
    get_stats,
    get_public_stats,
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
from app.core.signing import (
    verify_signature,
    get_public_key_hex,
    sign_payload,
    sign_trace,
    get_key_registry,
    get_active_key_id,
    derive_key_id,
)
from app.core.cache import cache_get, cache_set

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
    """Read authorization: requires a valid registered API key."""
    settings = get_settings()
    if settings.read_auth_enabled:
        if not x_api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required for this endpoint. Set x-api-key header."
            )
        import hmac
        from app.core.supabase_client import get_supabase
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        db = get_supabase()
        match = db.table("agents").select("id").eq("api_key_hash", key_hash).limit(1).execute()
        if not match.data:
            raise HTTPException(status_code=403, detail="Invalid API key.")


# --- Agent CRUD ---

@router.post("/agents", response_model=AgentResponse, summary="Register a new AI agent", tags=["Agents"])
async def create_agent(request: Request, req: AgentRegisterRequest):
    """Register a new AI agent in the GARL Protocol. Returns agent ID and API key."""
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


@router.post("/agents/auto-register", summary="Auto-register agent (minimal fields)", tags=["Agents"])
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
        developer_handle=req.developer_handle,
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


_PUBLIC_AGENT_FIELDS = (
    "id",
    "name",
    "description",
    "framework",
    "category",
    "homepage_url",
    "trust_score",
    "trust_score_lower",
    "trust_score_upper",
    "confidence",
    "certification_tier",
    "total_traces",
    "success_rate",
    "score_reliability",
    "score_speed",
    "score_cost_efficiency",
    "score_consistency",
    "score_security",
    "endorsement_count",
    "endorsement_score",
    "anomaly_flags",
    "sovereign_id",
    "last_trace_at",
    "created_at",
)


@router.get("/agents/{agent_id}", summary="Get agent by ID", tags=["Agents"])
async def read_agent(
    agent_id: str,
    response: Response,
    fields: str = "public",
    x_api_key: str | None = Header(default=None),
):
    """Fetch agent profile by UUID.

    By default returns a slim public projection (~24 fields) safe to
    share with anyone — score, dimensions, tier, identity, activity
    timestamps. Pass ``?fields=full`` together with an ``x-api-key``
    header whose hash matches the agent's ``api_key_hash`` to receive
    the full response (EMA values, security_events, permissions,
    sandbox/deleted flags, developer_id). ``api_key_hash`` itself is
    never exposed. Unauthenticated ``?fields=full`` requests silently
    fall back to the slim projection and carry ``Deprecation: true``
    plus a ``Sunset`` header so integrators can migrate before a hard
    cut.
    """
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if fields == "full":
        stored_hash = agent.get("api_key_hash") or ""
        provided_hash = (
            hashlib.sha256(x_api_key.encode()).hexdigest() if x_api_key else ""
        )
        if stored_hash and provided_hash and hmac.compare_digest(stored_hash, provided_hash):
            return agent
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = "Thu, 15 Oct 2026 00:00:00 GMT"
        response.headers["Link"] = '<https://garl.ai/docs#fields-full-auth>; rel="deprecation"'
    return {k: agent.get(k) for k in _PUBLIC_AGENT_FIELDS if k in agent}


@router.get(
    "/agents/{agent_id}/audit",
    summary="Audit log export (CSV / JSON-LD) for compliance",
    tags=["Agents", "Compliance"],
)
async def agent_audit_export(
    agent_id: str,
    request: Request,
    response: Response,
    days: int = 90,
    format: str = "csv",
    limit: int = 5000,
):
    """Bulk receipt export for compliance evidence (EU AI Act Code of
    Practice on AI-generated content, California SB 942 AI Transparency
    Act, ISO/IEC 42001:2023 Annex B, NIST AI RMF, and internal audits).

    Streams every trace this agent submitted in the trailing ``days``
    window with its ECDSA-secp256k1 signature attached, capped at
    ``limit`` rows. Public endpoint — anyone can audit any agent's
    public ledger history. ``format=csv`` is reviewer-friendly,
    ``format=jsonld`` returns one ``CertifiedExecutionTrace`` per row
    matching the existing per-trace certificate envelope.
    """
    import csv as _csv
    from io import StringIO
    from datetime import datetime, timedelta, timezone

    _validate_uuid(agent_id, "agent_id")
    _check_rate_limit(_get_client_ip(request), "default", request)

    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")
    _VALID_AUDIT_FORMATS = (
        "csv", "jsonld", "in-toto", "slsa-v1.1", "ca-sb942", "iso42001-annexb", "c2pa",
    )
    if format not in _VALID_AUDIT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of {', '.join(_VALID_AUDIT_FORMATS)}",
        )
    if limit < 1 or limit > 10000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 10000")

    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = _get_supabase()
    res = (
        db.table("traces")
        .select(
            "id,trace_hash,task_description,status,duration_ms,category,"
            "cost_usd,token_count,certificate,created_at"
        )
        .eq("agent_id", agent_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    pubkey = get_public_key_hex()

    if format == "csv":
        buf = StringIO()
        writer = _csv.writer(buf)
        writer.writerow([
            "trace_id", "trace_hash", "created_at", "status",
            "category", "duration_ms", "cost_usd", "token_count",
            "task_description", "ecdsa_signature", "public_key",
        ])
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            writer.writerow([
                r.get("id", ""),
                r.get("trace_hash", ""),
                r.get("created_at", ""),
                r.get("status", ""),
                r.get("category", ""),
                r.get("duration_ms", 0),
                r.get("cost_usd", 0),
                r.get("token_count", 0),
                (r.get("task_description") or "").replace("\n", " "),
                proof.get("signature", ""),
                pubkey,
            ])
        body = buf.getvalue()
        filename = f"garl-audit-{agent_id}-{days}d.csv"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Cache-Control"] = "private, no-store"
        return Response(content=body, media_type="text/csv; charset=utf-8")

    import base64 as _b64
    active_key_id = derive_key_id(pubkey)

    if format == "in-toto":
        # Array of DSSE envelopes wrapping in-toto v1 Statements with
        # the garl/ai-authorship-v1 predicate. Signatures are the
        # existing per-trace ECDSA signatures (base64-encoded here per
        # DSSE rather than hex).
        envelopes = []
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            statement = {
                "_type": "https://in-toto.io/Statement/v1",
                "subject": [{
                    "name": f"garl-trace:{r.get('id')}",
                    "digest": {"sha256": r.get("trace_hash", "")},
                }],
                "predicateType": "https://garl.ai/ai-authorship/v1",
                "predicate": {
                    "agent_id": agent_id,
                    "agent_name": agent.get("name"),
                    "task_description": r.get("task_description"),
                    "status": r.get("status"),
                    "category": r.get("category"),
                    "duration_ms": r.get("duration_ms"),
                    "cost_usd": float(r.get("cost_usd") or 0),
                    "token_count": r.get("token_count", 0),
                    "signed_at_unix": proof.get("created"),
                    "signing_epoch": "original" if cert else "pre-v0.3-unsigned-legacy",
                    "canonical_registry": "https://api.garl.ai",
                },
            }
            payload_bytes = json.dumps(
                statement, sort_keys=True, separators=(",", ":")
            ).encode()
            sig_hex = proof.get("signature", "")
            try:
                sig_b64 = _b64.b64encode(bytes.fromhex(sig_hex)).decode() if sig_hex else ""
            except ValueError:
                sig_b64 = ""
            envelopes.append({
                "payloadType": "application/vnd.in-toto+json",
                "payload": _b64.b64encode(payload_bytes).decode(),
                "signatures": [{
                    "keyid": proof.get("key_id") or active_key_id,
                    "sig": sig_b64,
                }],
            })
        return {
            "@type": "GarlAuditReport.InToto",
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "window_days": days,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "predicate_type": "https://garl.ai/ai-authorship/v1",
            "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
            "envelope_count": len(envelopes),
            "truncated": len(envelopes) >= limit,
            "envelopes": envelopes,
        }

    if format == "slsa-v1.1":
        # In-toto Statement v1 with SLSA v1.1 Provenance predicate.
        # Emits per-trace statements; consumers can then sign them
        # with cosign / rekor / their own signer.
        statements = []
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            statements.append({
                "_type": "https://in-toto.io/Statement/v1",
                "subject": [{
                    "name": f"garl-trace:{r.get('id')}",
                    "digest": {"sha256": r.get("trace_hash", "")},
                }],
                "predicateType": "https://slsa.dev/provenance/v1",
                "predicate": {
                    "buildDefinition": {
                        "buildType": "https://garl.ai/ai-authorship/v1",
                        "externalParameters": {
                            "agent_id": agent_id,
                            "category": r.get("category"),
                            "task": r.get("task_description"),
                        },
                        "internalParameters": {
                            "scoring_method": "exponential_moving_average",
                            "trust_score_after": r.get("status"),
                        },
                    },
                    "runDetails": {
                        "builder": {
                            "id": f"garl-agent:{agent.get('name') or agent_id}",
                            "version": {"garl": "v1"},
                        },
                        "metadata": {
                            "invocationId": r.get("id"),
                            "startedOn": r.get("created_at"),
                            "finishedOn": r.get("created_at"),
                        },
                    },
                    "garl": {
                        "signing_epoch": "original" if cert else "pre-v0.3-unsigned-legacy",
                        "key_id": proof.get("key_id") or active_key_id,
                        "signature_hex": proof.get("signature"),
                        "duration_ms": r.get("duration_ms"),
                    },
                },
            })
        return {
            "@type": "GarlAuditReport.SLSAv1_1",
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "window_days": days,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "predicate_type": "https://slsa.dev/provenance/v1",
            "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
            "statement_count": len(statements),
            "truncated": len(statements) >= limit,
            "statements": statements,
        }

    if format == "ca-sb942":
        # California SB 942 — AI Transparency Act evidence (active
        # since 1 Jan 2026). Each record carries the AI system name,
        # generation timestamp, and a machine-detectable provenance
        # pointer (the GARL receipt URL + ECDSA signature).
        records = []
        frontend = get_settings().public_frontend_url.rstrip("/")
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            short = (r.get("trace_hash") or "")[:8]
            records.append({
                "record_type": "ai_generated_content_disclosure",
                "ai_system_name": f"{agent.get('name') or 'garl-agent'} (framework={agent.get('framework') or 'custom'})",
                "ai_system_version": "v1",
                "generation_date": r.get("created_at"),
                "content_type": "source-code-commit-or-change",
                "content_identifier": r.get("trace_hash"),
                "content_summary": r.get("task_description"),
                "generation_method": "ai_autonomous_or_assisted",
                "provenance": {
                    "receipt_url": f"{frontend}/r/{short}" if short else None,
                    "verify_url": f"https://api.garl.ai/api/v1/verify/{r.get('trace_hash','')}",
                    "signature_algorithm": "ECDSA-secp256k1",
                    "signature_hex": proof.get("signature"),
                    "key_id": proof.get("key_id") or active_key_id,
                    "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
                    "signing_epoch": "original" if cert else "pre-v0.3-unsigned-legacy",
                },
            })
        return {
            "@type": "GarlAuditReport.CaliforniaSB942",
            "regulation": "California SB 942 (AI Transparency Act)",
            "regulation_url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB942",
            "regulation_effective": "2026-01-01",
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "window_days": days,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "truncated": len(records) >= limit,
            "records": records,
        }

    if format == "iso42001-annexb":
        # ISO/IEC 42001:2023 Annex B — AI management system evidence.
        # Controls we're mapping per record:
        #   A.6.2 (AI system lifecycle), A.6.2.5 (AI system verification),
        #   A.7.2 (Data quality), A.8.3 (Information for interested parties).
        records = []
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            records.append({
                "evidence_type": "ai_system_execution_record",
                "controls": ["A.6.2", "A.6.2.5", "A.7.2", "A.8.3"],
                "ai_system": {
                    "id": agent_id,
                    "name": agent.get("name"),
                    "sovereign_id": agent.get("sovereign_id"),
                },
                "execution": {
                    "trace_id": r.get("id"),
                    "started_on": r.get("created_at"),
                    "status": r.get("status"),
                    "category": r.get("category"),
                    "duration_ms": r.get("duration_ms"),
                    "task": r.get("task_description"),
                },
                "data_provenance": {
                    "content_hash_algorithm": "SHA-256",
                    "content_hash": r.get("trace_hash"),
                    "signature_algorithm": "ECDSA-secp256k1",
                    "signature_hex": proof.get("signature"),
                    "key_id": proof.get("key_id") or active_key_id,
                    "signing_epoch": "original" if cert else "pre-v0.3-unsigned-legacy",
                    "verifier_registry": "https://api.garl.ai/.well-known/garl-keys.json",
                },
            })
        return {
            "@type": "GarlAuditReport.ISO42001AnnexB",
            "standard": "ISO/IEC 42001:2023 Annex B",
            "standard_url": "https://www.iso.org/standard/42001",
            "controls_covered": ["A.6.2", "A.6.2.5", "A.7.2", "A.8.3"],
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "window_days": days,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "truncated": len(records) >= limit,
            "records": records,
        }

    if format == "c2pa":
        # C2PA-inspired Content Credentials manifests for code — one
        # manifest per trace, each describing a generative action with
        # the agent as claim_generator. This is a C2PA-adjacent shape,
        # not a strict C2PA 2.x binary manifest (those require JUMBF);
        # the envelope keys mirror the core C2PA vocabulary so tools
        # familiar with C2PA can consume it directly.
        manifests = []
        for r in rows:
            cert = r.get("certificate") or {}
            proof = (cert.get("proof") if isinstance(cert, dict) else {}) or {}
            manifests.append({
                "@context": "https://c2pa.org/schemas/v2",
                "claim_generator": f"GARL-Protocol/{agent.get('name') or 'agent'}",
                "claim_generator_version": "garl/v1",
                "instance_id": r.get("id"),
                "format": "application/vnd.garl.code-change+json",
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [
                                {
                                    "action": "c2pa.created",
                                    "when": r.get("created_at"),
                                    "softwareAgent": agent.get("name"),
                                    "digitalSourceType": (
                                        "http://cv.iptc.org/newscodes/digitalsourcetype/"
                                        "algorithmicallyGenerated"
                                    ),
                                    "parameters": {
                                        "task": r.get("task_description"),
                                        "category": r.get("category"),
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "label": "c2pa.hash.data",
                        "alg": "sha256",
                        "hash": r.get("trace_hash"),
                    },
                ],
                "signature": {
                    "alg": "ES256K",
                    "sig": proof.get("signature"),
                    "key_id": proof.get("key_id") or active_key_id,
                    "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
                },
            })
        return {
            "@type": "GarlAuditReport.C2PA",
            "profile": "C2PA-adjacent Content Credentials for source code",
            "profile_note": "Code-domain extension; not a C2PA 2.x JUMBF manifest",
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "window_days": days,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "manifest_count": len(manifests),
            "truncated": len(manifests) >= limit,
            "manifests": manifests,
        }

    # JSON-LD: array of CertifiedExecutionTrace envelopes (default)
    items = []
    for r in rows:
        cert = r.get("certificate") or {}
        items.append({
            "@type": "CertifiedExecutionTrace",
            "trace_id": r.get("id"),
            "trace_hash": r.get("trace_hash"),
            "created_at": r.get("created_at"),
            "status": r.get("status"),
            "category": r.get("category"),
            "duration_ms": r.get("duration_ms"),
            "task_description": r.get("task_description"),
            "certificate": cert,
        })
    return {
        "@context": "https://garl.io/schema/v1",
        "@type": "AgentAuditReport",
        "agent_id": agent_id,
        "agent_name": agent.get("name"),
        "sovereign_id": agent.get("sovereign_id"),
        "window_days": days,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "public_key": pubkey,
        "key_id": active_key_id,
        "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
        "trace_count": len(items),
        "truncated": len(items) >= limit,
        "traces": items,
    }


@router.get("/agents/{agent_id}/detail", summary="Get agent detail", tags=["Agents"])
async def read_agent_detail(agent_id: str):
    """Agent detail — public profile with traces, history, and decay projection."""
    _validate_uuid(agent_id, "agent_id")
    detail = get_agent_detail(agent_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Agent not found")
    return detail


@router.get("/agents/{agent_id}/traces", summary="Get agent traces", tags=["Agents"])
async def read_agent_traces(agent_id: str, limit: int = 20, offset: int = 0):
    """Public endpoint: recent traces for a specific agent."""
    _validate_uuid(agent_id, "agent_id")
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    from app.core.supabase_client import get_supabase
    db = get_supabase()
    res = (
        db.table("traces")
        .select("id,agent_id,task_description,status,duration_ms,category,trust_delta,cost_usd,trace_hash,created_at", count="exact")
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    total = res.count or 0
    return {
        "data": res.data or [],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": total > offset + limit,
    }


@router.get("/agents/{agent_id}/card", summary="Get agent card", tags=["Agents"])
async def read_agent_card(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    card = get_agent_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail="Agent not found")
    return card


# --- Portable Trust Passport ---

@router.get("/agents/{agent_id}/passport", summary="Portable trust passport", tags=["Agents"])
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


@router.get("/agents/{agent_id}/scorecard", summary="Get agent scorecard", tags=["Agents"])
async def agent_scorecard(agent_id: str, request: Request):
    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return generate_scorecard(agent)


@router.get(
    "/agents/{agent_id}/trust-vector",
    summary="Multi-dimensional Trust Vector",
    tags=["Agents"],
)
async def agent_trust_vector(agent_id: str, request: Request):
    """Trust Vector v0.1 — multi-dimensional reputation projection.

    A vector instead of a single score because different domains stress
    different dimensions. Spec: protocol/spec/trust-vector-v0.1.md.

    The legacy composite ``trust_score`` and ``certification_tier`` are
    preserved under ``legacy_composite`` for callers that still want a
    single number.
    """
    from app.services.trust_vector import compute_trust_vector

    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(agent_id, "agent_id")
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return compute_trust_vector(agent)


# --- ERC-8004 Compatibility ---

@router.get("/agents/{agent_id}/erc8004", summary="ERC-8004 agent metadata", tags=["ERC-8004"])
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


@router.get("/agents/{agent_id}/erc8004/feedback", summary="ERC-8004 reputation feedback", tags=["ERC-8004"])
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


# --- Public Trace Verification (No API key required) ---

_HEX_RE = re.compile(r"^[0-9a-f]+$")


_TIER_ORDER = ("bronze", "silver", "gold", "enterprise")


@router.post(
    "/policy/check",
    summary="Evaluate a declarative policy against a set of receipts",
    tags=["Trust & Verification", "Compliance"],
)
async def policy_check(request: Request, body: dict):
    """Stateless policy gate for CI/CD pipelines.

    Accepts ``{"policy": {...}, "receipts": [<trace_hash or short_hash>, ...]}``
    and returns a pass/fail evaluation with per-receipt reasons. Designed
    to be called from GitHub Actions, GitLab CI, or any build runner:
    the action does not need to re-implement policy logic.

    **Policy fields (all optional, conjunctive):**

    - ``min_score``: minimum agent trust score (0-100)
    - ``min_tier``: one of ``bronze|silver|gold|enterprise``
    - ``require_model_disclosure``: if true, each receipt must carry at
      least one entry in ``metadata.models``
    - ``allowed_models``: list of model names (e.g.
      ``["claude-opus-4-6", "claude-sonnet-4-6"]``) — at least one must
      appear in each receipt's models
    - ``forbidden_models``: list; none may appear in any receipt
    - ``require_signing_epoch``: ``"original"`` to reject pre-v0.3
      unsigned-legacy traces
    """
    _check_rate_limit(_get_client_ip(request), "default", request)

    policy = (body or {}).get("policy") or {}
    receipts = (body or {}).get("receipts") or []
    if not isinstance(receipts, list) or not receipts:
        raise HTTPException(status_code=400, detail="receipts must be a non-empty list")
    if len(receipts) > 100:
        raise HTTPException(status_code=400, detail="max 100 receipts per call")

    min_score = policy.get("min_score")
    min_tier = policy.get("min_tier")
    require_disclosure = bool(policy.get("require_model_disclosure", False))
    allowed_models = policy.get("allowed_models")
    forbidden_models = policy.get("forbidden_models")
    require_epoch = policy.get("require_signing_epoch")

    if min_tier is not None and min_tier not in _TIER_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"min_tier must be one of {', '.join(_TIER_ORDER)}",
        )

    db = None  # lazy — only touch Supabase when a valid hash needs lookup
    evaluations = []
    for rcpt in receipts:
        if not isinstance(rcpt, str):
            continue
        h = rcpt.strip().lower()
        if not _HEX_RE.match(h) or len(h) < 8 or len(h) > 64:
            evaluations.append({
                "receipt": rcpt,
                "pass": False,
                "reasons": ["invalid_hash_format"],
            })
            continue
        if db is None:
            db = _get_supabase()
        if len(h) == 64:
            res = db.table("traces").select("*").eq("trace_hash", h).limit(1).execute()
        else:
            res = db.table("traces").select("*").like("trace_hash", f"{h}%").limit(2).execute()
        rows = res.data or []
        if not rows:
            evaluations.append({"receipt": rcpt, "pass": False, "reasons": ["receipt_not_found"]})
            continue
        if len(rows) > 1:
            evaluations.append({"receipt": rcpt, "pass": False, "reasons": ["ambiguous_hash_prefix"]})
            continue
        trace = rows[0]
        reasons: list[str] = []

        agent_row = db.table("agents").select(
            "id,name,trust_score,certification_tier"
        ).eq("id", trace["agent_id"]).limit(1).execute()
        agent = (agent_row.data or [{}])[0]

        score = float(agent.get("trust_score") or 0)
        tier = agent.get("certification_tier") or "bronze"

        if min_score is not None and score < float(min_score):
            reasons.append(f"score_below_min ({score} < {min_score})")

        if min_tier is not None:
            try:
                if _TIER_ORDER.index(tier) < _TIER_ORDER.index(min_tier):
                    reasons.append(f"tier_below_min ({tier} < {min_tier})")
            except ValueError:
                reasons.append("unknown_tier")

        md = trace.get("metadata") or {}
        models = md.get("models") if isinstance(md, dict) else None
        model_names = [m.get("name") for m in (models or []) if isinstance(m, dict) and m.get("name")]

        if require_disclosure and not model_names:
            reasons.append("no_model_disclosure")

        if allowed_models:
            if not any(m in allowed_models for m in model_names):
                reasons.append("no_allowed_model_present")

        if forbidden_models:
            bad = [m for m in model_names if m in forbidden_models]
            if bad:
                reasons.append(f"forbidden_model_present ({','.join(bad)})")

        if require_epoch:
            cert = trace.get("certificate") or {}
            epoch = "original" if cert else "pre-v0.3-unsigned-legacy"
            if require_epoch == "original" and epoch != "original":
                reasons.append("signing_epoch_not_original")

        evaluations.append({
            "receipt": rcpt,
            "trace_hash": trace.get("trace_hash"),
            "agent_id": agent.get("id"),
            "agent_name": agent.get("name"),
            "score": score,
            "tier": tier,
            "models": model_names,
            "pass": not reasons,
            "reasons": reasons,
        })

    overall = all(e.get("pass") for e in evaluations) and len(evaluations) == len(receipts)
    return {
        "pass": overall,
        "policy": policy,
        "evaluation_count": len(evaluations),
        "evaluations": evaluations,
    }


@router.get(
    "/receipts/{trace_hash}/cert.json",
    summary="Raw stored certificate (no re-sign)",
    tags=["Trust & Verification"],
)
async def receipt_raw_certificate(trace_hash: str, request: Request, response: Response):
    """Return the certificate exactly as it was stored at trace-submission
    time — no re-signing. Provides a stable, canonical URL that consumers
    can hash or archive without worrying about signature drift.

    Accepts the same hash / short-hash grammar as /verify (8-64 hex).
    Returns 404 if no original signature exists (pre-v0.3 legacy). Use
    /verify for the richer envelope with signing_epoch disclosure.
    """
    _check_rate_limit(_get_client_ip(request), "default", request)

    # Action Receipt v0.1 takes precedence: this path also serves the generic
    # receipt envelope by receipt_id (UUID) or output_hash (64-hex). Try it
    # first so UUIDs (which fail the hex grammar below) resolve correctly. If
    # the receipts subsystem is unavailable, fall through to legacy trace cert.
    try:
        from app.services.action_receipts import get_action_receipt
        envelope = get_action_receipt((trace_hash or "").strip())
    except Exception:
        envelope = None
    if envelope:
        response.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400, immutable"
        return envelope

    h = (trace_hash or "").strip().lower()
    if not h or len(h) < 8 or len(h) > 64 or not _HEX_RE.match(h):
        raise HTTPException(status_code=400, detail="Invalid trace hash")

    db = _get_supabase()
    if len(h) == 64:
        res = db.table("traces").select("trace_hash,certificate").eq("trace_hash", h).limit(1).execute()
    else:
        res = (
            db.table("traces")
            .select("trace_hash,certificate")
            .like("trace_hash", f"{h}%")
            .limit(2)
            .execute()
        )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Receipt not found")
    if len(rows) > 1:
        raise HTTPException(status_code=409, detail="Ambiguous hash prefix")

    cert = rows[0].get("certificate") or {}
    if not (isinstance(cert, dict) and cert.get("proof")):
        raise HTTPException(
            status_code=404,
            detail="No original certificate stored for this trace (pre-v0.3 legacy). Use /verify for the signing_epoch disclosure.",
        )

    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400, immutable"
    return cert


@router.get("/keys", summary="Public signing key registry", tags=["Trust & Verification"])
async def list_public_keys(response: Response):
    """Mirror of /.well-known/garl-keys.json for API-prefix consumers.

    Returns the active signer public key plus any retired keys (by
    ``key_id``) so clients can verify older receipts after rotation."""
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=3600"
    return get_key_registry()


@router.get("/verify/{trace_hash}", summary="Verify trace by hash or short hash (public)", tags=["Trust & Verification"])
async def public_verify_trace(trace_hash: str, request: Request, response: Response):
    """Public endpoint: verify a trace's ECDSA signature by its hash.

    Accepts either the full 64-character SHA-256 hex hash or a short prefix
    (8-63 chars) for shareable receipt URLs. Short prefixes are resolved via
    prefix match; ambiguous prefixes return 409.

    No API key required — anyone can verify any trace's authenticity.
    """
    _check_rate_limit(_get_client_ip(request), "default", request)

    hash_input = (trace_hash or "").strip().lower()
    if not hash_input or len(hash_input) < 8 or len(hash_input) > 64 or not _HEX_RE.match(hash_input):
        raise HTTPException(
            status_code=400,
            detail="Invalid trace hash. Must be 8-64 lowercase hex characters (SHA-256 prefix or full hash).",
        )

    db = _get_supabase()

    if len(hash_input) == 64:
        res = db.table("traces").select("*").eq("trace_hash", hash_input).execute()
        matches = res.data or []
    else:
        res = (
            db.table("traces")
            .select("*")
            .like("trace_hash", f"{hash_input}%")
            .limit(2)
            .execute()
        )
        matches = res.data or []
        if len(matches) > 1:
            raise HTTPException(
                status_code=409,
                detail="Ambiguous hash prefix — multiple traces match. Use a longer prefix.",
            )

    if not matches:
        raise HTTPException(status_code=404, detail="Trace not found")

    trace = matches[0]
    full_hash = trace.get("trace_hash", "")

    stored_cert = trace.get("certificate") or {}
    has_original = (
        isinstance(stored_cert, dict)
        and stored_cert.get("proof")
        and isinstance(stored_cert["proof"], dict)
        and stored_cert["proof"].get("signature")
    )

    if has_original:
        # Return the original signature — chain of custody intact. No
        # re-sign (the previous behaviour produced a fresh non-deterministic
        # signature on every call and overwrote trust_score_after with 50.0
        # because the column doesn't exist — both fixed in one go).
        certificate = stored_cert
        signing_epoch = "original"
        original_signed_at = (stored_cert.get("proof") or {}).get("created")
    else:
        # pre-v0.3 legacy: no original signature ever existed. Surface the
        # raw payload without a fake signature so downstream consumers can
        # reason about chain-of-custody honestly via signing_epoch.
        certificate = {
            "@context": "https://garl.io/schema/v1",
            "@type": "CertifiedExecutionTrace",
            "payload": {
                "trace_id": trace["id"],
                "agent_id": trace["agent_id"],
                "task_description": trace.get("task_description", ""),
                "status": trace.get("status", ""),
                "duration_ms": trace.get("duration_ms", 0),
                "category": trace.get("category", "other"),
            },
        }
        signing_epoch = "pre-v0.3-unsigned-legacy"
        original_signed_at = None

    is_valid = bool(has_original and verify_signature(certificate))

    # Enrich with agent summary for receipt cards / OG rendering
    agent_row = db.table("agents").select(
        "name,framework,certification_tier,trust_score"
    ).eq("id", trace["agent_id"]).limit(1).execute()
    agent = (agent_row.data or [{}])[0]

    frontend_url = get_settings().public_frontend_url.rstrip("/")
    short = full_hash[:8] if full_hash else hash_input[:8]
    receipt_url = f"{frontend_url}/r/{short}" if short else None

    # Receipts are immutable per trace_hash (the hash itself fixes
    # every field that can affect the response). Cache hard so CDN +
    # browser can serve hot receipts without round-tripping.
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=86400, stale-while-revalidate=86400, immutable"

    return {
        "verified": is_valid,
        "trace_hash": full_hash or hash_input,
        "trace_id": trace["id"],
        "agent_id": trace["agent_id"],
        "agent_name": agent.get("name"),
        "agent_framework": agent.get("framework"),
        "agent_tier": agent.get("certification_tier"),
        "agent_trust_score": float(agent["trust_score"]) if agent.get("trust_score") is not None else None,
        "task_description": trace.get("task_description"),
        "status": trace.get("status"),
        "category": trace.get("category"),
        "duration_ms": trace.get("duration_ms"),
        "runtime_env": trace.get("runtime_env") or None,
        "created_at": trace.get("created_at"),
        "receipt_url": receipt_url,
        "short_hash": short,
        "certificate": certificate,
        "public_key": get_public_key_hex(),
        "key_id": get_active_key_id(),
        "signing_epoch": signing_epoch,
        "original_signed_at": original_signed_at,
        "key_registry_url": "https://api.garl.ai/.well-known/garl-keys.json",
        "rekor": ((certificate.get("proof") or {}).get("rekor") if isinstance(certificate, dict) else None),
    }


# --- Trace Submission ---

@router.post("/verify", response_model=TraceResponse, summary="Submit execution trace", tags=["Trust & Verification"])
async def verify_trace(request: Request, req: TraceSubmitRequest, x_api_key: str = Header(...)):
    """Submit a single execution trace to update agent trust score. Requires x-api-key header."""
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


@router.post("/verify/batch", summary="Submit batch traces", tags=["Trust & Verification"])
async def verify_batch(request: Request, req: BatchTraceRequest, x_api_key: str = Header(...)):
    """Submit multiple execution traces in a single request. All traces must belong to the same agent."""
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


@router.post("/verify/check", summary="Verify certificate/passport", tags=["Trust & Verification"])
async def check_certificate(certificate: dict):
    if "passport" in certificate and "signature" in certificate:
        payload = certificate["passport"]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).digest()
        try:
            from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
            vk = VerifyingKey.from_string(
                bytes.fromhex(certificate.get("public_key", get_public_key_hex())),
                curve=SECP256k1,
            )
            valid = vk.verify_digest(bytes.fromhex(certificate["signature"]), digest)
        except Exception:
            valid = False
    else:
        valid = verify_signature(certificate)
    return {"valid": valid, "public_key": get_public_key_hex()}


# --- Discovery & Ranking ---

@router.get("/leaderboard", summary="Get trust leaderboard", description="Returns agents ranked by trust score. Supports category filter and pagination.", tags=["Discovery"])
async def leaderboard(request: Request, category: str | None = None, limit: int = 50, offset: int = 0):
    _check_rate_limit(_get_client_ip(request), "default", request)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    cache_key = f"leaderboard:{category or 'all'}:{limit}:{offset}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = get_leaderboard(category, limit, offset)
    cache_set(cache_key, result, ttl=120)
    return result


@router.get("/feed", summary="Activity feed", description="Real-time feed of latest execution traces across the protocol.", tags=["Discovery"])
async def activity_feed(request: Request, limit: int = 20, offset: int = 0):
    _check_rate_limit(_get_client_ip(request), "default", request)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    result = get_recent_traces(limit, offset)
    for trace in result.get("data", []):
        trace["verification"] = {
            "trace_hash": trace.get("trace_hash"),
            "verify_url": f"/api/v1/verify/{trace.get('trace_hash')}" if trace.get("trace_hash") else None,
            "algorithm": "ECDSA-secp256k1",
            "hash_algorithm": "SHA-256",
        }
    return result


@router.get(
    "/public-stats",
    summary="Public dashboard stats (Wave 2 — receipts, capabilities, compensations)",
    tags=["Discovery"],
)
async def public_dashboard_stats():
    """Live public counts. Used by https://garl.ai/stats. No auth, cache-friendly."""
    return get_public_stats()


@router.get("/stats", summary="Protocol statistics", tags=["Discovery"])
async def protocol_stats():
    cached = cache_get("stats")
    if cached:
        return cached
    result = get_stats()
    cache_set("stats", result, ttl=60)
    return result


@router.get("/stats/daily", summary="Daily trace statistics", tags=["Discovery"])
async def daily_stats(request: Request, days: int = 30):
    """Daily trace counts and average trust deltas for the last N days."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    if days < 1 or days > 90:
        raise HTTPException(status_code=422, detail="days must be between 1 and 90")

    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    db = _get_supabase()
    res = (
        db.table("traces")
        .select("created_at, trust_delta, status")
        .gt("created_at", cutoff)
        .order("created_at", desc=False)
        .execute()
    )

    from collections import defaultdict
    daily: dict[str, dict] = defaultdict(lambda: {"traces": 0, "success": 0, "failure": 0, "avg_delta": 0.0, "total_delta": 0.0})

    for trace in (res.data or []):
        day = trace["created_at"][:10]
        daily[day]["traces"] += 1
        daily[day]["total_delta"] += float(trace.get("trust_delta", 0))
        if trace.get("status") == "success":
            daily[day]["success"] += 1
        elif trace.get("status") == "failure":
            daily[day]["failure"] += 1

    result = []
    for day, data in sorted(daily.items()):
        data["date"] = day
        data["avg_delta"] = round(data["total_delta"] / data["traces"], 2) if data["traces"] > 0 else 0
        del data["total_delta"]
        result.append(data)

    return {"days": days, "data": result}


@router.get("/usage", summary="API usage info", tags=["Discovery"])
async def api_usage(request: Request, x_api_key: str = Header(default=None)):
    """Returns rate limit tiers, current usage, and agent stats if authenticated."""
    ip = _get_client_ip(request)

    tiers_info = {name: {"max_requests": lim, "window_seconds": win} for name, (lim, win) in RATE_LIMITS.items()}

    result = {
        "rate_limits": tiers_info,
        "your_ip_hash": hashlib.sha256(ip.encode()).hexdigest()[:12],
    }

    if x_api_key:
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        db = _get_supabase()
        match = db.table("agents").select("id, name, total_traces, trust_score, certification_tier, created_at").eq("api_key_hash", key_hash).limit(1).execute()
        if match.data:
            agent = match.data[0]
            result["agent"] = {
                "id": agent["id"],
                "name": agent["name"],
                "total_traces": agent["total_traces"],
                "trust_score": float(agent["trust_score"]),
                "certification_tier": agent.get("certification_tier", "bronze"),
                "member_since": agent.get("created_at"),
            }

    return result


# --- A2A Trust ---

@router.get("/trust/verify", summary="A2A trust check", tags=["Trust & Verification"])
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


@router.post("/trust/verify/batch", summary="Batch A2A trust check", tags=["Trust & Verification"])
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

@router.get("/trust/route", summary="Smart agent routing", tags=["Trust & Verification"])
async def trust_route(category: str, min_tier: str = "silver", limit: int = 3):
    """Recommend the most trusted agents filtered by category and tier."""
    valid_tiers = ["bronze", "silver", "gold", "enterprise"]
    if min_tier not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {valid_tiers}")
    return route_agents(category, min_tier, max(1, min(limit, 10)))


# --- Trust History ---

@router.get("/agents/{agent_id}/history", summary="Trust score history", tags=["Agents"])
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

@router.get("/compare", summary="Compare agents side-by-side", tags=["Discovery"])
async def compare(agents: str):
    ids = [a.strip() for a in agents.split(",") if a.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 agent IDs")
    if len(ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 agents")
    for aid in ids:
        _validate_uuid(aid, "agent_id")
    results = compare_agents(ids)
    return results


# --- Badges ---

@router.get("/badge/svg/{agent_id}", summary="SVG trust badge", tags=["Badges"])
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


_REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


@router.get("/badge/repo/{owner}/{repo}.svg", summary="GARL Verified badge for a GitHub repo", tags=["Badges"])
async def badge_repo_svg(owner: str, repo: str):
    """SVG badge for the per-repo agent created by the
    `Garl-Protocol/garl-receipt-action`. Looks up the repo agent by
    canonical name `gh-{owner}-{repo}` (set by the auto-register call
    in the action's setup script) and renders a tier+score badge.

    Drop into a README:

        [![GARL Verified](https://api.garl.ai/api/v1/badge/repo/owner/repo.svg)](https://garl.ai/for-code)
    """
    if not _REPO_SLUG_RE.match(owner) or not _REPO_SLUG_RE.match(repo):
        raise HTTPException(status_code=400, detail="Invalid owner/repo slug.")

    expected_name = f"gh-{owner}-{repo}"
    db = _get_supabase()
    res = (
        db.table("agents")
        .select("id,name,trust_score,certification_tier,total_traces")
        .eq("name", expected_name)
        .eq("is_deleted", False)
        .limit(1)
        .execute()
    )
    rows = res.data or []

    if rows:
        agent = rows[0]
        score = float(agent["trust_score"])
        tier = agent.get("certification_tier", "bronze")
        traces = int(agent.get("total_traces", 0))
        verified = " ✓" if traces >= 1 else ""
        value = f"{score:.1f}"
    else:
        # Repo agent not registered yet — show a "not enrolled" badge.
        tier = "none"
        value = "—"
        verified = ""

    tier_colors = {
        "enterprise": "#a855f7",
        "gold": "#f59e0b",
        "silver": "#94a3b8",
        "bronze": "#92400e",
        "none": "#525252",
    }
    color = tier_colors.get(tier, "#00ff88")
    label = f"GARL {tier.upper()}" if tier != "none" else "GARL"
    label_width = len(label) * 7 + 10
    value_width = len(value + verified) * 7 + 14
    total_width = label_width + value_width

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}{verified} — {html_escape(owner)}/{html_escape(repo)}</title>
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
        headers={"Cache-Control": "public, max-age=300, s-maxage=600, stale-while-revalidate=3600"},
    )


@router.get("/badge/widget.js", summary="Embeddable badge widget JS", tags=["Badges"])
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


@router.get("/badge/{agent_id}", summary="Badge data (JSON)", tags=["Badges"])
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


@router.get("/badge/embed/{agent_id}", summary="Embeddable iframe badge", tags=["Badges"])
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

@router.post("/webhooks", summary="Register webhook", tags=["Webhooks"])
async def create_webhook(req: WebhookRegisterRequest, x_api_key: str = Header(...)):
    _validate_uuid(req.agent_id, "agent_id")
    _verify_agent_ownership(req.agent_id, x_api_key)
    hook = register_webhook(req.agent_id, req.url, req.events)
    return hook


@router.get("/webhooks/{agent_id}", summary="List agent webhooks", tags=["Webhooks"])
async def list_agent_webhooks(agent_id: str, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _verify_agent_ownership(agent_id, x_api_key)
    return list_webhooks(agent_id)


@router.patch("/webhooks/{agent_id}/{webhook_id}", summary="Update webhook", tags=["Webhooks"])
async def patch_webhook(agent_id: str, webhook_id: str, req: WebhookUpdateRequest, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _validate_uuid(webhook_id, "webhook_id")
    _verify_agent_ownership(agent_id, x_api_key)
    result = update_webhook(webhook_id, agent_id, req.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return result


@router.delete("/webhooks/{agent_id}/{webhook_id}", summary="Delete webhook", tags=["Webhooks"])
async def remove_webhook(agent_id: str, webhook_id: str, x_api_key: str = Header(...)):
    _validate_uuid(agent_id, "agent_id")
    _validate_uuid(webhook_id, "webhook_id")
    _verify_agent_ownership(agent_id, x_api_key)
    deleted = delete_webhook(webhook_id, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"deleted": True}


# --- Endorsement (Sybil-Resistant) ---

@router.post("/endorse", summary="Endorse an agent", tags=["Endorsements"])
async def endorse_agent(request: Request, req: EndorsementRequest, x_api_key: str = Header(...)):
    _check_rate_limit(x_api_key[:16], "default", request)
    _validate_uuid(req.target_agent_id, "target_agent_id")

    db = _get_supabase()
    endorser_res = db.table("agents").select("id, api_key_hash").eq("api_key_hash", hashlib.sha256(x_api_key.encode()).hexdigest()).execute()
    if not endorser_res.data:
        raise HTTPException(status_code=403, detail="Invalid API key")
    endorser_id = endorser_res.data[0]["id"]

    safe_context = _strip_html(req.context, 500) if req.context else ""
    try:
        result = create_endorsement(endorser_id, req.target_agent_id, safe_context, x_api_key)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/endorsements/{agent_id}", summary="Get agent endorsements", tags=["Endorsements"])
async def read_endorsements(agent_id: str):
    _validate_uuid(agent_id, "agent_id")
    return get_endorsements(agent_id)


# --- GDPR & Data Protection ---

@router.delete("/agents/{agent_id}", summary="Soft delete agent (GDPR)", tags=["GDPR & Privacy"])
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


@router.post("/agents/{agent_id}/anonymize", summary="Anonymize agent (GDPR)", tags=["GDPR & Privacy"])
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

@router.get("/agents/{agent_id}/compliance", summary="Compliance report (CISO)", tags=["Agents"])
async def read_compliance(agent_id: str, x_api_key: str | None = Header(default=None)):
    """Enterprise compliance report: SLA, security risks, anomaly history."""
    _validate_uuid(agent_id, "agent_id")
    _require_read_auth(x_api_key)
    report = get_compliance_report(agent_id)
    if not report:
        raise HTTPException(status_code=404, detail="Agent not found")
    return report


# OpenClaw integration removed in 2026-04 — OpenClaw EOL'd, the bridge had
# no active callers. Submit traces via POST /api/v1/verify directly, or
# use Action Receipt v0.1 (POST /api/v1/verify with security_context.
# action_receipt_version="garl/action-receipt/v0.1").


# --- Agent Search ---

@router.get("/search", summary="Search agents", description="Full-text search across agent names and descriptions. Supports category filter.", tags=["Discovery"])
async def search_agents_endpoint(q: str = "", category: str | None = None, limit: int = 10, offset: int = 0):
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0")
    return search_agents(q, category, max(1, min(limit, 50)), max(0, offset))


# ──────────────────────────────────────────────────────────────────────
# Wave 2: Capability tokens, Capability Gate, Action Receipt v0.1, Reversibility
# ──────────────────────────────────────────────────────────────────────

@router.post(
    "/capability/issue",
    summary="Issue a capability token",
    tags=["Capability"],
)
async def issue_capability(request: Request, body: dict, x_api_key: str = Header(...)):
    """Issue a fresh capability token. JWT-shaped + ECDSA-secp256k1 + RFC 6979.
    Required body fields: ``agent_id``, ``scope``, ``side_effect_class``.
    Optional: ``expires_in_seconds`` (default 3600), ``spend_limit_usd``,
    ``merchant_allowlist``, ``caveats``, ``parent_token_hash``,
    ``human_delegate``."""
    from app.services.capability_tokens import issue_capability_token

    _check_rate_limit(x_api_key[:16], "write", request)
    required = ("agent_id", "scope", "side_effect_class")
    for f in required:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Field {f!r} required")
    _validate_uuid(body["agent_id"], "agent_id")
    try:
        return issue_capability_token(
            agent_id=body["agent_id"],
            scope=body["scope"],
            side_effect_class=body["side_effect_class"],
            expires_in_seconds=int(body.get("expires_in_seconds", 3600)),
            spend_limit_usd=body.get("spend_limit_usd"),
            merchant_allowlist=body.get("merchant_allowlist"),
            caveats=body.get("caveats"),
            parent_token_hash=body.get("parent_token_hash"),
            human_delegate=body.get("human_delegate"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/capability/verify",
    summary="Verify a capability token",
    tags=["Capability"],
)
async def verify_capability(request: Request, body: dict):
    """Verify a token's signature, expiration, and (optionally) revocation.
    Public endpoint — anyone can verify offline against the registry, but
    a remote check goes through this endpoint for revocation freshness."""
    from app.services.capability_tokens import (
        CapabilityTokenInvalid,
        verify_capability_token,
    )

    _check_rate_limit(_get_client_ip(request), "default", request)
    if not body.get("token"):
        raise HTTPException(status_code=422, detail="Field 'token' required")
    try:
        claims = verify_capability_token(
            body["token"],
            check_revocation=bool(body.get("check_revocation", True)),
        )
        return {"valid": True, "claims": claims}
    except CapabilityTokenInvalid as e:
        return {"valid": False, "reason": str(e)}


@router.post(
    "/capability/revoke",
    summary="Revoke a capability token (cascades to descendants)",
    tags=["Capability"],
)
async def revoke_capability(request: Request, body: dict, x_api_key: str = Header(...)):
    """Mark a token revoked. Cascades to all attenuated descendants."""
    from app.services.capability_tokens import revoke_capability_token

    _check_rate_limit(x_api_key[:16], "write", request)
    if not body.get("token_hash"):
        raise HTTPException(status_code=422, detail="Field 'token_hash' required")
    reason = body.get("reason") or "manual-revoke"
    cascade = bool(body.get("cascade", True))
    return revoke_capability_token(body["token_hash"], reason, cascade=cascade)


@router.post(
    "/capability/evaluate",
    summary="Capability Gate pre-flight",
    tags=["Capability"],
)
async def evaluate_capability(request: Request, body: dict):
    """Pre-flight: should this agent be allowed to perform this action?
    Returns a decision plus, if allowed, a freshly-minted scoped capability
    token. Public — the agent should call this before each side-effecting
    action and present the resulting token to the tool server."""
    from app.services.capability_gate import GateError, evaluate_request

    _check_rate_limit(_get_client_ip(request), "default", request)
    required = ("agent_id", "action_type", "side_effect_class")
    for f in required:
        if not body.get(f):
            raise HTTPException(status_code=422, detail=f"Field {f!r} required")
    _validate_uuid(body["agent_id"], "agent_id")
    try:
        return evaluate_request(
            agent_id=body["agent_id"],
            action_type=body["action_type"],
            side_effect_class=body["side_effect_class"],
            target=body.get("target"),
            requested_scope=body.get("requested_scope"),
            expires_in_seconds=int(body.get("expires_in_seconds", 3600)),
            spend_limit_usd=body.get("spend_limit_usd"),
            merchant_allowlist=body.get("merchant_allowlist"),
            threshold_override=body.get("threshold_override"),
        )
    except GateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/receipts",
    summary="Submit Action Receipt v0.1 (generic, beyond commits)",
    tags=["Receipts"],
)
async def submit_receipt(request: Request, body: dict, x_api_key: str = Header(...)):
    """Action Receipt v0.1 generic submit. Accepts the envelope shape
    declared in protocol/spec/action-receipt-v0.1.md: action_type ∈
    {code_write, api_call, payment, browser_action, file_op, tool_call},
    side_effect ∈ {none, reversible, irreversible}.

    For backward compat, the legacy /verify endpoint stays the way to
    submit git-commit-flavored traces. New surfaces should use this."""
    from app.services.action_receipts import (
        ActionReceiptValidationError,
        submit_action_receipt,
    )

    _check_rate_limit(x_api_key[:16], "write", request)
    try:
        envelope = submit_action_receipt(body)
        return envelope
    except ActionReceiptValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post(
    "/receipts/{receipt_id}/undo",
    summary="UETA §10(b) consumer-undo trigger",
    tags=["Receipts"],
)
async def trigger_receipt_undo(receipt_id: str, request: Request, body: dict):
    """Move a recorded compensation from 'recorded' to 'pending' and
    return the undo payload. Refuses for irreversible receipts."""
    from app.services.reversibility import ReversibilityError, trigger_undo

    _check_rate_limit(_get_client_ip(request), "default", request)
    _validate_uuid(receipt_id, "receipt_id")
    reason = (body.get("reason") if isinstance(body, dict) else None) or "consumer-initiated-undo"
    try:
        return trigger_undo(receipt_id, reason)
    except ReversibilityError as e:
        raise HTTPException(status_code=409, detail=str(e))
