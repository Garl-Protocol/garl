import logging
import uuid as _uuid

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import get_settings
from app.api.routes import router
from app.api.a2a import a2a_router
from app.api.mcp import mcp_router
from app.services.agents import get_agent_card, get_leaderboard
from app.core.signing import get_public_key_hex, get_key_registry

_log = logging.getLogger("garl")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "GARL Protocol — cryptographic verification for AI-authored code. "
        "Signed receipts for every AI-generated commit with ECDSA-secp256k1 "
        "and an immutable ledger. Provenance evidence for EU AI Act, "
        "California SB 942, and ISO/IEC 42001 Annex B."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {"url": "https://api.garl.ai", "description": "Canonical production registry"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    # The API authenticates via the x-api-key header, never cookies, so
    # credentialed CORS is unnecessary. Keeping it off removes the footgun
    # where a future wildcard origin would become credential-exfiltratable.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


_A2A_SUPPORTED_VERSIONS = {"1.0"}
_A2A_PATHS = {"/a2a"}

# Endpoints that belong to the pre-pivot agent-reputation surface.
# We keep them live but add Deprecation / Sunset headers so integrators
# have a clear signal and migration window. Sunset is 12 months out
# from the Phase 7 rollout.
_DEPRECATED_PATH_PREFIXES = (
    "/api/v1/trust/",
    "/api/v1/a2a/",
    "/api/v1/erc8004/",
    "/api/v1/erc8004",
    "/a2a",
)
_DEPRECATION_SUNSET = "Thu, 15 Apr 2027 00:00:00 GMT"
_DEPRECATION_LINK = '<https://garl.ai/for-code>; rel="successor-version"'


@app.middleware("http")
async def deprecated_endpoints_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if any(path.startswith(p) for p in _DEPRECATED_PATH_PREFIXES):
        response.headers["Deprecation"] = "true"
        response.headers["Sunset"] = _DEPRECATION_SUNSET
        response.headers["Link"] = _DEPRECATION_LINK
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    from app.api.routes import rate_limit_info
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    if not request.url.path.startswith("/api/v1/badge/embed/"):
        response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
        fa = "'none'" if not request.url.path.startswith("/api/v1/badge/embed/") else "*"
        response.headers["Content-Security-Policy"] = f"default-src 'none'; frame-ancestors {fa}"
    rl = getattr(request.state, "rate_limit_headers", None) or rate_limit_info.get(None)
    if rl:
        for k, v in rl.items():
            response.headers[k] = v
        rate_limit_info.set(None)
    return response


@app.middleware("http")
async def a2a_version_middleware(request: Request, call_next):
    if request.url.path in _A2A_PATHS:
        version = (
            request.headers.get("A2A-Version", "").strip()
            or request.headers.get("A2A-Protocol-Version", "").strip()
        )
        if version and version not in _A2A_SUPPORTED_VERSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "VersionNotSupported",
                        "data": {
                            "supported": list(_A2A_SUPPORTED_VERSIONS),
                            "requested": version,
                        },
                    },
                    "id": None,
                },
            )
    return await call_next(request)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak exception repr to the client. Log full details server-side with
    # a correlation id the caller can quote when reporting an incident.
    correlation_id = str(_uuid.uuid4())
    _log.exception(
        "unhandled_exception correlation_id=%s path=%s method=%s",
        correlation_id,
        request.url.path,
        request.method,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "correlation_id": correlation_id,
        },
    )


app.include_router(router)
app.include_router(a2a_router)
app.include_router(mcp_router)

from app.api.pr_bot_routes import pr_bot_router  # noqa: E402  (import order kept
app.include_router(pr_bot_router)                # intentionally — the router
                                                 # needs the main app ready.)


@app.get("/")
async def root():
    return {
        "protocol": "GARL",
        "version": settings.app_version,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.app_version, "protocol": "garl"}


@app.get("/api/v1/health")
async def health_v1():
    return {"status": "healthy", "version": settings.app_version, "protocol": "garl"}


@app.get("/.well-known/garl-keys.json")
async def well_known_garl_keys(response: Response):
    """Public key registry (JWKS-style) for offline receipt verification.

    Receipts issued by this registry carry ``proof.key_id``; verifiers
    should resolve that id against the ``keys`` array here. Retired keys
    remain listed so old receipts stay verifiable after rotation."""
    response.headers["Cache-Control"] = "public, max-age=300, s-maxage=3600"
    return get_key_registry()


@app.get("/.well-known/security.txt", include_in_schema=False)
@app.get("/security.txt", include_in_schema=False)
async def well_known_security_txt(response: Response):
    """RFC 9116 security.txt — vulnerability disclosure contact.

    A security researcher's first stop. Without it, a discovered issue is more
    likely to be dropped publicly than reported. Expires is computed ~1 year
    out on each request so it never goes stale."""
    expires = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = (
        "# GARL Protocol security contact (RFC 9116)\n"
        "Contact: https://github.com/Garl-Protocol/garl/security/advisories/new\n"
        "Contact: mailto:security@garl.ai\n"
        f"Expires: {expires}\n"
        "Preferred-Languages: en, tr\n"
        "Canonical: https://api.garl.ai/.well-known/security.txt\n"
        "Policy: https://github.com/Garl-Protocol/garl/blob/main/SECURITY.md\n"
    )
    response.headers["Cache-Control"] = "public, max-age=86400"
    return PlainTextResponse(content=body, headers=response.headers)


@app.get("/.well-known/agent-card.json")
async def well_known_agent_card():
    """A2A v1.0 compliant Agent Card (RFC agent-card.json)."""
    return {
        "name": "GARL Protocol",
        "description": (
            "Proof-of-Trust oracle for autonomous AI agents. "
            "Cryptographic trust scoring, verification, and smart routing."
        ),
        "supportedInterfaces": [
            {
                "url": "https://api.garl.ai/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            },
            {
                "url": "https://api.garl.ai/mcp",
                "protocolBinding": "MCP",
                "protocolVersion": "2024-11-05",
            },
        ],
        "provider": {
            "organization": "Garl Protocol",
            "url": "https://garl.ai",
        },
        "version": settings.app_version,
        "documentationUrl": "https://garl.ai/docs",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "securitySchemes": {
            "garlApiKey": {
                "apiKeySecurityScheme": {
                    "location": "header",
                    "name": "x-api-key",
                }
            }
        },
        "securityRequirements": [{"garlApiKey": []}],
        "defaultInputModes": ["application/json", "text/plain"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "trust_check",
                "name": "Check Agent Trust",
                "description": "Verify trust score and certification tier for any registered agent",
                "tags": ["trust", "verification", "reputation", "scoring"],
                "examples": [
                    "Is agent X trusted?",
                    "What is the trust score for did:garl:abc123?",
                ],
            },
            {
                "id": "verify_trace",
                "name": "Submit Execution Trace",
                "description": "Submit and cryptographically sign an agent execution trace for reputation scoring",
                "tags": ["trace", "verification", "signing", "execution"],
            },
            {
                "id": "route_agent",
                "name": "Smart Agent Routing",
                "description": "Find the most trusted agent for a given task category and minimum tier",
                "tags": ["routing", "delegation", "discovery", "recommendation"],
            },
            {
                "id": "compare_agents",
                "name": "Compare Agents",
                "description": "Side-by-side 5-dimensional trust comparison of multiple agents",
                "tags": ["comparison", "analysis", "scoring"],
            },
            {
                "id": "register_agent",
                "name": "Register Agent",
                "description": "Zero-friction agent registration with sovereign DID identity",
                "tags": ["registration", "identity", "onboarding"],
            },
        ],
        "extensions": {
            "registration": {
                "url": "https://api.garl.ai/api/v1/agents/auto-register",
                "method": "POST",
                "required_fields": ["name"],
                "instructions": (
                    "Send POST with {\"name\":\"your-name\",\"framework\":\"your-framework\"} "
                    "to instantly receive a DID identity and API key. "
                    "Then submit execution traces via POST /api/v1/verify to build trust."
                ),
            },
            "mcp": {
                "remote_endpoint": "https://api.garl.ai/mcp",
                "transport": "streamable-http",
                "npm_package": "@garl-protocol/mcp-server",
            },
            "erc8004": {
                "compatible": True,
                "metadata_endpoint": "https://api.garl.ai/api/v1/agents/{agent_id}/erc8004",
                "feedback_endpoint": "https://api.garl.ai/api/v1/agents/{agent_id}/erc8004/feedback",
                "cryptographic_curve": "secp256k1",
                "description": "GARL trust scores available in ERC-8004 Reputation Registry format",
            },
            "llms_txt": "https://garl.ai/llms.txt",
        },
    }


@app.get("/.well-known/agent.json")
async def well_known_agent(agent_id: str = Query(default=None)):
    if agent_id:
        try:
            card = get_agent_card(agent_id)
        except Exception:
            raise HTTPException(status_code=404, detail="Agent not found")
        if not card:
            raise HTTPException(status_code=404, detail="Agent not found")
        return card

    top_agents = get_leaderboard(None, 20, 0).get("data", [])
    agent_skills = [
        {
            "id": a["id"],
            "name": a["name"],
            "description": f"[{a.get('certification_tier', 'bronze').upper()}] Trust: {a['trust_score']:.1f}/100 | {a['total_traces']} traces | {a['framework']}",
        }
        for a in top_agents
    ]

    base_url = "https://api.garl.ai"

    return {
        "name": "GARL Protocol",
        "description": "GARL Protocol — cryptographic verification for AI-authored code. "
                       "ECDSA-secp256k1 signed receipts for every AI-generated commit, "
                       "immutable ledger, compliance export for EU AI Act / CA SB 942 / "
                       "ISO 42001. Agent reputation scoring available as a secondary surface.",
        "version": settings.app_version,
        "protocol": "garl/v1",
        "url": "https://garl.ai",
        "provider": {
            "organization": "GARL Protocol",
            "url": "https://garl.ai",
        },
        "interoperability_standards": ["garl/v1", "a2a/v1", "mcp/v1"],
        "a2a_agent_card": "/.well-known/agent-card.json",
        "api": {
            "type": "rest",
            "base_url": f"{base_url}/api/v1",
            "docs_url": f"{base_url}/docs",
            "health_url": f"{base_url}/health",
        },
        "authentication": {
            "schemes": [
                {
                    "type": "apiKey",
                    "in": "header",
                    "name": "x-api-key",
                    "description": "API key returned on agent registration via POST /api/v1/agents",
                }
            ],
        },
        "registration": {
            "url": f"{base_url}/api/v1/agents/auto-register",
            "method": "POST",
            "content_type": "application/json",
            "required_fields": ["name"],
            "optional_fields": ["framework", "category", "description"],
            "instructions": (
                "To register your agent, send a POST request with at least a 'name' field. "
                "You will receive an api_key (shown once — store it) and a DID (did:garl:uuid). "
                "Then submit execution traces via POST /api/v1/verify to build trust. "
                "Other agents check your trust score before delegating work. No score = no delegation."
            ),
            "example_request": {
                "name": "my-agent",
                "framework": "langchain",
            },
            "example_response_fields": ["id", "api_key", "sovereign_id", "trust_score", "instructions"],
        },
        "trust_gate": {
            "description": "Agents using GARL check trust scores before delegating work. "
                           "Unregistered agents receive 'unknown' recommendation and are typically rejected. "
                           "Register to participate in the agent economy.",
            "check_endpoint": f"{base_url}/api/v1/trust/verify?agent_id=AGENT_UUID",
            "recommendation_levels": [
                {"level": "trusted", "min_score": 75, "requires_verified": True},
                {"level": "trusted_with_monitoring", "min_score": 60, "requires_verified": True},
                {"level": "proceed_with_monitoring", "min_score": 50},
                {"level": "caution", "min_score": 25},
                {"level": "do_not_delegate", "min_score": 0},
            ],
        },
        "capabilities": {
            "trust_verification": True,
            "cryptographic_certificates": True,
            "five_dimensional_scoring": True,
            "security_dimension": True,
            "certification_tiers": True,
            "did_identity": True,
            "smart_routing": True,
            "agent_comparison": True,
            "webhook_notifications": True,
            "svg_badges": True,
            "sybil_resistant_endorsements": True,
            "pii_masking": True,
            "anomaly_detection": True,
            "proactive_delegation_guard": True,
            "gdpr_compliance": True,
            "compliance_reports": True,
            "auto_registration": True,
        },
        "certification_tiers": {
            "bronze": {"range": "0-40", "description": "Starter / Unverified"},
            "silver": {"range": "40-70", "description": "Trusted / Active"},
            "gold": {"range": "70-90", "description": "High Performance / Verified"},
            "enterprise": {"range": "90+", "description": "Zero Anomaly / SLA Compliant"},
        },
        "skills": agent_skills,
        "trust": {
            "public_key": get_public_key_hex(),
            "algorithm": "ECDSA-secp256k1",
            "hash_algorithm": "SHA-256",
            "dimensions": ["reliability", "security", "speed", "cost_efficiency", "consistency"],
            "weights": {
                "reliability": 0.30,
                "security": 0.20,
                "speed": 0.15,
                "cost_efficiency": 0.10,
                "consistency": 0.25,
            },
            "scoring_method": "exponential_moving_average",
            "ema_alpha": 0.3,
        },
        "mcp": {
            "server_name": "garl-protocol",
            "remote_endpoint": "https://api.garl.ai/mcp",
            "transport": "streamable-http",
            "protocol_version": "2024-11-05",
            "npm_package": "@garl-protocol/mcp-server",
            "tools": [
                "garl_verify", "garl_verify_batch", "garl_check_trust",
                "garl_should_delegate", "garl_route",
                "garl_get_score", "garl_trust_history",
                "garl_leaderboard", "garl_compare",
                "garl_agent_card", "garl_endorse",
                "garl_register_webhook", "garl_search",
                "garl_compliance", "garl_soft_delete", "garl_anonymize",
                "garl_register_agent", "garl_get_feed",
            ],
        },
        "agent_manifest": "https://garl.ai/agents.txt",
        "llms_txt": "https://garl.ai/llms.txt",
    }
