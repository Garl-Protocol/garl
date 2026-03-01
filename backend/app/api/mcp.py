"""
GARL Protocol — Remote MCP Endpoint (Streamable HTTP)
Spec: MCP 2024-11-05, Streamable HTTP transport
Endpoint: POST /mcp
"""

import re
import json
import logging
from typing import Any

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.services.agents import (
    get_agent,
    get_leaderboard,
    compare_agents,
    search_agents,
    route_agents,
    get_recent_traces,
    get_agent_card,
    get_compliance_report,
)
from app.services.traces import submit_trace
from app.models.schemas import TraceSubmitRequest
from app.core.signing import verify_signature

logger = logging.getLogger(__name__)

mcp_router = APIRouter()

SERVER_INFO = {
    "name": "garl-protocol",
    "version": "3.1.0",
}

CAPABILITIES = {
    "tools": {},
}

MCP_TOOLS = [
    {
        "name": "garl_trust_check",
        "description": "Check trust score and delegation recommendation for an AI agent.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "UUID of the agent to check"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "garl_search_agents",
        "description": "Search agents by name, description, or category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query (name or description)"},
                "category": {"type": "string", "description": "Filter by category"},
                "limit": {"type": "number", "description": "Max results (default: 10)", "default": 10},
            },
        },
    },
    {
        "name": "garl_compare",
        "description": "Compare multiple agents side-by-side across all trust dimensions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Agent UUIDs to compare (2-10)",
                    "minItems": 2,
                    "maxItems": 10,
                },
            },
            "required": ["agent_ids"],
        },
    },
    {
        "name": "garl_route",
        "description": "Smart routing — find the best agents for a task category.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Task category (coding, research, etc.)"},
                "min_tier": {
                    "type": "string",
                    "enum": ["bronze", "silver", "gold", "enterprise"],
                    "description": "Minimum certification tier",
                },
                "limit": {"type": "number", "description": "Number of results (default: 10)", "default": 10},
            },
        },
    },
    {
        "name": "garl_leaderboard",
        "description": "Top-performing agents ranked by trust score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by category (optional)"},
                "limit": {"type": "number", "description": "Number of results (default: 10, max: 100)", "default": 10},
            },
        },
    },
    {
        "name": "garl_agent_profile",
        "description": "Get detailed agent profile including trust dimensions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "UUID of the agent"},
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "garl_verify_certificate",
        "description": "Verify a cryptographic trust certificate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "certificate": {"type": "object", "description": "Certificate object to verify"},
            },
            "required": ["certificate"],
        },
    },
    {
        "name": "garl_feed",
        "description": "Get recent trust verification events across the GARL network.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "number", "description": "Number of entries (default: 10, max: 100)", "default": 10},
            },
        },
    },
]


def _jsonrpc_error(code: int, message: str, req_id: Any = None, data: Any = None) -> dict:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "error": err, "id": req_id}


def _jsonrpc_result(result: Any, req_id: Any = None) -> dict:
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


def _require_uuid(value: str | None, field: str = "agent_id") -> str:
    if not value:
        raise ValueError(f"{field} is required")
    if not _UUID_RE.match(value.strip()):
        raise ValueError(f"Invalid {field} format. Expected UUID (e.g. 550e8400-e29b-41d4-a716-446655440000)")
    return value.strip()


def _require_limit(value, default: int = 10, max_val: int = 100) -> int:
    limit = int(value) if value is not None else default
    if limit < 1 or limit > max_val:
        raise ValueError(f"limit must be between 1 and {max_val}")
    return limit


def _handle_tool_call(name: str, args: dict) -> dict:
    """Execute an MCP tool and return result content."""
    if name == "garl_trust_check":
        agent_id = _require_uuid(args.get("agent_id"))
        agent = get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        score = agent.get("trust_score", 0)
        total = agent.get("total_traces", 0)
        tier = agent.get("certification_tier", "bronze")
        verified = total >= 10
        if score >= 75 and verified:
            rec = "trusted"
        elif score >= 60 and verified:
            rec = "trusted_with_monitoring"
        elif score >= 50:
            rec = "proceed_with_monitoring"
        elif score >= 25:
            rec = "caution"
        else:
            rec = "do_not_delegate"
        dims = {
            "reliability": agent.get("score_reliability", 50),
            "security": agent.get("score_security", 50),
            "speed": agent.get("score_speed", 50),
            "cost_efficiency": agent.get("score_cost_efficiency", 50),
            "consistency": agent.get("score_consistency", 50),
        }
        return {
            "content": [{"type": "text", "text": "\n".join([
                f"Agent: {agent['name']}",
                f"Trust Score: {score:.1f}/100",
                f"Tier: {tier}",
                f"Recommendation: {rec}",
                f"Verified: {'Yes' if verified else 'No'} ({total} traces)",
                f"Dimensions: Rel={dims['reliability']:.1f} Sec={dims['security']:.1f} "
                f"Spd={dims['speed']:.1f} Cost={dims['cost_efficiency']:.1f} Con={dims['consistency']:.1f}",
            ])}]
        }

    elif name == "garl_search_agents":
        q = args.get("query", "")
        cat = args.get("category")
        limit = _require_limit(args.get("limit"), 10, 50)
        results = search_agents(q, cat if cat and cat != "all" else None, limit)
        if not results:
            return {"content": [{"type": "text", "text": "No agents found."}]}
        rows = [f"{a['name']} — Score: {a['trust_score']:.1f} ({a.get('category', 'other')}, {a.get('total_traces', 0)} traces)"
                for a in results]
        return {"content": [{"type": "text", "text": "Search Results:\n\n" + "\n".join(rows)}]}

    elif name == "garl_compare":
        ids = args.get("agent_ids", [])
        if len(ids) < 2:
            raise ValueError("At least 2 agent_ids required")
        if len(ids) > 10:
            raise ValueError("Maximum 10 agent_ids")
        for aid in ids:
            _require_uuid(aid, "agent_ids[]")
        results = compare_agents(ids)
        rows = [
            f"{a['name']}: Score={a['trust_score']:.1f} "
            f"Rel={a.get('score_reliability', 50):.1f} Sec={a.get('score_security', 50):.1f} "
            f"Spd={a.get('score_speed', 50):.1f} Cost={a.get('score_cost_efficiency', 50):.1f} "
            f"Con={a.get('score_consistency', 50):.1f}"
            for a in results
        ]
        return {"content": [{"type": "text", "text": "Agent Comparison:\n\n" + "\n".join(rows)}]}

    elif name == "garl_route":
        cat = args.get("category", "coding")
        min_tier = args.get("min_tier", "silver")
        limit = _require_limit(args.get("limit"), 10, 50)
        result = route_agents(cat, min_tier, limit)
        recs = result.get("recommendations", [])
        if not recs:
            return {"content": [{"type": "text", "text": "No agents found for this category/tier."}]}
        rows = [f"{i+1}. {a.get('name', a.get('agent_id', '?'))} — Score: {a.get('trust_score', 0):.1f} [{a.get('certification_tier', 'N/A')}]"
                for i, a in enumerate(recs)]
        return {"content": [{"type": "text", "text": "Routing Results:\n\n" + "\n".join(rows)}]}

    elif name == "garl_leaderboard":
        cat = args.get("category")
        limit = _require_limit(args.get("limit"), 10, 100)
        results = get_leaderboard(cat if cat and cat != "all" else None, limit)
        rows = [f"#{a.get('rank', i+1)} {a['name']} — {a['trust_score']:.1f} ({a.get('framework', '?')}, {a.get('total_traces', 0)} traces)"
                for i, a in enumerate(results)]
        return {"content": [{"type": "text", "text": "GARL Leaderboard:\n\n" + "\n".join(rows)}]}

    elif name == "garl_agent_profile":
        agent_id = _require_uuid(args.get("agent_id"))
        agent = get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        safe_agent = {k: v for k, v in agent.items() if k not in ("api_key_hash",)}
        return {"content": [{"type": "text", "text": json.dumps(safe_agent, indent=2, default=str)}]}

    elif name == "garl_verify_certificate":
        cert = args.get("certificate")
        if not cert:
            raise ValueError("certificate is required")
        valid = verify_signature(cert)
        from app.core.signing import get_public_key_hex
        return {"content": [{"type": "text", "text": json.dumps({"valid": valid, "public_key": get_public_key_hex()})}]}

    elif name == "garl_feed":
        limit = _require_limit(args.get("limit"), 10, 100)
        results = get_recent_traces(limit)
        if not results:
            return {"content": [{"type": "text", "text": "No recent feed entries."}]}
        rows = []
        for e in results:
            delta = e.get("trust_delta", 0)
            delta_str = f"+{delta:.2f}" if delta > 0 else f"{delta:.2f}"
            status = "OK" if e.get("status") == "success" else "FAIL"
            rows.append(f"{status} {e.get('agent_name', e.get('agent_id', '?')[:8])} — "
                        f"{(e.get('task_description') or '?')[:60]} ({delta_str})")
        return {"content": [{"type": "text", "text": "Live Trust Feed:\n\n" + "\n".join(rows)}]}

    else:
        raise ValueError(f"Unknown tool: {name}")


def _handle_message(msg: dict) -> dict | None:
    """Process a single JSON-RPC 2.0 message, return response or None for notifications."""
    req_id = msg.get("id")
    method = msg.get("method", "")
    params = msg.get("params", {})

    if msg.get("jsonrpc") != "2.0":
        return _jsonrpc_error(-32600, "Invalid Request: jsonrpc field must be \"2.0\"", req_id)

    if req_id is None and method not in ("initialize", "notifications/initialized"):
        return None

    if method == "initialize":
        return _jsonrpc_result({
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": CAPABILITIES,
        }, req_id)

    if method == "ping":
        return _jsonrpc_result({}, req_id)

    if method == "tools/list":
        return _jsonrpc_result({"tools": MCP_TOOLS}, req_id)

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            result = _handle_tool_call(tool_name, tool_args)
            return _jsonrpc_result(result, req_id)
        except Exception as exc:
            return _jsonrpc_result(
                {"content": [{"type": "text", "text": f"Error: {exc}"}], "isError": True},
                req_id,
            )

    if method == "notifications/initialized":
        return None

    return _jsonrpc_error(-32601, f"Method not found: {method}", req_id)


@mcp_router.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP Streamable HTTP endpoint — JSON-RPC 2.0 over POST."""
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return JSONResponse(
            status_code=415,
            content=_jsonrpc_error(-32700, "Content-Type must be application/json"),
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content=_jsonrpc_error(-32700, "Parse error"),
        )

    if isinstance(body, list):
        responses = []
        for msg in body:
            resp = _handle_message(msg)
            if resp is not None:
                responses.append(resp)
        if not responses:
            return JSONResponse(status_code=204, content=None)
        return JSONResponse(content=responses)

    if not isinstance(body, dict):
        return JSONResponse(
            status_code=400,
            content=_jsonrpc_error(-32600, "Invalid Request"),
        )

    resp = _handle_message(body)
    if resp is None:
        return JSONResponse(status_code=204, content=None)
    return JSONResponse(content=resp)
