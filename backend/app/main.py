from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.routes import router
from app.services.agents import get_agent_card, get_leaderboard
from app.core.signing import get_public_key_hex

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Global Agent Reputation Ledger — Sovereign Trust Layer for the Agent Economy",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "protocol": "GARL",
        "version": settings.app_version,
        "codename": "Sovereign Trust Layer",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.app_version, "protocol": "garl"}


@app.get("/api/v1/health")
async def health_v1():
    return {"status": "healthy", "version": settings.app_version, "protocol": "garl"}


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

    top_agents = get_leaderboard(None, 20, 0)
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
        "description": "Global Agent Reputation Ledger — The Universal Trust Standard for AI Agents. "
                       "Five-dimensional trust scoring, DID-based sovereign identity, certification tiers, "
                       "smart routing, and GDPR-compliant agent lifecycle management.",
        "version": settings.app_version,
        "protocol": "garl/v1",
        "url": "https://garl.ai",
        "provider": {
            "organization": "GARL Protocol",
            "url": "https://garl.ai",
        },
        "interoperability_standards": ["garl/v1", "a2a/v1", "mcp/v1"],
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
            "openclaw_bridge": True,
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
            "server_name": "garl-mcp-server",
            "tools": [
                "garl_verify", "garl_verify_batch", "garl_check_trust",
                "garl_should_delegate", "garl_route",
                "garl_get_score", "garl_trust_history",
                "garl_leaderboard", "garl_compare",
                "garl_agent_card", "garl_endorse",
                "garl_register_webhook", "garl_search",
                "garl_compliance", "garl_soft_delete", "garl_anonymize",
            ],
        },
        "openclaw": {
            "skill": "garl-reputation",
            "webhook_endpoint": "/api/v1/ingest/openclaw",
        },
        "llms_txt": "https://garl.ai/llms.txt",
    }
